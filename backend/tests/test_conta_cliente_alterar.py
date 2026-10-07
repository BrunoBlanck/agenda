"""Conta do cliente no site, Fase B (SIT-23, SIT-24, AGE-25, DIR-003): cancelar e remarcar pela conta.

Usa a loja de tests/clinica.py: Maria (11) 98888-1111 e João (11) 98888-2222; Limpeza (60 min, R$ 200,
Admin e Profissional, locais Sala 1 e Online); jornada às segundas, 08h-12h e 13h-18h (2030-01-07 é segunda).
"""

import html
import re
import threading
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import text

from app.models import Agendamento, Cliente
from app.models.enums import StatusAgendamento
from app.services import conta_agendamentos
from app.services.agendamentos import TRANSICOES
from app.services.conta_agendamentos import MOTIVO_CANCELAMENTO, TRANSICOES_DO_CLIENTE
from app.services.conta_cliente import ANTECEDENCIA_CLIENTE, pode_alterar
from tests.clinica import SEGUNDA
from tests.fabricas import inserir, mudar_modulo, sessao
from tests.test_conta_cliente import LOJA, NOVO_TEL, contar, criar_conta, destino, hrefs, parametros
from tests.test_site_paginas import opcoes_de_profissional

S = StatusAgendamento
SP = ZoneInfo('America/Sao_Paulo')
TELEFONE_LOJA = '(11) 3333-4444'
MSG_PRAZO = 'Este agendamento não pode mais ser alterado pelo site. Fale com a loja: '
MSG_COM_A_LOJA = 'Para remarcar este horário, fale com a loja: '


# --- Ajudantes ------------------------------------------------------------------------------------


@pytest.fixture
def conta(navegador, clinica, engine_dono):
    """Navegador na conta da Maria, com o telefone da loja preenchido."""
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET telefone = :t WHERE slug = 'loja-a'"), {'t': TELEFONE_LOJA})
    nav = navegador()
    criar_conta(nav, engine_dono)
    return nav


def na_segunda(hora: str) -> datetime:
    return datetime.fromisoformat(f'{SEGUNDA}T{hora}:00-03:00')


def daqui(minutos: int) -> datetime:
    return datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=minutos)


def proxima_segunda() -> date:
    hoje = datetime.now(SP).date()
    return hoje + timedelta(days=(7 - hoje.weekday()) % 7 or 7)


def marcar(
    engine,
    clinica,
    inicio: datetime,
    *,
    minutos: int = 60,
    situacao: StatusAgendamento = S.confirmado,
    cliente_id: str | None = None,
    funcionario_id: UUID | None = None,
    **extra,
) -> UUID:
    lt = clinica.lt
    ag = Agendamento(
        loja_id=lt.loja.id,
        cliente_id=cliente_id or clinica.maria,
        servico_id=extra.pop('servico_id', clinica.limpeza),
        funcionario_id=funcionario_id or lt.prof.id,
        inicio=inicio,
        fim=inicio + timedelta(minutes=minutos),
        status=situacao,
        preco=200,
        **extra,
    )
    inserir(engine, ag)
    return ag.id


def ler(engine, agendamento_id: UUID):
    with engine.connect() as conexao:
        return conexao.execute(
            text(
                'SELECT inicio, fim, status::text AS status, funcionario_id, local_id, servico_id, preco,'
                ' motivo_cancelamento, link_reuniao, atualizado_por FROM agendamentos WHERE id = :id'
            ),
            {'id': agendamento_id},
        ).one()


def url(agendamento_id: UUID | str, acao: str) -> str:
    return f'{LOJA}/conta/agendamentos/{agendamento_id}/{acao}'


def escolha(clinica, hora: str, **extra) -> dict[str, str]:
    return {'profissional': str(clinica.lt.prof.id), 'inicio': f'{SEGUNDA}T{hora}-03:00', **extra}


def confirmar_remarcacao(nav, agendamento_id: UUID, dados: dict[str, str]):
    return nav.post(url(agendamento_id, 'remarcar/confirmar'), data=dados, follow_redirects=False)


def ultima_auditoria(engine, agendamento_id: UUID):
    with engine.connect() as conexao:
        return conexao.execute(
            text(
                'SELECT operacao::text AS operacao, origem::text AS origem, funcionario_id, depois FROM auditoria'
                " WHERE tabela = 'agendamentos' AND registro_id = :id ORDER BY id DESC LIMIT 1"
            ),
            {'id': str(agendamento_id)},
        ).one()


