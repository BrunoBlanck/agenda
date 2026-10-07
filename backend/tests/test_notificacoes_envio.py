"""Tarefa de fundo (NOT-04, NOT-05, NOT-07), envio de e-mail e Configurações › Avisos e e-mail (CFG-05/06).

``processar`` recebe o ``agora`` e o provedor de e-mail: os testes andam no tempo sem esperar e nada sai
para a rede (``EnvioFalso``).
"""

import socket
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text

from app.config import get_settings
from app.models import Agendamento, Auditoria, Cliente
from app.models.enums import StatusAgendamento, StatusLoja
from app.services import envio_email
from app.services.auditoria import mudancas
from app.services.cifra import decifrar
from app.services.envio_email import (
    MSG_CONECTAR,
    MSG_LOGIN,
    MSG_SENHA_ILEGIVEL,
    MSG_SERVIDOR_NAO_PERMITIDO,
    ConfigSmtp,
    Email,
    EnvioFalso,
    EnvioSmtp,
    FalhaEnvio,
    montar_mensagem,
)
from app.services.notificacoes import MSG_SEM_SMTP
from app.services.tarefa_notificacoes import Despachante, processar
from tests.clinica import SEGUNDA
from tests.fabricas import inserir, sessao, usuario_com
from tests.test_notificacoes import avisos, criar_no_painel, dar_email, ligar_smtp, pedir_pelo_site

S = StatusAgendamento
URL = '/api/loja/configuracoes/notificacoes'
NOVE = datetime.fromisoformat(f'{SEGUNDA}T09:00:00-03:00')


@pytest.fixture
def falso(monkeypatch) -> EnvioFalso:
    """O provedor do ambiente de teste, zerado a cada teste."""
    novo = EnvioFalso()
    monkeypatch.setattr(envio_email, 'FALSO', novo)
    return novo


def marcar(engine, clinica, inicio: datetime, situacao=S.confirmado, **extra) -> Agendamento:
    lt = clinica.lt
    return inserir(
        engine,
        Agendamento(
            loja_id=lt.loja.id,
            cliente_id=extra.pop('cliente_id', clinica.maria),
            servico_id=clinica.limpeza,
            funcionario_id=lt.prof.id,
            local_id=clinica.sala1,
            inicio=inicio,
            fim=inicio + timedelta(hours=1),
            status=situacao,
            **extra,
        ),
    )


def antecedencia(engine, loja_id, minutos: int) -> None:
    with engine.begin() as conexao:
        conexao.execute(
            text('UPDATE loja_configuracoes SET antecedencia_cliente_minutos = :m WHERE loja_id = :l'),
            {'m': minutos, 'l': loja_id},
        )


def fila(engine) -> list[dict]:
    with engine.connect() as conexao:
        return [
            dict(linha)
            for linha in conexao.execute(
                text(
                    'SELECT id, evento, status_email, email_tentativas, email_erro, email_proxima_tentativa_em,'
                    ' email_enviado_em FROM notificacoes ORDER BY criado_em, id'
                )
            ).mappings()
        ]


# --- Envio dos e-mails (NOT-04, NOT-07) ----------------------------------------------------------------


def test_envio_com_sucesso(cliente, clinica, engine_dono, falso):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    ciclo = processar(envio=falso)
    assert (ciclo.lojas, ciclo.enviados, ciclo.falhas) == (1, 1, 0)
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas'], linha['email_erro']) == (2, 1, None)
    assert linha['email_enviado_em'] is not None
    assert linha['email_proxima_tentativa_em'] is None
    [(config, email)] = falso.enviados
    assert (config.servidor, config.porta, config.seguranca, config.senha) == (
        'smtp.exemplo.com',
        587,
        'starttls',
        None,
    )
    assert email.destino == 'maria@example.com'
    assert email.assunto == 'Horário agendado · Loja loja-a'
    assert email.corpo.startswith(
        'Loja loja-a agendou Limpeza para seg 07/01 às 9h com Profissional (Sala 1).'
    )
    # Nada mais a fazer: o ciclo seguinte não encontra a loja
    assert processar(envio=falso).lojas == 0


