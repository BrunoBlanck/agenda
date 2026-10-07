"""Notificações no site: avisos da conta (SIT-25, NOT-06), ações do cliente (NOT-03) e o prazo da loja (CFG-05).

Maria (11) 98888-1111 tem a conta; João (11) 98888-2222 é outro telefone.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.models import Agendamento, Cliente
from app.models.enums import StatusAgendamento
from tests.clinica import SEGUNDA
from tests.fabricas import inserir
from tests.test_conta_cliente import LOJA, criar_conta, destino
from tests.test_conta_cliente_alterar import confirmar_remarcacao, escolha, url
from tests.test_notificacoes import avisos, criar_no_painel, pedir_pelo_site
from tests.test_notificacoes_envio import antecedencia

S = StatusAgendamento
AVISOS = f'{LOJA}/conta/avisos'
NOVE = datetime.fromisoformat(f'{SEGUNDA}T09:00:00-03:00')


@pytest.fixture
def conta(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    return nav


def marcar(
    engine, clinica, inicio: datetime, cliente_id: str | None = None, situacao=S.confirmado
) -> Agendamento:
    lt = clinica.lt
    return inserir(
        engine,
        Agendamento(
            loja_id=lt.loja.id,
            cliente_id=cliente_id or clinica.maria,
            servico_id=clinica.limpeza,
            funcionario_id=lt.prof.id,
            local_id=clinica.sala1,
            inicio=inicio,
            fim=inicio + timedelta(hours=1),
            status=situacao,
            preco=200,
        ),
    )


def daqui(minutos: int) -> datetime:
    return datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=minutos)


# --- Ações do cliente pelo site (NOT-03) -----------------------------------------------------------------


def test_cancelar_pelo_site_avisa_so_o_profissional(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, NOVE)
    resposta = conta.post(url(ag.id, 'cancelar'), follow_redirects=False)
    assert destino(resposta) == f'{LOJA}/conta?aviso=cancelado'
    assert avisos(engine_dono, tipo='cliente') == []  # a ação foi do próprio cliente
    [aviso] = avisos(engine_dono, tipo='loja')
    assert aviso['funcionario_id'] == clinica.lt.prof.id
    assert (aviso['evento'], aviso['titulo']) == ('cancelado_pelo_cliente', 'Cancelado pelo cliente')
    assert aviso['mensagem'] == 'Maria Oliveira cancelou Limpeza de seg 07/01 às 9h pelo site.'
    # O mesmo envio de novo não gera outro aviso
    conta.post(url(ag.id, 'cancelar'), follow_redirects=False)
    assert len(avisos(engine_dono)) == 1


def test_remarcar_para_o_mesmo_profissional(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, NOVE)
    resposta = confirmar_remarcacao(conta, ag.id, escolha(clinica, '10:00', local=clinica.sala1))
    assert destino(resposta) == f'{LOJA}/conta?aviso=remarcado'
    [para_cliente] = avisos(engine_dono, tipo='cliente')
    assert (para_cliente['evento'], para_cliente['titulo']) == (
        'pedido_recebido',
        'Pedido de remarcação recebido',
    )
    assert para_cliente['mensagem'] == (
        'Recebemos o seu pedido para remarcar Limpeza para seg 07/01 às 10h com Profissional (Sala 1). '
        'Loja loja-a vai confirmar o novo horário.'
    )
    [para_loja] = avisos(engine_dono, tipo='loja')
    assert (para_loja['evento'], para_loja['funcionario_id']) == ('remarcacao_pedida', clinica.lt.prof.id)
    assert (
        para_loja['mensagem']
        == 'Maria Oliveira pediu para remarcar Limpeza de seg 07/01 às 9h para seg 07/01 às 10h.'
    )


def test_remarcar_para_outro_profissional_avisa_os_dois(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, NOVE)
    resposta = confirmar_remarcacao(
        conta, ag.id, escolha(clinica, '10:00', profissional=str(clinica.lt.admin.id))
    )
    assert destino(resposta) == f'{LOJA}/conta?aviso=remarcado'
    por_funcionario = {a['funcionario_id']: a for a in avisos(engine_dono, tipo='loja')}
    assert set(por_funcionario) == {clinica.lt.admin.id, clinica.lt.prof.id}
    assert por_funcionario[clinica.lt.admin.id]['evento'] == 'remarcacao_pedida'
    antigo = por_funcionario[clinica.lt.prof.id]
    assert antigo['evento'] == 'cancelado_pelo_cliente'
    assert antigo['mensagem'] == 'Maria Oliveira remarcou Limpeza de seg 07/01 às 9h para outro profissional.'
    assert len(avisos(engine_dono, tipo='cliente')) == 1
    # A recepção (que não é profissional do agendamento) não recebe nada
    assert {a['funcionario_id'] for a in avisos(engine_dono, tipo='loja')} == {
        clinica.lt.admin.id,
        clinica.lt.prof.id,
    }


def test_profissional_inativo_nao_recebe_o_cancelamento(conta, clinica, engine_dono):
    ag = marcar(engine_dono, clinica, NOVE)
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE funcionarios SET ativo = false WHERE id = :f'), {'f': clinica.lt.prof.id}
        )
    assert (
        destino(conta.post(url(ag.id, 'cancelar'), follow_redirects=False)) == f'{LOJA}/conta?aviso=cancelado'
    )
    assert avisos(engine_dono) == []


# --- Prazo da loja para cancelar e remarcar (CFG-05) --------------------------------------------------------


@pytest.mark.parametrize(
    ('minutos', 'falta', 'pode'),
    [(0, 10, True), (120, 115, False), (120, 125, True), (1440, 23 * 60, False), (1440, 25 * 60, True)],
)
def test_prazo_do_site_segue_a_configuracao(conta, clinica, engine_dono, minutos, falta, pode):
    antecedencia(engine_dono, clinica.lt.loja.id, minutos)
    ag = marcar(engine_dono, clinica, daqui(falta))
    for acao in ('cancelar', 'remarcar'):
        assert conta.get(url(ag.id, acao)).status_code == (200 if pode else 409), acao
    resposta = conta.post(url(ag.id, 'cancelar'), follow_redirects=False)
    if pode:
        assert destino(resposta) == f'{LOJA}/conta?aviso=cancelado'
    else:
        assert resposta.status_code == 409
        assert 'Este agendamento não pode mais ser alterado pelo site. Fale com a loja' in resposta.text


def test_a_loja_altera_depois_do_prazo_do_site(cliente, conta, clinica, engine_dono):
    antecedencia(engine_dono, clinica.lt.loja.id, 180)
    ag = marcar(engine_dono, clinica, daqui(120))
    assert conta.get(url(ag.id, 'cancelar')).status_code == 409
    resposta = cliente.post(
        f'/api/loja/agendamentos/{ag.id}/status',
        json={'status': 'cancelado', 'motivo_cancelamento': 'Pedido por telefone'},
        headers=clinica.lt.h_admin,
    )
    assert resposta.status_code == 200


# --- Avisos da conta (SIT-25, NOT-06) ---------------------------------------------------------------------


def test_avisos_exige_sessao(navegador, clinica):
    resposta = navegador().get(AVISOS, follow_redirects=False)
    assert resposta.status_code == 303
    assert destino(resposta) == f'{LOJA}/conta/entrar?voltar=%2Floja-a%2Fconta%2Favisos'


def test_avisos_vazio_e_sem_contador(conta, clinica):
    pagina = conta.get(AVISOS)
    assert pagina.status_code == 200
    assert 'Nenhum aviso por enquanto.' in pagina.text
    assert '<meta name="robots" content="noindex">' in pagina.text
    assert 'aria-label="Avisos"' in pagina.text
    assert 'class="contador"' not in pagina.text


def test_avisos_do_telefone_da_conta_marcados_ao_abrir(cliente, conta, clinica, engine_dono):
    criar_no_painel(cliente, clinica)  # Maria
    outra_maria = inserir(
        engine_dono,
        Cliente(loja_id=clinica.lt.loja.id, nome='Maria', sobrenome='Dois', telefone='11988881111'),
    )
    criar_no_painel(cliente, clinica, cliente_id=str(outra_maria.id), inicio=f'{SEGUNDA}T10:00')
    criar_no_painel(cliente, clinica, cliente_id=clinica.joao, inicio=f'{SEGUNDA}T11:00')  # outro telefone

    inicio = conta.get(f'{LOJA}/conta')
    assert 'aria-label="Avisos, 2 não lidos"' in inicio.text
    assert '<span class="contador" aria-hidden="true">2</span>' in inicio.text
    assert f'href="{AVISOS}"' in inicio.text

    primeira = conta.get(AVISOS)
    assert primeira.status_code == 200
    assert primeira.text.count('class="aviso-item aviso-novo"') == 2
    assert primeira.text.count('Novo</span>') == 2
    assert 'agendou Limpeza para seg 07/01 às 9h' in primeira.text
    assert 'agendou Limpeza para seg 07/01 às 10h' in primeira.text
    assert 'às 11h' not in primeira.text  # do João
    assert 'aria-label="Avisos"' in primeira.text  # o cabeçalho já conta depois de marcar
    assert {
        a['status_site'] for a in avisos(engine_dono, tipo='cliente') if str(a['cliente_id']) != clinica.joao
    } == {2}
    assert [a['status_site'] for a in avisos(engine_dono) if str(a['cliente_id']) == clinica.joao] == [1]

    segunda = conta.get(AVISOS)
    assert 'aviso-novo' not in segunda.text
    assert segunda.text.count('class="aviso-item"') == 2


def test_aviso_que_chega_depois_continua_novo(cliente, conta, clinica, engine_dono):
    criar_no_painel(cliente, clinica)
    conta.get(AVISOS)
    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T10:00')
    assert 'aria-label="Avisos, 1 não lido"' in conta.get(f'{LOJA}/conta').text


def test_avisos_paginados_e_pagina_estranha(cliente, conta, clinica, engine_dono):
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('SET LOCAL session_replication_role = replica')
        )  # o trigger reescreveria criado_em
        for i in range(25):
            conexao.execute(
                text(
                    'INSERT INTO notificacoes (loja_id, tipo, cliente_id, evento, titulo, mensagem, status_email,'
                    " status_whatsapp, criado_em) VALUES (:l, 'cliente', :c, 'confirmado', :t, 'm', 4, 4,"
                    ' now() - make_interval(mins => :i))'
                ),
                {'l': clinica.lt.loja.id, 'c': clinica.maria, 't': f'Aviso {i:02d}', 'i': i},
            )
    primeira = conta.get(AVISOS)
    assert 'Aviso 00' in primeira.text
    assert 'Aviso 19' in primeira.text
    assert 'Aviso 20' not in primeira.text
    assert 'Página 1 de 2' in primeira.text
    assert f'href="{AVISOS}?pagina=2"' in primeira.text
    segunda = conta.get(AVISOS, params={'pagina': '2'})
    assert 'Aviso 24' in segunda.text
    assert 'Aviso 19' not in segunda.text
    assert f'href="{AVISOS}" rel="prev"' in segunda.text
    for estranha in ('9', '0', '-1', 'abc', '²', '9' * 20):
        resposta = conta.get(AVISOS, params={'pagina': estranha})
        assert resposta.status_code == 200, estranha
        assert 'Página 1 de 2' in resposta.text


def test_avisos_sem_caminho_para_o_painel(cliente, conta, clinica, engine_dono):
    """DIR-003: a página de avisos (com avisos) não leva ao painel nem ao login."""
    criar_no_painel(cliente, clinica)
    pedir_pelo_site(cliente, clinica, telefone='(11) 98888-1111')
    html = conta.get(AVISOS).text.lower()
    for proibido in ('painel', 'superadmin', 'login'):
        assert proibido not in html
    assert 'motivo' not in html


def test_avisos_de_outra_loja_nao_aparecem(cliente, conta, clinica, lojas, engine_dono):
    loja_b = lojas[1]
    maria_b = inserir(
        engine_dono, Cliente(loja_id=loja_b.loja.id, nome='Maria', sobrenome='B', telefone='(11) 98888-1111')
    )
    with engine_dono.begin() as conexao:
        conexao.execute(
            text(
                'INSERT INTO notificacoes (loja_id, tipo, cliente_id, evento, titulo, mensagem, status_email,'
                " status_whatsapp) VALUES (:l, 'cliente', :c, 'confirmado', 'Da loja B', 'm', 4, 4)"
            ),
            {'l': loja_b.loja.id, 'c': maria_b.id},
        )
    assert 'Da loja B' not in conta.get(AVISOS).text
    assert 'Nenhum aviso por enquanto.' in conta.get(AVISOS).text