def todas_as_rotas(nav, agendamento_id: UUID | str, clinica) -> list[httpx.Response]:
    """As cinco rotas da Fase B (GET e POST), sem seguir redirecionamentos."""
    return [
        nav.get(url(agendamento_id, 'cancelar'), follow_redirects=False),
        nav.post(url(agendamento_id, 'cancelar'), follow_redirects=False),
        nav.get(url(agendamento_id, 'remarcar'), follow_redirects=False),
        nav.get(
            url(agendamento_id, 'remarcar/confirmar'),
            params=escolha(clinica, '10:00'),
            follow_redirects=False,
        ),
        confirmar_remarcacao(nav, agendamento_id, escolha(clinica, '10:00')),
    ]


# --- Minha conta: ações por agendamento -------------------------------------------------------------


def test_minha_conta_mostra_remarcar_e_cancelar_so_nos_elegiveis(conta, clinica, engine_dono):
    elegivel = marcar(engine_dono, clinica, daqui(3 * 24 * 60))
    em_cima = marcar(engine_dono, clinica, daqui(60), situacao=S.pendente)  # menos de 2 h
    passado = marcar(engine_dono, clinica, daqui(-3 * 24 * 60), situacao=S.concluido)
    pagina = conta.get(f'{LOJA}/conta').text
    proximos, historico = pagina.split('id="historico"')
    links = hrefs(proximos)
    assert url(elegivel, 'remarcar') in links
    assert url(elegivel, 'cancelar') in links
    assert url(em_cima, 'remarcar') not in links
    assert url(em_cima, 'cancelar') not in links
    assert proximos.count('Para alterar, fale com a loja') == 1
    assert f'Para alterar, fale com a loja: <a href="tel:1133334444">{TELEFONE_LOJA}</a>' in proximos
    assert str(passado) not in pagina
    assert 'Para alterar' not in historico


def test_sem_telefone_da_loja_o_texto_nao_quebra(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    marcar(engine_dono, clinica, daqui(60))
    assert 'Para alterar, fale com a loja</p>' in nav.get(f'{LOJA}/conta').text


# --- Cancelar (SIT-23) -----------------------------------------------------------------------------


def test_cancelar_mais_de_2h_antes(conta, cliente, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), local_id=clinica.sala1)
    pagina = conta.get(url(ag, 'cancelar'))
    assert pagina.status_code == 200
    assert 'Cancelar este agendamento?' in pagina.text
    assert 'Limpeza' in pagina.text
    assert 'Segunda-feira, 7 de janeiro' in pagina.text
    assert 'Sala 1' in pagina.text
    assert f'action="{url(ag, "cancelar")}"' in pagina.text

    resposta = conta.post(url(ag, 'cancelar'), follow_redirects=False)
    assert destino(resposta) == f'{LOJA}/conta?aviso=cancelado'
    linha = ler(engine_dono, ag)
    assert linha.status == 'cancelado'
    assert linha.motivo_cancelamento == MOTIVO_CANCELAMENTO
    assert linha.atualizado_por is None
    auditoria = ultima_auditoria(engine_dono, ag)
    assert (auditoria.operacao, auditoria.origem, auditoria.funcionario_id) == ('alterar', 'site', None)
    assert auditoria.depois['status'] == 'cancelado'

    minha = conta.get(destino(resposta)).text
    assert 'Agendamento cancelado.' in minha
    proximos, historico = minha.split('id="historico"')
    assert 'Você não tem horários marcados.' in proximos
    assert 'Cancelado' in historico
    assert MOTIVO_CANCELAMENTO not in minha  # o motivo nunca aparece no site (SIT-21)

    # O painel vê cancelado, com o motivo do site, e o horário fica livre para outro pedido
    painel = cliente.get(f'/api/loja/agendamentos/{ag}', headers=clinica.lt.h_admin).json()
    assert (painel['status'], painel['motivo_cancelamento']) == ('cancelado', MOTIVO_CANCELAMENTO)
    pedido = {
        'servico': clinica.limpeza,
        **escolha(clinica, '09:00'),
        'local': clinica.sala1,
        'nome': 'Ana',
        'sobrenome': 'Souza',
        'telefone': '(11) 97777-6666',
    }
    assert urlsplit(destino(cliente.post(f'{LOJA}/agendar', data=pedido, follow_redirects=False))).path == (
        f'{LOJA}/agendar/pronto'
    )


@pytest.mark.parametrize('situacao', [S.pendente, S.agendado, S.confirmado])
def test_cancelar_vale_para_as_situacoes_ativas(conta, clinica, engine_dono, situacao):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), situacao=situacao)
    assert destino(conta.post(url(ag, 'cancelar'), follow_redirects=False)) == f'{LOJA}/conta?aviso=cancelado'
    assert ler(engine_dono, ag).status == 'cancelado'