def test_falha_temporaria_tenta_tres_vezes_com_espera_crescente(cliente, clinica, engine_dono, falso):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    falso.falhas = [FalhaEnvio(MSG_CONECTAR) for _ in range(3)]
    agora = datetime.now(UTC) + timedelta(seconds=1)

    processar(agora=agora, relogio=lambda: agora, envio=falso)
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas'], linha['email_erro']) == (1, 1, MSG_CONECTAR)
    assert linha['email_proxima_tentativa_em'] == agora + timedelta(minutes=1)
    assert (
        processar(
            agora=agora + timedelta(seconds=59), relogio=lambda: agora + timedelta(seconds=59), envio=falso
        ).lojas
        == 0
    )  # ainda esperando

    processar(agora=agora + timedelta(minutes=1), relogio=lambda: agora + timedelta(minutes=1), envio=falso)
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas']) == (1, 2)
    assert linha['email_proxima_tentativa_em'] == agora + timedelta(minutes=6)

    processar(agora=agora + timedelta(minutes=6), relogio=lambda: agora + timedelta(minutes=6), envio=falso)
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas'], linha['email_erro']) == (3, 3, MSG_CONECTAR)
    assert linha['email_proxima_tentativa_em'] is None
    assert falso.enviados == []
    assert (
        processar(
            agora=agora + timedelta(hours=1), relogio=lambda: agora + timedelta(hours=1), envio=falso
        ).lojas
        == 0
    )


def test_falha_definitiva_encerra_na_hora(cliente, clinica, engine_dono, falso):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    falso.falhas = [FalhaEnvio(MSG_LOGIN, definitiva=True)]
    processar(envio=falso)
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas'], linha['email_erro']) == (3, 1, MSG_LOGIN)


def test_loja_que_desligou_o_smtp_ou_senha_ilegivel_encerra_com_erro(cliente, clinica, engine_dono, falso):
    loja_id = clinica.lt.loja.id
    ligar_smtp(engine_dono, loja_id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T10:00')
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE loja_configuracoes SET smtp_ativo = false WHERE loja_id = :l'), {'l': loja_id}
        )
    processar(envio=falso)
    assert {(linha['status_email'], linha['email_erro']) for linha in fila(engine_dono)} == {
        (3, MSG_SEM_SMTP)
    }

    ligar_smtp(engine_dono, loja_id)
    with engine_dono.begin() as conexao:
        conexao.execute(
            text("UPDATE loja_configuracoes SET smtp_senha_cifrada = 'nao-abre' WHERE loja_id = :l"),
            {'l': loja_id},
        )
    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T11:00')
    processar(envio=falso)
    assert fila(engine_dono)[-1]['status_email'] == 3
    assert fila(engine_dono)[-1]['email_erro'] == MSG_SENHA_ILEGIVEL
    assert falso.enviados == []


def test_reserva_vencida_volta_para_a_fila(cliente, clinica, engine_dono, falso):
    """O processo morreu no meio do envio: a linha volta quando a reserva vence (5 min)."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)

    class Quebra:
        def enviar(self, config, email):
            raise RuntimeError('processo morreu')

    agora = datetime.now(UTC) + timedelta(seconds=1)
    processar(agora=agora, relogio=lambda: agora, envio=Quebra())
    [linha] = fila(engine_dono)
    assert (linha['status_email'], linha['email_tentativas']) == (1, 1)
    assert linha['email_proxima_tentativa_em'] == agora + timedelta(minutes=5)
    processar(agora=agora + timedelta(minutes=4), relogio=lambda: agora + timedelta(minutes=4), envio=falso)
    assert falso.enviados == []
    processar(agora=agora + timedelta(minutes=5), relogio=lambda: agora + timedelta(minutes=5), envio=falso)
    assert len(falso.enviados) == 1
    assert fila(engine_dono)[0]['status_email'] == 2


def test_dois_processos_nao_enviam_o_mesmo_email(cliente, clinica, engine_dono):
    """SKIP LOCKED + reserva: cada e-mail sai uma vez, mesmo com dois ciclos ao mesmo tempo."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    for hora in ('08:00', '09:00', '10:00', '11:00', '13:00', '14:00'):
        criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T{hora}')
    enviados: list[str] = []
    trava = threading.Lock()

    class Lento:
        def enviar(self, config, email):
            time.sleep(0.2)
            with trava:
                enviados.append(email.corpo)

    barreira = threading.Barrier(2)
    erros: list[BaseException] = []

    def rodar():
        try:
            barreira.wait()
            processar(envio=Lento(), lote=4, despachante=Despachante())  # cada thread, um processo
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=rodar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert erros == []
    assert len(enviados) == 6
    assert len(set(enviados)) == 6
    assert {linha['status_email'] for linha in fila(engine_dono)} == {2}
    assert {linha['email_tentativas'] for linha in fila(engine_dono)} == {1}


