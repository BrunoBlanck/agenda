"""Correções da revisão rodada 1 das notificações (A2 a A5 e sugestões aplicadas).

A2/A3 usam um servidor SMTP lento **de verdade** (aceita a conexão e manda a saudação um byte por segundo:
o tempo limite por operação nunca estoura) e relógios simulados com o pior caso de duração.
"""

import socket
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import get_engine
from app.services import config_notificacoes, envio_email, tarefa_notificacoes
from app.services.envio_email import (
    MSG_ACENTOS,
    MSG_CONECTAR,
    MSG_DEMOROU,
    PRAZO_ENVIO,
    ConfigSmtp,
    Email,
    EnvioFalso,
    EnvioSmtp,
    FalhaEnvio,
    _publico,
)
from app.services.tarefa_notificacoes import (
    MSG_LEMBRETE_VENCIDO,
    MSG_VENCIDO,
    ORCAMENTO_LOJA,
    RESERVA,
    Despachante,
    processar,
)
from tests.clinica import SEGUNDA, montar_clinica
from tests.fabricas import usuario_com
from tests.test_conta_cliente import LOJA, criar_conta
from tests.test_notificacoes import avisos, criar_no_painel, dar_email, ligar_smtp, mudar
from tests.test_notificacoes_envio import SMTP_COMPLETO, URL, erros, fila, salvar

NOVE = datetime.fromisoformat(f'{SEGUNDA}T09:00:00-03:00')


# --- SMTP lento de verdade ----------------------------------------------------------------------------


@pytest.fixture
def smtp_lento():
    """Porta de um servidor que goteja a saudação (1 byte/s por até 60 s) e conta as conexões."""
    parar = threading.Event()
    servidor = socket.socket()
    try:  # porta aceita pelo CHECK de loja_configuracoes.smtp_porta
        servidor.bind(('127.0.0.1', 2525))
    except OSError:
        servidor.close()
        pytest.skip('Porta 2525 ocupada nesta máquina.')
    servidor.listen(16)
    servidor.settimeout(0.2)
    conexoes: list[int] = []

    def atender(conexao: socket.socket) -> None:
        try:
            conexao.sendall(b'220-')
            for _ in range(60):
                if parar.is_set():
                    break
                time.sleep(1)
                conexao.sendall(b'x')
        except OSError:
            pass
        finally:
            conexao.close()

    def aceitar() -> None:
        while not parar.is_set():
            try:
                conexao, _ = servidor.accept()
            except (TimeoutError, OSError):
                continue
            conexoes.append(1)
            threading.Thread(target=atender, args=(conexao,), daemon=True).start()

    fio = threading.Thread(target=aceitar, daemon=True)
    fio.start()
    yield servidor.getsockname()[1], conexoes
    parar.set()
    fio.join(2)
    servidor.close()


def configurar(engine, loja_id, servidor: str, porta: int) -> None:
    with engine.begin() as conexao:
        conexao.execute(
            text(
                'UPDATE loja_configuracoes SET smtp_ativo = true, smtp_servidor = :s, smtp_porta = :p,'
                " smtp_seguranca = 'starttls', smtp_remetente_email = 'avisos@loja.com' WHERE loja_id = :l"
            ),
            {'s': servidor, 'p': porta, 'l': loja_id},
        )


def config_lenta(porta: int) -> ConfigSmtp:
    return ConfigSmtp('127.0.0.1', porta, 'starttls', None, None, 'avisos@loja.com', None)


# --- A2: prazo total por envio, lote interrompido, orçamento por loja, lojas em paralelo ----------------


def test_prazo_padrao_e_de_15_segundos():
    assert PRAZO_ENVIO == 15
    assert EnvioSmtp().prazo == 15


def test_prazo_e_do_envio_inteiro_mesmo_com_servidor_gotejando(smtp_lento):
    porta, _ = smtp_lento
    inicio = time.monotonic()
    with pytest.raises(FalhaEnvio) as erro:
        EnvioSmtp(prazo=2).enviar(config_lenta(porta), Email('maria@example.com', 'Oi', 'Corpo'))
    duracao = time.monotonic() - inicio
    assert 1.8 < duracao < 4  # sem o vigia, levaria os 60 s da saudação gotejada
    assert (erro.value.mensagem, erro.value.definitiva, erro.value.conexao) == (MSG_DEMOROU, False, True)


