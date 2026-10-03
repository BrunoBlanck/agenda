"""LOG-05: fuso da loja que o Postgres (ou o Python) não conhece.

A criação e a edição da loja pelo superadmin recusam o fuso (422). Se mesmo assim um fuso inválido
chegar ao banco (dado antigo, base de fusos atualizada), nenhuma rota cai: vale America/Sao_Paulo.
"""

import logging

import pytest
from sqlalchemy import text

from tests.clinica import SEGUNDA
from tests.fabricas import cabecalho_superadmin, criar_plano, criar_superadmin, login_loja

MSG_FUSO = 'Fuso horário inválido (ex.: America/Sao_Paulo).'


def _mudar_fuso(engine, loja_id, fuso):
    with engine.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET fuso_horario = :f WHERE id = :i'), {'f': fuso, 'i': loja_id})


@pytest.mark.parametrize('fuso', ['Marte/Olympus_Mons', 'America/Sao_Paulo; DROP TABLE lojas'])
def test_fuso_desconhecido_nao_derruba_login_nem_rotas(cliente, clinica, engine_dono, caplog, fuso):
    lt = clinica.lt
    ag = cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=lt.h_admin)
    assert ag.status_code == 201, ag.json()
    _mudar_fuso(engine_dono, lt.loja.id, fuso)

    with caplog.at_level(logging.WARNING):
        h = login_loja(cliente, lt.loja.slug, lt.admin.email)
        lista = cliente.get('/api/loja/agendamentos', headers=h)
    assert lista.status_code == 200, lista.json()
    # Cai no fuso padrão (America/Sao_Paulo), nas datas do banco e nas do Python
    assert lista.json()['itens'][0]['inicio'] == f'{SEGUNDA}T09:00:00-03:00'
    assert cliente.get('/api/loja/inicio', headers=h).status_code == 200
    assert cliente.get(f'/api/site/{lt.loja.slug}').status_code == 200
    assert any('fuso' in r.getMessage() for r in caplog.records)


@pytest.fixture
def sa(engine_dono):
    return cabecalho_superadmin(criar_superadmin(engine_dono))


def _loja(plano, **extra):
    return {
        'tipo': 'barbearia',
        'nome': 'Navalha Cortes ME',
        'nome_fantasia': 'Barbearia Navalha',
        'slug': 'barbearia-navalha',
        'plano_id': str(plano.id),
        'admin': {'nome': 'Marcos Silva', 'email': 'marcos@navalha.com'},
        **extra,
    }


def test_superadmin_recusa_fuso_que_o_postgres_nao_conhece(cliente, engine_dono, sa, monkeypatch):
    plano = criar_plano(engine_dono)
    criada = cliente.post(
        '/api/superadmin/lojas', json=_loja(plano, fuso_horario='America/Manaus'), headers=sa
    )
    assert criada.status_code == 201, criada.json()

    # O Python conhece America/Manaus; o "Postgres" deste teste, não
    monkeypatch.setattr('app.db._fusos_do_banco', frozenset({'UTC', 'America/Sao_Paulo'}))
    url = '/api/superadmin/lojas'
    for resposta in (
        cliente.post(url, json=_loja(plano, slug='outra', fuso_horario='America/Manaus'), headers=sa),
        cliente.put(
            f'{url}/{criada.json()["id"]}',
            json={k: v for k, v in _loja(plano, fuso_horario='America/Manaus').items() if k != 'admin'},
            headers=sa,
        ),
    ):
        assert resposta.status_code == 422
        assert resposta.json() == {
            'detail': 'Verifique os dados informados.',
            'erros': [{'campo': 'fuso_horario', 'mensagem': MSG_FUSO}],
        }
    # Um fuso conhecido pelos dois continua valendo
    ok = cliente.post(url, json=_loja(plano, slug='mais-uma', fuso_horario='America/Sao_Paulo'), headers=sa)
    assert ok.status_code == 201, ok.json()