def test_outro_processo_durante_o_envio_nao_pega_os_reservados(cliente, clinica, engine_dono):
    """Um ciclo que começa enquanto outro ainda envia (reserva já gravada) não manda os mesmos e-mails."""
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    for hora in ('08:00', '09:00', '10:00'):
        criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T{hora}')
    enviados: list[str] = []
    enviando, segundo_terminou = threading.Event(), threading.Event()

    class Primeiro:
        def enviar(self, config, email):
            enviando.set()
            segundo_terminou.wait(10)  # o segundo ciclo roda inteiro durante este envio
            enviados.append(email.corpo)

    class Segundo:
        def enviar(self, config, email):
            enviados.append(email.corpo)

    primeiro = threading.Thread(target=processar, kwargs={'envio': Primeiro()})
    primeiro.start()
    assert enviando.wait(10)
    try:
        assert processar(envio=Segundo(), despachante=Despachante()).enviados == 0  # outro processo
    finally:
        segundo_terminou.set()
        primeiro.join()
    assert len(enviados) == 3
    assert len(set(enviados)) == 3


# --- Lembrete (NOT-05) ------------------------------------------------------------------------------


def lembretes(engine) -> list[dict]:
    return avisos(engine, evento='lembrete')


def test_lembrete_dentro_da_janela_uma_vez_so(clinica, engine_dono, falso):
    ag = marcar(engine_dono, clinica, NOVE)
    assert processar(agora=NOVE - timedelta(minutes=121), envio=falso).lembretes == 0  # antes da janela
    assert lembretes(engine_dono) == []
    assert processar(agora=NOVE - timedelta(minutes=120), envio=falso).lembretes == 1  # encostado
    assert processar(agora=NOVE - timedelta(minutes=30), envio=falso).lembretes == 0  # já lembrado
    [aviso] = lembretes(engine_dono)
    assert aviso['agendamento_id'] == ag.id
    assert str(aviso['cliente_id']) == clinica.maria
    assert aviso['titulo'] == 'Lembrete do seu horário'
    assert aviso['mensagem'] == (
        'Seu horário de Limpeza é seg 07/01 às 9h com Profissional (Sala 1). Loja loja-a espera por você.'
    )
    assert (aviso['status_email'], aviso['status_whatsapp']) == (4, 4)


def test_lembrete_no_inicio_ou_depois_nao_sai(clinica, engine_dono, falso):
    marcar(engine_dono, clinica, NOVE)
    assert processar(agora=NOVE, envio=falso).lembretes == 0
    assert processar(agora=NOVE + timedelta(minutes=5), envio=falso).lembretes == 0


@pytest.mark.parametrize(
    ('situacao', 'motivo'),
    [(S.pendente, None), (S.cancelado, 'x'), (S.concluido, None), (S.nao_compareceu, None)],
)
def test_lembrete_so_para_agendado_ou_confirmado(clinica, engine_dono, falso, situacao, motivo):
    marcar(engine_dono, clinica, NOVE, situacao=situacao, motivo_cancelamento=motivo)
    assert processar(agora=NOVE - timedelta(minutes=60), envio=falso).lembretes == 0


def test_agendado_tambem_recebe_e_remarcacao_gera_outro(clinica, engine_dono, falso):
    ag = marcar(engine_dono, clinica, NOVE, situacao=S.agendado)
    assert processar(agora=NOVE - timedelta(minutes=60), envio=falso).lembretes == 1
    with engine_dono.begin() as conexao:  # a loja remarcou para 10h
        conexao.execute(
            text(
                "UPDATE agendamentos SET inicio = inicio + interval '1 hour', fim = fim + interval '1 hour' WHERE id = :a"
            ),
            {'a': ag.id},
        )
    assert processar(agora=NOVE - timedelta(minutes=30), envio=falso).lembretes == 1
    assert [a['mensagem'].split(' com ')[0] for a in lembretes(engine_dono)] == [
        'Seu horário de Limpeza é seg 07/01 às 9h',
        'Seu horário de Limpeza é seg 07/01 às 10h',
    ]