def test_loja_com_smtp_lento_nao_atrasa_as_outras_e_nao_gasta_tentativas(
    cliente, lojas, engine_dono, smtp_lento
):
    porta, conexoes = smtp_lento
    lenta, rapida = montar_clinica(cliente, lojas[0]), montar_clinica(cliente, lojas[1])
    dar_email(engine_dono, lenta.maria, 'lenta@example.com')
    dar_email(engine_dono, rapida.maria, 'rapida@example.com')
    configurar(engine_dono, lenta.lt.loja.id, '127.0.0.1', porta)
    ligar_smtp(engine_dono, rapida.lt.loja.id)
    for hora in ('08:00', '09:00', '10:00'):
        criar_no_painel(cliente, lenta, inicio=f'{SEGUNDA}T{hora}')
    criar_no_painel(cliente, rapida)

    real, falso = EnvioSmtp(prazo=3), EnvioFalso()
    momentos: dict[str, float] = {}
    inicio = time.monotonic()

    class PorServidor:
        def enviar(self, config, email):
            try:
                if config.servidor == '127.0.0.1':
                    real.enviar(config, email)
                else:
                    falso.enviar(config, email)
            finally:
                momentos.setdefault(email.destino, time.monotonic() - inicio)

    ciclo = processar(envio=PorServidor())
    assert momentos['rapida@example.com'] < 2  # atendida em paralelo, sem esperar a lenta
    assert 2.5 < momentos['lenta@example.com'] < 5  # o prazo total do envio
    assert len(conexoes) == 1  # parou na primeira falha de conexão: os outros dois nem foram tentados
    assert (ciclo.enviados, ciclo.falhas) == (1, 1)
    linhas = {
        (linha['email_tentativas'], linha['status_email'], linha['email_erro']) for linha in fila(engine_dono)
    }
    # A que falhou gastou 1 tentativa; as duas devolvidas voltam sem gastar; a da loja rápida saiu
    assert sorted(linhas) == sorted({(1, 1, MSG_DEMOROU), (0, 1, None), (1, 2, None)})
    assert [linha['email_tentativas'] for linha in fila(engine_dono)].count(0) == 2


def test_orcamento_da_loja_devolve_o_resto_para_o_proximo_ciclo(cliente, clinica, engine_dono, monkeypatch):
    monkeypatch.setattr(tarefa_notificacoes, 'ORCAMENTO_LOJA', 0.5)
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    for hora in ('08:00', '09:00', '10:00', '11:00', '13:00'):
        criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T{hora}')

    class Lento:  # cada envio no pior caso permitido pelo orçamento de teste
        enviados = 0

        def enviar(self, config, email):
            time.sleep(0.3)
            Lento.enviados += 1

    ciclo = processar(envio=Lento())
    assert ciclo.enviados == 2  # 0,3 s + 0,3 s passou do orçamento de 0,5 s
    tentativas = sorted((linha['status_email'], linha['email_tentativas']) for linha in fila(engine_dono))
    assert tentativas == [(1, 0), (1, 0), (1, 0), (2, 1), (2, 1)]
    assert processar(envio=Lento()).enviados == 2  # voltaram para a fila na hora


def test_reserva_cobre_o_pior_caso_de_uma_loja():
    assert timedelta(seconds=ORCAMENTO_LOJA + 2 * PRAZO_ENVIO) < RESERVA


def test_testar_email_com_servidor_gotejando_responde_no_prazo(
    cliente, clinica, engine_dono, smtp_lento, monkeypatch
):
    porta, _ = smtp_lento
    configurar(engine_dono, clinica.lt.loja.id, '127.0.0.1', porta)
    monkeypatch.setattr(envio_email, 'FALSO', EnvioSmtp(prazo=2))
    inicio = time.monotonic()
    resposta = cliente.post(
        f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=clinica.lt.h_admin
    )
    assert time.monotonic() - inicio < 5
    assert resposta.json() == {'enviado': False, 'erro': MSG_DEMOROU}