def test_cancelar_de_novo_volta_a_minha_conta_sem_alterar(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    conta.post(url(ag, 'cancelar'), follow_redirects=False)
    antes = contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos'")
    repetido = conta.post(url(ag, 'cancelar'), follow_redirects=False)  # duplo clique sem JS (LOG-07)
    assert destino(repetido) == f'{LOJA}/conta?aviso=cancelado'
    assert contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos'") == antes


# --- Prazo e situações finais (SIT-23/24) ----------------------------------------------------------


def test_prazo_de_2h_na_funcao():
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    assert timedelta(hours=2) == ANTECEDENCIA_CLIENTE
    assert pode_alterar(S.confirmado, inicio, agora=inicio - timedelta(hours=2))  # encostado no prazo
    assert not pode_alterar(S.confirmado, inicio, agora=inicio - timedelta(hours=2) + timedelta(seconds=1))
    assert not pode_alterar(S.concluido, inicio, agora=inicio - timedelta(days=1))


def test_a_menos_de_2h_nada_se_altera_e_mostra_o_telefone(conta, clinica, engine_dono):
    inicio = daqui(115)
    ag = marcar(engine_dono, clinica, inicio, situacao=S.agendado)
    for resposta in todas_as_rotas(conta, ag, clinica):
        assert resposta.status_code == 409, resposta.request.url
        assert MSG_PRAZO + f'<a href="tel:1133334444">{TELEFONE_LOJA}</a>.' in resposta.text
        assert '<meta name="robots" content="noindex">' in resposta.text
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.inicio) == ('agendado', inicio)
    assert (
        contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos'") == 1
    )  # só a criação


def test_a_mais_de_2h_pode_alterar(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, daqui(130))
    assert conta.get(url(ag, 'cancelar')).status_code == 200
    assert conta.get(url(ag, 'remarcar')).status_code == 200


@pytest.mark.parametrize(
    ('situacao', 'motivo'),
    [(S.concluido, None), (S.nao_compareceu, None), (S.cancelado, 'Recusado pela loja')],
)
def test_situacoes_finais_nao_se_alteram_pelo_site(conta, clinica, engine_dono, situacao, motivo):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), situacao=situacao, motivo_cancelamento=motivo)
    for resposta in todas_as_rotas(conta, ag, clinica):
        assert resposta.status_code == 409, resposta.request.url
        assert MSG_PRAZO in resposta.text
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.motivo_cancelamento) == (situacao.value, motivo)


# --- Isolamento: só agendamentos da conta (404) -------------------------------------------------------


def test_agendamento_de_outro_telefone_loja_inexistente_ou_excluido_e_404(conta, clinica, lojas, engine_dono):
    do_joao = marcar(engine_dono, clinica, na_segunda('09:00'), cliente_id=clinica.joao)
    excluido = marcar(engine_dono, clinica, na_segunda('10:00'))
    with sessao(engine_dono) as db:
        db.get(Agendamento, excluido).excluido_em = datetime.now(UTC)
    # Outra loja, com uma cliente de mesmo telefone
    loja_b = lojas[1]
    maria_b = inserir(
        engine_dono,
        Cliente(loja_id=loja_b.loja.id, nome='Maria', sobrenome='B', telefone='(11) 98888-1111'),
    )
    da_outra_loja = inserir(
        engine_dono,
        Agendamento(
            loja_id=loja_b.loja.id,
            cliente_id=maria_b.id,
            funcionario_id=loja_b.prof.id,
            inicio=na_segunda('09:00'),
            fim=na_segunda('10:00'),
            status=S.confirmado,
        ),
    ).id
    # Cliente da Maria excluído na loja: os agendamentos dele saem da conta
    outra_maria = inserir(
        engine_dono,
        Cliente(loja_id=clinica.lt.loja.id, nome='Maria', sobrenome='Dois', telefone='11988881111'),
    )
    de_cliente_excluido = marcar(engine_dono, clinica, na_segunda('11:00'), cliente_id=outra_maria.id)
    with sessao(engine_dono) as db:
        db.get(Cliente, outra_maria.id).excluido_em = datetime.now(UTC)

    for alvo in (do_joao, excluido, da_outra_loja, de_cliente_excluido, uuid4(), 'abc', '1' * 40):
        for resposta in todas_as_rotas(conta, alvo, clinica):
            assert resposta.status_code == 404, (alvo, resposta.request.url)
            assert 'Limpeza' not in resposta.text
    for ag in (do_joao, da_outra_loja):
        assert ler(engine_dono, ag).status == 'confirmado'