def test_antecedencia_da_loja_e_zero_desliga(clinica, engine_dono, falso):
    marcar(engine_dono, clinica, NOVE)
    antecedencia(engine_dono, clinica.lt.loja.id, 180)
    assert processar(agora=NOVE - timedelta(minutes=181), envio=falso).lembretes == 0
    assert processar(agora=NOVE - timedelta(minutes=180), envio=falso).lembretes == 1
    marcar(engine_dono, clinica, NOVE + timedelta(hours=2))
    antecedencia(engine_dono, clinica.lt.loja.id, 0)
    assert processar(agora=NOVE + timedelta(minutes=119), envio=falso).lembretes == 0


def test_lembrete_com_email_sai_no_mesmo_ciclo_e_loja_suspensa_fica_parada(clinica, engine_dono, falso):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    marcar(engine_dono, clinica, NOVE)
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET status = 'suspensa' WHERE id = :l"), {'l': clinica.lt.loja.id})
    assert processar(agora=NOVE - timedelta(minutes=60), envio=falso).lojas == 0
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE lojas SET status = :s WHERE id = :l'),
            {'s': StatusLoja.ativa.value, 'l': clinica.lt.loja.id},
        )
    ciclo = processar(agora=NOVE - timedelta(minutes=60), envio=falso)
    assert (ciclo.lembretes, ciclo.enviados) == (1, 1)
    assert lembretes(engine_dono)[0]['status_email'] == 2


def test_lembretes_de_duas_lojas_ficam_cada_um_na_sua(cliente, clinica, lojas, engine_dono, falso):
    marcar(engine_dono, clinica, NOVE)
    loja_b = lojas[1]
    cliente_b = inserir(
        engine_dono, Cliente(loja_id=loja_b.loja.id, nome='Bia', sobrenome='B', telefone='(11) 90000-0000')
    )
    inserir(
        engine_dono,
        Agendamento(
            loja_id=loja_b.loja.id,
            cliente_id=cliente_b.id,
            funcionario_id=loja_b.prof.id,
            inicio=NOVE,
            fim=NOVE + timedelta(hours=1),
            status=S.confirmado,
        ),
    )
    ciclo = processar(agora=NOVE - timedelta(minutes=60), envio=falso)
    assert (ciclo.lojas, ciclo.lembretes) == (2, 2)
    assert {(a['loja_id'], a['cliente_id']) for a in lembretes(engine_dono)} == {
        (clinica.lt.loja.id, UUID(clinica.maria)),
        (loja_b.loja.id, cliente_b.id),
    }
    # O agendamento da loja B não tem serviço: a mensagem usa "Atendimento" e o nome da loja B
    [da_b] = [a for a in lembretes(engine_dono) if a['loja_id'] == loja_b.loja.id]
    assert (
        da_b['mensagem']
        == 'Seu horário de Atendimento é seg 07/01 às 9h com Profissional. Loja loja-b espera por você.'
    )


# --- E-mail: mensagem e SMTP real -----------------------------------------------------------------------

CONFIG = ConfigSmtp(
    servidor='127.0.0.1',
    porta=1,
    seguranca='starttls',
    usuario=None,
    senha=None,
    remetente_email='avisos@loja.com',
    remetente_nome='Loja\r\nBcc: x@y.com',
)


def test_mensagem_sem_quebra_nos_cabecalhos():
    mensagem = montar_mensagem(CONFIG, Email('maria@example.com', 'Oi\r\nBcc: ataque@x.com', 'Corpo'))
    assert mensagem['Subject'] == 'Oi Bcc: ataque@x.com'
    assert mensagem['Bcc'] is None
    assert '\n' not in mensagem['From']
    assert mensagem['From'].endswith('<avisos@loja.com>')
    assert mensagem['To'] == 'maria@example.com'
    assert mensagem.get_content_type() == 'text/plain'


def _porta_fechada() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def test_smtp_real_sem_servidor_e_falha_temporaria():
    config = replace(CONFIG, porta=_porta_fechada())
    with pytest.raises(FalhaEnvio) as erro:
        EnvioSmtp().enviar(config, Email('maria@example.com', 'Oi', 'Corpo'))
    assert (erro.value.mensagem, erro.value.definitiva) == (MSG_CONECTAR, False)