def test_servidor_que_recusa_a_conexao_falha_rapido():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        porta = sock.getsockname()[1]
    with pytest.raises(FalhaEnvio) as erro:
        EnvioSmtp().enviar(config_lenta(porta), Email('maria@example.com', 'Oi', 'Corpo'))
    assert (erro.value.mensagem, erro.value.conexao) == (MSG_CONECTAR, True)


# --- A3: relógio da reserva e token conferido ---------------------------------------------------------


def test_reserva_usa_o_relogio_da_hora_da_reserva(cliente, clinica, engine_dono):
    """O processo 1 começou o ciclo em t, mas só reservou a loja 12 min depois (o pior caso de lojas lentas
    antes dela). Outro processo, em t + 12 min 30 s, não pode achar a reserva vencida."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    t = datetime.now(UTC) + timedelta(seconds=1)
    enviados: list[str] = []

    class Processo2:
        def enviar(self, config, email):
            enviados.append('P2')

    class Processo1:
        def enviar(self, config, email):
            depois = t + timedelta(minutes=12, seconds=30)
            processar(agora=depois, relogio=lambda: depois, envio=Processo2(), despachante=Despachante())
            enviados.append('P1')

    processar(agora=t, relogio=lambda: t + timedelta(minutes=12), envio=Processo1())
    assert enviados == ['P1']
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas']) == (2, 1)


def test_resultado_de_reserva_vencida_nao_sobrescreve_o_do_outro_processo(cliente, clinica, engine_dono):
    """Se a reserva venceu (processo congelado) e outro processo enviou, o resultado atrasado do primeiro
    não mexe na linha (token: tentativa + data da reserva)."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    t = datetime.now(UTC) + timedelta(seconds=1)
    depois = t + RESERVA + timedelta(minutes=1)
    outro = EnvioFalso()

    class Congelado:
        def enviar(self, config, email):
            # Outro processo (outro despachante), quando a reserva já venceu
            processar(agora=depois, relogio=lambda: depois, envio=outro, despachante=Despachante())
            raise FalhaEnvio(MSG_CONECTAR)

    processar(agora=t, relogio=lambda: t, envio=Congelado())
    assert len(outro.enviados) == 1
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas'], linha['email_erro']) == (2, 2, None)


# --- A4: trocar servidor ou usuário exige a senha de novo ----------------------------------------------


MSG_SENHA_DE_NOVO = 'Informe a senha de novo ao trocar o servidor ou o usuário.'


def test_trocar_servidor_ou_usuario_exige_a_senha(cliente, clinica, engine_dono, monkeypatch):
    h = clinica.lt.h_admin
    assert salvar(cliente, h, **SMTP_COMPLETO).status_code == 200
    sem_senha = {k: v for k, v in SMTP_COMPLETO.items() if k != 'senha'}
    for troca in ({'servidor': 'smtp.outro.example'}, {'usuario': 'outra@loja.com'}, {'usuario': None}):
        assert erros(salvar(cliente, h, **{**sem_senha, **troca})) == {'email.senha': MSG_SENHA_DE_NOVO}, (
            troca
        )
    # O teste de envio continua indo para o servidor salvo, com a senha salva
    falso = EnvioFalso()
    monkeypatch.setattr(envio_email, 'FALSO', falso)
    cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=h)
    assert falso.enviados[0][0].servidor == 'smtp.exemplo.com'
    # Mudar o resto mantém a senha; trocar mandando a senha (ou apagando-a) é aceito
    assert salvar(cliente, h, **{**sem_senha, 'porta': 465, 'seguranca': 'ssl'}).json()['email'][
        'senha_definida'
    ]
    trocado = salvar(cliente, h, **{**SMTP_COMPLETO, 'servidor': 'smtp.outro.example', 'senha': 'nova-senha'})
    assert trocado.status_code == 200
    apagado = salvar(cliente, h, **{**sem_senha, 'servidor': 'smtp.terceiro.example', 'senha': None})
    assert apagado.json()['email']['senha_definida'] is False
    # Sem senha salva, trocar o servidor não pede nada
    assert salvar(cliente, h, **{**sem_senha, 'servidor': 'smtp.quarto.example'}).status_code == 200