def test_sem_sessao_vai_para_entrar_voltando_a_mesma_pagina(navegador, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    nav = navegador()
    resposta = nav.get(url(ag, 'cancelar'), follow_redirects=False)
    voltar = parametros(destino(resposta))['voltar']
    assert urlsplit(destino(resposta)).path == f'{LOJA}/conta/entrar'
    assert voltar == url(ag, 'cancelar')
    confirmar = nav.get(
        url(ag, 'remarcar/confirmar'), params=escolha(clinica, '10:00'), follow_redirects=False
    )
    voltar_confirmar = parametros(destino(confirmar))['voltar']
    assert urlsplit(voltar_confirmar).path == url(ag, 'remarcar/confirmar')
    assert parametros(voltar_confirmar) == escolha(clinica, '10:00')
    assert urlsplit(destino(nav.post(url(ag, 'cancelar'), follow_redirects=False))).path == (
        f'{LOJA}/conta/entrar'
    )
    assert ler(engine_dono, ag).status == 'confirmado'

    criar_conta(nav, engine_dono)
    assert nav.get(voltar).status_code == 200  # depois de entrar, a página do cancelamento abre


def test_cookie_vencido_e_apagado_e_nada_muda(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE cliente_contas SET sessao_versao = sessao_versao + 1'))
    resposta = conta.post(url(ag, 'cancelar'), follow_redirects=False)
    assert 'aviso=sessao' in destino(resposta)
    assert (
        'sessao_cliente=""' in resposta.headers['set-cookie'] or 'Max-Age=0' in resposta.headers['set-cookie']
    )
    assert ler(engine_dono, ag).status == 'confirmado'


# --- Remarcar (SIT-24, AGE-25) ---------------------------------------------------------------------


def test_remarcar_confirmado_volta_a_pendente_e_libera_o_horario(conta, cliente, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), minutos=90, local_id=clinica.sala1)
    with engine_dono.begin() as conexao:  # o preço do serviço muda depois: o agendamento mantém o dele
        conexao.execute(text('UPDATE servicos SET preco = 999 WHERE id = :id'), {'id': clinica.limpeza})

    pagina = conta.get(url(ag, 'remarcar/confirmar'), params=escolha(clinica, '10:00'))
    assert pagina.status_code == 200
    assert 'Remarcar: Limpeza' in pagina.text
    assert 'A loja vai confirmar o novo horário. O horário atual fica livre.' in pagina.text
    assert 'Confirmar remarcação' in pagina.text
    de, para = pagina.text.split('resumo-para')
    assert '09:00' in de
    assert '10:00' in para
    assert 'Sala 1' in de
    assert 'Online' in para  # o primeiro local permitido e livre, como no pedido (SIT-04)
    assert f'action="{url(ag, "remarcar/confirmar")}"' in pagina.text

    resposta = confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))
    assert destino(resposta) == f'{LOJA}/conta?aviso=remarcado'
    linha = ler(engine_dono, ag)
    assert linha.status == 'pendente'
    assert linha.inicio == na_segunda('10:00')
    assert linha.fim - linha.inicio == timedelta(minutes=90)  # duração atual, não a do serviço
    assert str(linha.servico_id) == clinica.limpeza
    assert linha.preco == 200
    assert str(linha.local_id) == clinica.online
    assert linha.link_reuniao is None
    assert linha.atualizado_por is None
    auditoria = ultima_auditoria(engine_dono, ag)
    assert (auditoria.operacao, auditoria.origem, auditoria.funcionario_id) == ('alterar', 'site', None)
    assert auditoria.depois['status'] == 'pendente'

    minha = conta.get(destino(resposta)).text
    assert 'Pedido de remarcação enviado.' in minha
    assert 'Aguardando confirmação' in minha

    # O horário antigo fica livre para outro pedido do site
    pedido = {
        'servico': clinica.limpeza,
        **escolha(clinica, '09:00'),
        'local': '',
        'nome': 'Ana',
        'sobrenome': 'Souza',
        'telefone': '(11) 97777-6666',
    }
    assert urlsplit(destino(cliente.post(f'{LOJA}/agendar', data=pedido, follow_redirects=False))).path == (
        f'{LOJA}/agendar/pronto'
    )
    # A loja aceita no painel como um pedido
    aceito = cliente.post(f'/api/loja/agendamentos/{ag}/aceitar', headers=clinica.lt.h_admin)
    assert aceito.status_code == 200, aceito.json()
    assert aceito.json()['status'] == 'confirmado'


def test_remarcar_pendente_continua_pendente_com_o_novo_horario(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), situacao=S.pendente)
    assert (
        destino(confirmar_remarcacao(conta, ag, escolha(clinica, '14:00'))) == f'{LOJA}/conta?aviso=remarcado'
    )
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.inicio) == ('pendente', na_segunda('14:00'))


def test_remarcar_de_novo_para_o_mesmo_horario_nao_muda_nada(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    assert (
        destino(confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))) == f'{LOJA}/conta?aviso=remarcado'
    )
    antes = contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos'")
    repetido = confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))  # duplo clique sem JS (LOG-07)
    assert destino(repetido) == f'{LOJA}/conta?aviso=remarcado'
    assert contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos'") == antes
    # Confirmado no mesmo horário: escolher outro (não volta a pendente à toa)
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE agendamentos SET status = 'confirmado' WHERE id = :id"), {'id': ag})
    mesmo = confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))
    assert parametros(destino(mesmo))['aviso'] == 'mesmo'
    assert ler(engine_dono, ag).status == 'confirmado'