def test_smtp_real_em_producao_recusa_endereco_interno(monkeypatch):
    monkeypatch.setattr(get_settings(), 'ambiente', 'producao')
    for servidor in ('127.0.0.1', '10.0.0.5', '169.254.169.254', '::1', 'localhost'):
        config = replace(CONFIG, servidor=servidor, porta=587)
        with pytest.raises(FalhaEnvio) as erro:
            EnvioSmtp().enviar(config, Email('maria@example.com', 'Oi', 'Corpo'))
        assert (erro.value.mensagem, erro.value.definitiva) == (MSG_SERVIDOR_NAO_PERMITIDO, True), servidor


def test_corpo_do_email_ao_cliente_so_leva_ao_site(cliente, clinica, engine_dono, falso, monkeypatch):
    """NOT-08 e DIR-003: com URL_PUBLICA, o link é o de Minha conta do site; nunca o painel."""
    monkeypatch.setattr(get_settings(), 'url_publica', 'https://agenda.exemplo.com')
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    pedir_pelo_site(cliente, clinica)  # cliente (Ana) e profissional
    processar(envio=falso)
    corpos = {email.destino: email.corpo for _, email in falso.enviados}
    assert set(corpos) == {'maria@example.com', 'ana@example.com', 'prof@loja-a.com'}
    for destino in ('maria@example.com', 'ana@example.com'):
        assert 'Veja os seus horários: https://agenda.exemplo.com/loja-a/conta' in corpos[destino]
    assert 'https://' not in corpos['prof@loja-a.com']
    for corpo in corpos.values():
        for proibido in ('painel', 'superadmin', 'login'):
            assert proibido not in corpo.lower()


# --- Configurações › Avisos e e-mail (CFG-05, CFG-06) ---------------------------------------------------

SMTP_COMPLETO = {
    'ativo': True,
    'servidor': 'smtp.exemplo.com',
    'porta': 587,
    'seguranca': 'starttls',
    'usuario': 'avisos@loja.com',
    'senha': 'segredo-123',
    'remetente_email': 'avisos@loja.com',
    'remetente_nome': 'Clínica A',
}


def salvar(cliente, headers, antecedencia_min=120, **email):
    return cliente.put(
        URL, json={'antecedencia_cliente_minutos': antecedencia_min, 'email': email}, headers=headers
    )


def erros(resposta) -> dict[str, str]:
    assert resposta.status_code == 422, resposta.json()
    return {e['campo']: e['mensagem'] for e in resposta.json()['erros']}


def test_configuracao_padrao(cliente, clinica):
    resposta = cliente.get(URL, headers=clinica.lt.h_admin)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo['antecedencia_cliente_minutos'] == 120
    assert corpo['email'] == {
        'ativo': False,
        'servidor': None,
        'porta': None,
        'seguranca': None,
        'usuario': None,
        'senha_definida': False,
        'remetente_email': None,
        'remetente_nome': None,
    }
    assert corpo['whatsapp_disponivel'] is False
    assert {'atualizado_em', 'atualizado_por', 'atualizado_por_nome'} <= set(corpo)


def test_salvar_cifra_a_senha_e_ela_nunca_volta(cliente, clinica, engine_dono):
    h = clinica.lt.h_admin
    resposta = salvar(cliente, h, 90, **SMTP_COMPLETO)
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo['antecedencia_cliente_minutos'] == 90
    assert corpo['email']['senha_definida'] is True
    assert 'senha' not in corpo['email']
    assert 'segredo-123' not in resposta.text
    assert corpo['atualizado_por'] == str(clinica.lt.admin.id)
    assert corpo['atualizado_por_nome'] == 'Admin'
    assert 'segredo-123' not in cliente.get(URL, headers=h).text
    with engine_dono.connect() as conexao:
        cifrada = conexao.execute(
            text('SELECT smtp_senha_cifrada FROM loja_configuracoes WHERE loja_id = :l'),
            {'l': clinica.lt.loja.id},
        ).scalar()
        auditoria = conexao.execute(
            text(
                "SELECT antes::text, depois::text, campos_alterados FROM auditoria WHERE tabela = 'loja_configuracoes'"
                " AND operacao = 'alterar' ORDER BY id DESC LIMIT 1"
            )
        ).one()
    assert 'segredo' not in cifrada
    assert decifrar(cifrada) == 'segredo-123'
    assert 'smtp_senha_cifrada' not in auditoria[0]
    assert 'smtp_senha_cifrada' not in auditoria[1]
    assert cifrada not in auditoria[1]
    assert 'smtp_senha_cifrada' in auditoria[2]

    sem_senha = {k: v for k, v in SMTP_COMPLETO.items() if k != 'senha'}  # ausente = mantém
    assert salvar(cliente, h, **sem_senha).json()['email']['senha_definida'] is True
    with engine_dono.connect() as conexao:
        assert (
            conexao.execute(
                text('SELECT smtp_senha_cifrada FROM loja_configuracoes WHERE loja_id = :l'),
                {'l': clinica.lt.loja.id},
            ).scalar()
            == cifrada
        )
    assert salvar(cliente, h, **{**sem_senha, 'senha': None}).json()['email']['senha_definida'] is False