# --- A5: avisos vencidos ---------------------------------------------------------------------------------


def _lembrete_pendente(cliente, clinica, engine_dono) -> dict:
    """Agendamento às 9h com um lembrete criado e com o e-mail pendente (o primeiro envio falhou)."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    ag = criar_no_painel(cliente, clinica)
    processar(envio=EnvioFalso())  # o "agendamento_criado" sai
    falho = EnvioFalso(falhas=[FalhaEnvio('Temporária.')])
    agora = NOVE - timedelta(minutes=100)
    processar(agora=agora, envio=falho)
    [lembrete] = avisos(engine_dono, evento='lembrete')
    assert (lembrete['status_email'], lembrete['email_erro']) == (1, 'Temporária.')
    return ag


@pytest.mark.parametrize('mudanca', ['cancelar', 'remarcar', 'excluir'])
def test_lembrete_pendente_nao_sai_se_o_agendamento_mudou(cliente, clinica, engine_dono, mudanca):
    ag = _lembrete_pendente(cliente, clinica, engine_dono)
    h = clinica.lt.h_admin
    if mudanca == 'cancelar':
        assert mudar(cliente, clinica, ag['id'], 'cancelado', 'Doença').status_code == 200
    elif mudanca == 'remarcar':
        resposta = cliente.put(
            f'/api/loja/agendamentos/{ag["id"]}', json=clinica.dados(inicio=f'{SEGUNDA}T11:00'), headers=h
        )
        assert resposta.status_code == 200
    else:
        assert cliente.delete(f'/api/loja/agendamentos/{ag["id"]}', headers=h).status_code == 204
    falso = EnvioFalso()
    agora = NOVE - timedelta(minutes=90)
    processar(agora=agora, envio=falso)
    assert not any('Lembrete' in email.assunto for _, email in falso.enviados)
    [lembrete] = avisos(engine_dono, evento='lembrete')
    assert (lembrete['status_email'], lembrete['email_erro']) == (3, MSG_LEMBRETE_VENCIDO)


def test_lembrete_pendente_nao_sai_depois_do_inicio(cliente, clinica, engine_dono):
    _lembrete_pendente(cliente, clinica, engine_dono)
    falso = EnvioFalso()
    agora = NOVE + timedelta(minutes=1)
    processar(agora=agora, envio=falso)
    assert falso.enviados == []
    [lembrete] = avisos(engine_dono, evento='lembrete')
    assert (lembrete['status_email'], lembrete['email_erro']) == (3, MSG_LEMBRETE_VENCIDO)


def test_lembrete_pendente_do_mesmo_horario_ainda_sai(cliente, clinica, engine_dono):
    _lembrete_pendente(cliente, clinica, engine_dono)
    falso = EnvioFalso()
    agora = NOVE - timedelta(minutes=90)
    processar(agora=agora, envio=falso)
    assert [email.assunto for _, email in falso.enviados] == ['Lembrete do seu horário · Loja loja-a']


def test_aviso_com_mais_de_24h_ou_de_agendamento_ja_comecado_vence(cliente, clinica, engine_dono):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    velho = criar_no_painel(cliente, clinica)
    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T10:00')
    with engine_dono.begin() as conexao:
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text("UPDATE notificacoes SET criado_em = now() - interval '25 hours' WHERE agendamento_id = :a"),
            {'a': velho['id']},
        )
    falso = EnvioFalso()
    processar(envio=falso)
    assert len(falso.enviados) == 1
    assert {(a['status_email'], a['email_erro']) for a in avisos(engine_dono)} == {
        (3, MSG_VENCIDO),
        (2, None),
    }

    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T11:00')
    depois = NOVE + timedelta(hours=3)  # o agendamento das 11h já começou
    processar(agora=depois, envio=falso)
    assert len(falso.enviados) == 1
    assert avisos(engine_dono)[-1]['email_erro'] == MSG_VENCIDO


# --- Sugestões aplicadas --------------------------------------------------------------------------------


def test_head_nao_marca_os_avisos(cliente, clinica, engine_dono, navegador):
    nav = navegador()
    criar_conta(nav, engine_dono)
    criar_no_painel(cliente, clinica)
    assert nav.head(f'{LOJA}/conta/avisos').status_code == 200
    assert [a['status_site'] for a in avisos(engine_dono, tipo='cliente')] == [1]
    nav.get(f'{LOJA}/conta/avisos')
    assert [a['status_site'] for a in avisos(engine_dono, tipo='cliente')] == [2]


def test_funcao_security_definer_so_para_a_aplicacao(engine_dono, engine_app):
    with engine_dono.connect() as conexao:
        acl = conexao.execute(
            text("SELECT proacl::text FROM pg_proc WHERE proname = 'notificacoes_lojas_com_trabalho'")
        ).scalar()
        publico = conexao.execute(
            text(
                "SELECT has_function_privilege('public', 'notificacoes_lojas_com_trabalho(timestamptz)', 'EXECUTE')"
            )
        ).scalar()
    assert acl is not None
    assert '{=X/' not in acl
    assert ',=X/' not in acl
    assert publico is False
    with engine_app.connect() as conexao:  # o papel da aplicação continua executando
        conexao.execute(text('SELECT notificacoes_lojas_com_trabalho(now())')).all()


@pytest.mark.parametrize(
    ('endereco', 'publico'),
    [
        ('64:ff9b::7f00:1', False),  # NAT64 para 127.0.0.1
        ('64:ff9b::a00:5', False),  # NAT64 para 10.0.0.5
        ('64:ff9b::808:808', True),  # NAT64 para 8.8.8.8
        ('::ffff:10.0.0.1', False),  # IPv4 mapeado
        ('::127.0.0.1', False),  # IPv4-compatível
        ('2002:7f00:1::1', False),  # 6to4 de 127.0.0.1
        ('2002:808:808::1', False),  # 6to4: o Python não considera 2002::/16 global (recusa conservadora)
        ('8.8.8.8', True),
        ('169.254.169.254', False),
        ('2001:4860:4860::8888', True),
    ],
)
def test_ipv4_embutido_em_ipv6_e_conferido(endereco, publico):
    assert _publico(endereco) is publico


def test_email_com_acento_sem_smtputf8_tem_mensagem_propria(monkeypatch):
    import smtplib

    class SemUtf8(smtplib.SMTP):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def connect(self, host='localhost', port=0, source_address=None):
            return (220, b'ok')

        def starttls(self, *args, **kwargs):
            return (220, b'ok')

        def send_message(self, *args, **kwargs):
            raise smtplib.SMTPNotSupportedError('sem SMTPUTF8')

        def quit(self):
            return (221, b'ok')

    monkeypatch.setattr(envio_email, '_SmtpConferido', SemUtf8)
    with pytest.raises(FalhaEnvio) as erro:
        EnvioSmtp().enviar(config_lenta(25), Email('joão@exemplo.com.br', 'Oi', 'Corpo'))
    assert (erro.value.mensagem, erro.value.definitiva) == (MSG_ACENTOS, True)


def test_dns_do_servidor_e_consultado_fora_da_transacao(cliente, clinica, engine_dono, monkeypatch):
    conexoes_abertas: list[int] = []

    def conferir(servidor, porta):
        conexoes_abertas.append(get_engine().pool.checkedout())
        return True

    monkeypatch.setattr(config_notificacoes, 'servidor_permitido', conferir)
    assert salvar(cliente, clinica.lt.h_admin, **SMTP_COMPLETO).status_code == 200
    assert conexoes_abertas == [0]  # nenhuma conexão do banco presa durante o DNS
    # Sem login não consulta nada
    resposta = cliente.put(URL, json={'antecedencia_cliente_minutos': 1, 'email': SMTP_COMPLETO})
    assert resposta.status_code == 401
    assert conexoes_abertas == [0]
    # Sem escrita em config_loja (leitura, ou sem acesso) também não consulta: a rota responde 403
    for acesso in ({'config_loja': 'leitura'}, {'clientes': 'escrita'}):
        resposta = salvar(cliente, usuario_com(engine_dono, clinica.lt.loja, acesso), **SMTP_COMPLETO)
        assert resposta.status_code == 403
    assert conexoes_abertas == [0]