def test_o_proprio_horario_nao_conta_como_ocupado(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    # 09:30 sobrepõe o próprio agendamento (09:00-10:00): vale
    assert (
        destino(confirmar_remarcacao(conta, ag, escolha(clinica, '09:30'))) == f'{LOJA}/conta?aviso=remarcado'
    )
    assert ler(engine_dono, ag).inicio == na_segunda('09:30')


def test_escolha_de_horario_da_remarcacao(conta, clinica, engine_dono):
    segunda = proxima_segunda()
    inicio = datetime.combine(segunda, datetime.min.time().replace(hour=9), tzinfo=SP)
    ag = marcar(engine_dono, clinica, inicio)
    marcar(engine_dono, clinica, inicio + timedelta(hours=2), cliente_id=clinica.joao)  # 11:00 ocupado
    prof = str(clinica.lt.prof.id)
    pagina = conta.get(url(ag, 'remarcar'), params={'profissional': prof, 'dia': segunda.isoformat()})
    assert pagina.status_code == 200
    texto = pagina.text
    assert 'Remarcar: Limpeza' in texto
    assert 'Horário atual: <strong>' in texto
    assert '60 min' in texto
    assert f'href="{LOJA}/conta"' in texto  # Voltar
    # Opções de profissional: links da própria remarcação (sem serviço), mantendo o dia escolhido
    opcoes = opcoes_de_profissional(texto)
    assert opcoes
    assert [nome for _, marcada, nome in opcoes if marcada] == ['Profissional']
    for parametros_da_opcao, _, _ in opcoes:
        assert 'servico' not in parametros_da_opcao
        assert parametros_da_opcao['dia'] == segunda.isoformat()
    assert all(
        urlsplit(html.unescape(h)).path == url(ag, 'remarcar')
        for h in re.findall(r'<a class="chip" href="([^"]+)"', texto)
    )
    assert 'name="servico"' not in texto
    horarios = {
        parametros(h)['inicio'][11:16]: h
        for h in hrefs(texto)
        if urlsplit(h).path == url(ag, 'remarcar/confirmar')
    }
    assert {'09:00', '09:30'} <= set(horarios)  # o próprio horário não ocupa
    assert '11:00' not in horarios
    assert '10:30' not in horarios  # 10:30-11:30 bate no das 11:00
    assert parametros(horarios['09:30'])['profissional'] == prof
    dias = [h for h in hrefs(texto) if urlsplit(h).path == url(ag, 'remarcar') and h.endswith('#horarios')]
    assert dias
    assert all(parametros(h.removesuffix('#horarios'))['profissional'] == prof for h in dias)

    # Profissional inválido: horários de qualquer profissional, com aviso
    invalido = conta.get(url(ag, 'remarcar'), params={'profissional': str(clinica.lt.recepcao.id)}).text
    assert 'Esse profissional não atende este serviço.' in invalido
    # O mesmo horário de antes (mesmo profissional e início): volta à escolha
    mesmo = conta.get(
        url(ag, 'remarcar/confirmar'),
        params={'profissional': prof, 'inicio': inicio.isoformat(timespec='minutes')},
        follow_redirects=False,
    )
    assert parametros(destino(mesmo))['aviso'] == 'mesmo'
    assert 'Esse já é o horário do seu agendamento.' in conta.get(destino(mesmo)).text


@pytest.mark.parametrize(
    ('dados', 'aviso'),
    [
        ({'inicio': f'{SEGUNDA}T12:00-03:00'}, 'ocupado'),  # intervalo de almoço (fora da jornada)
        ({'inicio': f'{SEGUNDA}T07:00-03:00'}, 'ocupado'),
        ({'inicio': f'{SEGUNDA}T11:00-03:00'}, 'ocupado'),  # ocupado pelo João
        ({'inicio': 'amanhã'}, 'horario'),
        ({'profissional': 'abc'}, 'horario'),
        ({'local': 'xyz'}, 'horario'),
        ({'local': 'SALA2'}, 'horario'),  # local que não é do serviço
        ({'profissional': 'RECEPCAO'}, 'horario'),  # não faz a Limpeza
    ],
)
def test_horario_que_nao_e_oferecido_volta_a_escolha(conta, clinica, engine_dono, dados, aviso):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    marcar(engine_dono, clinica, na_segunda('11:00'), cliente_id=clinica.joao)
    trocas = {'SALA2': clinica.sala2, 'RECEPCAO': str(clinica.lt.recepcao.id)}
    enviados = {**escolha(clinica, '10:00'), **{k: trocas.get(v, v) for k, v in dados.items()}}
    for resposta in (
        conta.get(url(ag, 'remarcar/confirmar'), params=enviados, follow_redirects=False),
        confirmar_remarcacao(conta, ag, enviados),
    ):
        local = destino(resposta)
        assert urlsplit(local).path == url(ag, 'remarcar')
        assert parametros(local)['aviso'] == aviso
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.inicio) == ('confirmado', na_segunda('09:00'))