def test_historico_mostra_a_senha_do_email_oculta(cliente, clinica, engine_dono):
    salvar(cliente, clinica.lt.h_admin, **SMTP_COMPLETO)
    with sessao(engine_dono) as db:
        registro = db.scalars(
            select(Auditoria).where(Auditoria.tabela == 'loja_configuracoes').order_by(Auditoria.id.desc())
        ).first()
        senha = [m for m in mudancas(registro) if m.campo == 'senha do e-mail']
    assert [(m.antes, m.depois) for m in senha] == [('••••••', 'alterada')]


def test_ativo_exige_os_campos(cliente, clinica):
    assert erros(salvar(cliente, clinica.lt.h_admin, ativo=True)) == {
        'email.servidor': 'Campo obrigatório para ativar o envio de e-mail.',
        'email.porta': 'Campo obrigatório para ativar o envio de e-mail.',
        'email.seguranca': 'Campo obrigatório para ativar o envio de e-mail.',
        'email.remetente_email': 'Campo obrigatório para ativar o envio de e-mail.',
    }
    # Desligado, pode ficar incompleto
    assert salvar(cliente, clinica.lt.h_admin, ativo=False, servidor='smtp.exemplo.com').status_code == 200


@pytest.mark.parametrize(
    ('campo', 'valor', 'mensagem'),
    [
        (
            'servidor',
            'http://smtp.exemplo.com',
            'Informe só o nome do servidor (ex.: smtp.exemplo.com), sem http:// nem porta.',
        ),
        (
            'servidor',
            'smtp.exemplo.com:587',
            'Informe só o nome do servidor (ex.: smtp.exemplo.com), sem http:// nem porta.',
        ),
        ('porta', 22, 'Use a porta 25, 465, 587 ou 2525.'),
        ('seguranca', 'nenhuma', 'Opção inválida.'),
        ('remetente_email', 'nao-e-email', 'E-mail inválido.'),
        ('remetente_nome', 'x' * 121, 'Texto muito longo (máximo de 120 caracteres).'),
        ('senha', '', 'Texto muito curto (mínimo de 1 caractere(s)).'),
    ],
)
def test_campos_do_smtp_invalidos(cliente, clinica, campo, valor, mensagem):
    assert erros(salvar(cliente, clinica.lt.h_admin, **{**SMTP_COMPLETO, campo: valor})) == {
        f'email.{campo}': mensagem
    }


@pytest.mark.parametrize('minutos', [-1, 10081, 'muito'])
def test_antecedencia_fora_da_faixa(cliente, clinica, minutos):
    assert set(erros(salvar(cliente, clinica.lt.h_admin, minutos, ativo=False))) == {
        'antecedencia_cliente_minutos'
    }


def test_corpo_sem_email_ou_sem_antecedencia(cliente, clinica):
    h = clinica.lt.h_admin
    assert set(erros(cliente.put(URL, json={'antecedencia_cliente_minutos': 60}, headers=h))) == {'email'}
    assert set(erros(cliente.put(URL, json={'email': {'ativo': False}}, headers=h))) == {
        'antecedencia_cliente_minutos'
    }


def test_em_producao_servidor_interno_e_recusado(cliente, clinica, monkeypatch):
    h = clinica.lt.h_admin
    monkeypatch.setattr(get_settings(), 'ambiente', 'producao')
    for servidor in ('127.0.0.1', '192.168.0.10', 'localhost', '[::1]'):
        assert erros(salvar(cliente, h, **{**SMTP_COMPLETO, 'servidor': servidor})) == {
            'email.servidor': 'Servidor não permitido.'
        }, servidor
    assert salvar(cliente, h, **{**SMTP_COMPLETO, 'servidor': '8.8.8.8'}).status_code == 200


def test_em_desenvolvimento_smtp_local_e_aceito(cliente, clinica):
    assert (
        salvar(cliente, clinica.lt.h_admin, **{**SMTP_COMPLETO, 'servidor': '127.0.0.1'}).status_code == 200
    )