def test_corrida_recusada_pelo_banco_volta_a_escolha(conta, clinica, engine_dono, monkeypatch):
    """Outro pedido leva o horário entre a conferência e a gravação: o EXCLUDE recusa (23P01)."""
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    original = conta_agendamentos.horario_oferecido

    def oferecido_e_ocupado_logo_depois(*args, **kwargs):
        escolhido = original(*args, **kwargs)
        marcar(engine_dono, clinica, na_segunda('10:00'), cliente_id=clinica.joao, situacao=S.pendente)
        return escolhido

    monkeypatch.setattr(conta_agendamentos, 'horario_oferecido', oferecido_e_ocupado_logo_depois)
    local = destino(confirmar_remarcacao(conta, ag, escolha(clinica, '10:00')))
    assert urlsplit(local).path == url(ag, 'remarcar')
    assert parametros(local) == {'dia': SEGUNDA, 'aviso': 'ocupado'}
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.inicio) == ('confirmado', na_segunda('09:00'))


def _postar_com_cookie(
    base: str, cookie: str, envios: list[tuple[str, dict[str, str]]]
) -> list[httpx.Response]:
    barreira = threading.Barrier(len(envios))
    respostas: list[httpx.Response | None] = [None] * len(envios)
    erros: list[BaseException] = []

    def postar(i: int) -> None:
        caminho, dados = envios[i]
        cabecalhos = {'Cookie': f'sessao_cliente={cookie}'}
        try:
            with httpx.Client(base_url=base, timeout=60, headers=cabecalhos) as c:
                barreira.wait()
                respostas[i] = c.post(caminho, data=dados)
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=postar, args=(i,)) for i in range(len(envios))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if erros:
        raise erros[0]
    return [r for r in respostas if r is not None]


def test_duas_remarcacoes_juntas_para_o_mesmo_horario(conta, clinica, engine_dono, servidor):
    primeiro = marcar(engine_dono, clinica, na_segunda('09:00'))
    segundo = marcar(engine_dono, clinica, na_segunda('14:00'))
    cookie = conta.cookies.get('sessao_cliente')
    alvo = escolha(clinica, '16:00')
    envios = [(url(primeiro, 'remarcar/confirmar'), alvo), (url(segundo, 'remarcar/confirmar'), alvo)]
    respostas = _postar_com_cookie(servidor, cookie, envios)
    avisos = sorted(parametros(r.headers['location'])['aviso'] for r in respostas)
    assert avisos == ['ocupado', 'remarcado']
    no_horario = 'SELECT count(*) FROM agendamentos WHERE inicio = :i'
    assert contar(engine_dono, no_horario, i=na_segunda('16:00')) == 1


def test_cancelar_junto_tres_vezes_cancela_uma(conta, clinica, engine_dono, servidor):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    cookie = conta.cookies.get('sessao_cliente')
    respostas = _postar_com_cookie(servidor, cookie, [(url(ag, 'cancelar'), {})] * 3)
    assert {r.headers['location'] for r in respostas} == {f'{LOJA}/conta?aviso=cancelado'}
    alteracoes = "SELECT count(*) FROM auditoria WHERE tabela = 'agendamentos' AND operacao = 'alterar'"
    assert contar(engine_dono, alteracoes) == 1


# --- Quando remarcar só com a loja (SIT-24) ----------------------------------------------------------


@pytest.mark.parametrize(
    'sql',
    [
        'UPDATE servicos SET ativo = false WHERE id = :servico',
        'UPDATE servicos SET excluido_em = now() WHERE id = :servico',
        'UPDATE funcionarios SET ativo = false WHERE loja_id = :loja',
        'UPDATE servico_funcionarios SET excluido_em = now() WHERE servico_id = :servico',
        'UPDATE locais SET ativo = false WHERE loja_id = :loja',
    ],
    ids=['servico-inativo', 'servico-removido', 'sem-profissional-ativo', 'ninguem-habilitado', 'sem-local'],
)
def test_sem_como_remarcar_pelo_site_mas_cancelar_continua(conta, clinica, engine_dono, sql):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    with engine_dono.begin() as conexao:
        conexao.execute(text(sql), {'servico': clinica.limpeza, 'loja': clinica.lt.loja.id})
    paginas = [
        conta.get(url(ag, 'remarcar'), follow_redirects=False),
        conta.get(url(ag, 'remarcar/confirmar'), params=escolha(clinica, '10:00'), follow_redirects=False),
        confirmar_remarcacao(conta, ag, escolha(clinica, '10:00')),
    ]
    for resposta in paginas:
        assert resposta.status_code == 409, resposta.request.url
        assert MSG_COM_A_LOJA + f'<a href="tel:1133334444">{TELEFONE_LOJA}</a>.' in resposta.text
        assert url(ag, 'cancelar') in hrefs(resposta.text)
    assert ler(engine_dono, ag).inicio == na_segunda('09:00')
    assert conta.get(url(ag, 'cancelar')).status_code == 200
    assert destino(conta.post(url(ag, 'cancelar'), follow_redirects=False)) == f'{LOJA}/conta?aviso=cancelado'


def test_com_servicos_ligado_agendamento_sem_servico_so_com_a_loja(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), servico_id=None)
    resposta = conta.get(url(ag, 'remarcar'))
    assert resposta.status_code == 409
    assert MSG_COM_A_LOJA in resposta.text


def test_sem_modulo_servicos_remarca_com_a_duracao_atual_entre_os_da_jornada(conta, clinica, engine_dono):
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'servicos', habilitado=False)
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), minutos=45)
    escolher = conta.get(url(ag, 'remarcar'))
    assert escolher.status_code == 200
    assert '45 min' in escolher.text
    recepcao = [
        url['profissional'] for url, _, nome in opcoes_de_profissional(escolher.text) if nome == 'Recepção'
    ]
    assert recepcao == [str(clinica.lt.recepcao.id)]  # SIT-08
    dados = {'profissional': str(clinica.lt.recepcao.id), 'inicio': f'{SEGUNDA}T10:00-03:00'}
    assert destino(confirmar_remarcacao(conta, ag, dados)) == f'{LOJA}/conta?aviso=remarcado'
    linha = ler(engine_dono, ag)
    assert linha.funcionario_id == clinica.lt.recepcao.id
    assert linha.fim - linha.inicio == timedelta(minutes=45)
    assert str(linha.servico_id) == clinica.limpeza  # o serviço fica como estava


def test_com_locais_o_servidor_escolhe_um_local_livre_e_permitido(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'), local_id=clinica.online)
    marcar(
        engine_dono,
        clinica,
        na_segunda('10:00'),
        cliente_id=clinica.joao,
        funcionario_id=clinica.lt.admin.id,
        local_id=clinica.online,
    )
    assert (
        destino(confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))) == f'{LOJA}/conta?aviso=remarcado'
    )
    assert str(ler(engine_dono, ag).local_id) == clinica.sala1  # Online ocupado às 10:00
    # Local pedido e livre: fica com ele
    pedido = escolha(clinica, '14:00', local=clinica.online)
    assert destino(confirmar_remarcacao(conta, ag, pedido)) == f'{LOJA}/conta?aviso=remarcado'
    assert str(ler(engine_dono, ag).local_id) == clinica.online
    # Local pedido e ocupado: volta à escolha
    ocupado = escolha(clinica, '10:00', local=clinica.online)
    assert parametros(destino(confirmar_remarcacao(conta, ag, ocupado)))['aviso'] == 'ocupado'


def test_sem_modulo_locais_o_local_antigo_sai(conta, clinica, engine_dono):
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'locais', habilitado=False)
    ag = marcar(
        engine_dono,
        clinica,
        na_segunda('09:00'),
        local_id=clinica.online,
        link_reuniao='https://meet.example.com/x',
    )
    assert (
        destino(confirmar_remarcacao(conta, ag, escolha(clinica, '10:00'))) == f'{LOJA}/conta?aviso=remarcado'
    )
    linha = ler(engine_dono, ag)
    assert (linha.local_id, linha.link_reuniao) == (None, None)


# --- AGE-25: transições só do cliente ------------------------------------------------------------------


def test_transicoes_do_cliente_nao_entram_no_painel(cliente, clinica, engine_dono):
    assert all(S.pendente not in destinos for destinos in TRANSICOES.values())
    assert set(TRANSICOES_DO_CLIENTE) == {S.pendente, S.agendado, S.confirmado}
    assert all(destinos == {S.pendente, S.cancelado} for destinos in TRANSICOES_DO_CLIENTE.values())
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    resposta = cliente.post(
        f'/api/loja/agendamentos/{ag}/status', json={'status': 'pendente'}, headers=clinica.lt.h_admin
    )
    assert resposta.status_code == 422
    assert ler(engine_dono, ag).status == 'confirmado'


# --- Segurança das páginas: origem, DIR-003, cabeçalhos, loja indisponível, parâmetros -----------------