def test_sem_chave_de_cifra_nao_guarda_senha(cliente, clinica, monkeypatch):
    monkeypatch.setattr(get_settings(), 'chave_cifra', None)
    h = clinica.lt.h_admin
    assert erros(salvar(cliente, h, **SMTP_COMPLETO)) == {
        'email.senha': 'O servidor não está configurado para guardar senhas de e-mail.'
    }
    sem_senha = {k: v for k, v in SMTP_COMPLETO.items() if k != 'senha'}
    assert salvar(cliente, h, **sem_senha).status_code == 200
    assert salvar(cliente, h, **{**sem_senha, 'senha': None}).status_code == 200


def test_chave_trocada_nao_abre_a_senha_antiga(cliente, clinica, monkeypatch):
    from cryptography.fernet import Fernet

    from app.services.cifra import SenhaIlegivel

    salvar(cliente, clinica.lt.h_admin, **SMTP_COMPLETO)
    monkeypatch.setattr(get_settings(), 'chave_cifra', SecretStr(Fernet.generate_key().decode()))
    resposta = cliente.post(
        f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=clinica.lt.h_admin
    )
    assert resposta.json() == {'enviado': False, 'erro': MSG_SENHA_ILEGIVEL}
    with pytest.raises(SenhaIlegivel):
        decifrar('qualquer')


def test_permissoes_e_isolamento(cliente, clinica, lojas, engine_dono):
    lt = clinica.lt
    leitura = usuario_com(engine_dono, lt.loja, {'config_loja': 'leitura'})
    nenhum = usuario_com(engine_dono, lt.loja, {'clientes': 'escrita'})
    assert cliente.get(URL, headers=leitura).status_code == 200
    for resposta in (
        salvar(cliente, leitura, **SMTP_COMPLETO),
        cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=leitura),
    ):
        assert resposta.status_code == 403
        assert resposta.json()['detail'] == 'Você só tem permissão de leitura aqui.'
    assert cliente.get(URL, headers=nenhum).status_code == 403
    # Loja B não vê nem é afetada pela configuração da loja A
    salvar(cliente, lt.h_admin, 30, **SMTP_COMPLETO)
    da_b = cliente.get(URL, headers=lojas[1].h_admin).json()
    assert (da_b['antecedencia_cliente_minutos'], da_b['email']['ativo'], da_b['email']['servidor']) == (
        120,
        False,
        None,
    )


# --- Enviar e-mail de teste (CFG-06) -------------------------------------------------------------------


def test_testar_sem_configuracao_e_409(cliente, clinica, falso):
    resposta = cliente.post(
        f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=clinica.lt.h_admin
    )
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'Configure e ative o envio de e-mail antes de testar.'
    assert falso.enviados == []


def test_testar_envia_com_a_configuracao_salva(cliente, clinica, falso):
    h = clinica.lt.h_admin
    salvar(cliente, h, **SMTP_COMPLETO)
    resposta = cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=h)
    assert resposta.status_code == 200
    assert resposta.json() == {'enviado': True}
    [(config, email)] = falso.enviados
    assert (config.servidor, config.usuario, config.senha) == (
        'smtp.exemplo.com',
        'avisos@loja.com',
        'segredo-123',
    )
    assert (email.destino, email.assunto) == ('eu@loja.com', 'E-mail de teste · Loja loja-a')

    falso.falhas = [FalhaEnvio(MSG_LOGIN, definitiva=True)]
    resposta = cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=h)
    assert resposta.json() == {'enviado': False, 'erro': MSG_LOGIN}
    assert 'segredo' not in resposta.text


def test_testar_destino_invalido_e_limite(cliente, clinica, falso):
    h = clinica.lt.h_admin
    salvar(cliente, h, **SMTP_COMPLETO)
    assert set(erros(cliente.post(f'{URL}/testar-email', json={'destino': 'x'}, headers=h))) == {'destino'}
    for _ in range(5):
        assert (
            cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=h).status_code == 200
        )
    resposta = cliente.post(f'{URL}/testar-email', json={'destino': 'eu@loja.com'}, headers=h)
    assert resposta.status_code == 429
    assert resposta.json()['detail'] == 'Muitos testes seguidos. Tente de novo em alguns minutos.'
    assert 'Retry-After' in resposta.headers
    assert len(falso.enviados) == 5