@pytest.mark.parametrize('acao', ['cancelar', 'remarcar/confirmar'])
@pytest.mark.parametrize(
    'cabecalhos',
    [
        {'Origin': 'https://outro-site.example'},
        {'Origin': 'null'},
        {'Referer': 'https://outro-site.example/x'},
    ],
)
def test_post_de_outro_site_e_recusado(conta, clinica, engine_dono, acao, cabecalhos):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    resposta = conta.post(
        url(ag, acao), data=escolha(clinica, '10:00'), headers=cabecalhos, follow_redirects=False
    )
    assert resposta.status_code == 403
    linha = ler(engine_dono, ag)
    assert (linha.status, linha.inicio) == ('confirmado', na_segunda('09:00'))


def test_post_da_propria_origem_e_aceito(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    cabecalhos = {'Origin': 'https://testserver', 'Referer': f'https://testserver{url(ag, "cancelar")}'}
    assert conta.post(url(ag, 'cancelar'), headers=cabecalhos, follow_redirects=False).status_code == 303


def test_paginas_noindex_sem_painel_e_com_cabecalhos(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    final = marcar(engine_dono, clinica, na_segunda('14:00'), situacao=S.concluido)
    paginas = [
        conta.get(url(ag, 'cancelar')),
        conta.get(url(ag, 'remarcar')),
        conta.get(url(ag, 'remarcar/confirmar'), params=escolha(clinica, '10:00')),
        conta.get(url(final, 'cancelar')),
    ]
    for resposta in paginas:
        assert resposta.status_code in (200, 409)
        assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
        assert resposta.headers['cache-control'] == 'no-store'
        assert resposta.headers['x-frame-options'] == 'DENY'
        assert "form-action 'self'" in resposta.headers['content-security-policy']
        assert '<meta name="robots" content="noindex">' in resposta.text
        assert '/painel' not in resposta.text
        assert 'superadmin' not in resposta.text.lower()
        assert 'login' not in resposta.text.lower()


@pytest.mark.parametrize('situacao', ['suspensa', 'cancelada'])
def test_loja_indisponivel_responde_404(conta, clinica, engine_dono, situacao):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE lojas SET status = CAST(:s AS status_loja) WHERE slug = :slug'),
            {'s': situacao, 'slug': 'loja-a'},
        )
    for resposta in todas_as_rotas(conta, ag, clinica):
        assert resposta.status_code == 404, resposta.request.url
    assert ler(engine_dono, ag).status == 'confirmado'


def test_parametros_estranhos_nunca_dao_erro_do_servidor(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    for caminho in (
        url(ag, 'remarcar') + '?profissional=%ff&dia=%00&aviso=<b>',
        url(ag, 'remarcar') + '?dia=9999-99-99&profissional=' + 'x' * 3000,
        url(ag, 'remarcar/confirmar') + '?inicio=%ff%fe&profissional=&local=',
        url(ag, 'remarcar/confirmar') + '?inicio=2030-02-30T10:00&profissional=' + str(clinica.lt.prof.id),
        url('%ff', 'cancelar'),
        url(ag, 'remarcar') + '?dia=٢٠٣٠-٠١-٠٧&profissional=' + str(clinica.lt.prof.id),
        url(ag, 'remarcar') + '?dia=²⁰³⁰-⁰¹-⁰⁷',
        url(ag, 'remarcar/confirmar')
        + '?inicio=٢٠٣٠-٠١-٠٧T١٠:٠٠-03:00&profissional='
        + str(clinica.lt.prof.id),
        url('x' * 600, 'remarcar'),
    ):
        assert conta.get(caminho, follow_redirects=False).status_code in (200, 303, 404), caminho
    arabe = escolha(clinica, '10:00') | {'inicio': '٢٠٣٠-٠١-٠٧T١٠:٠٠-03:00'}
    assert parametros(destino(confirmar_remarcacao(conta, ag, arabe)))['aviso'] == 'horario'
    resposta = conta.post(
        url(ag, 'remarcar/confirmar'),
        content=b'\xff\xfe',
        headers={'content-type': 'application/x-www-form-urlencoded'},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    assert '<b>' not in conta.get(url(ag, 'remarcar') + '?aviso=<b>').text


def test_paginas_contam_no_limite_do_site(conta, clinica, engine_dono, monkeypatch):
    from app.config import get_settings

    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    monkeypatch.setattr(get_settings(), 'limite_site_por_ip', 1)
    conta.get(url(ag, 'cancelar'))
    assert conta.get(url(ag, 'cancelar')).status_code == 429


def test_novo_telefone_sem_agendamentos_nao_ve_os_da_maria(navegador, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, na_segunda('09:00'))
    outra = navegador()
    criar_conta(outra, engine_dono, NOVO_TEL, nome='Carla', sobrenome='Dias')
    for resposta in todas_as_rotas(outra, ag, clinica):
        assert resposta.status_code == 404
