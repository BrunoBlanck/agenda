"""SUPERADMIN: auditoria uma loja por vez, com filtros, nomes resolvidos e antes → depois (estrutura.md, 1.9)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.services.auditoria import registrar_acao
from tests.fabricas import cabecalho_superadmin, criar_loja_teste, criar_superadmin, sessao

URL = '/api/superadmin/auditoria'


@pytest.fixture
def cenario(cliente, engine_dono):
    superadmin = criar_superadmin(engine_dono)
    h = cabecalho_superadmin(superadmin)
    a, b = criar_loja_teste(engine_dono, 'loja-a'), criar_loja_teste(engine_dono, 'loja-b')
    maria = cliente.post(
        '/api/loja/clientes',
        json={'nome': 'Maria', 'sobrenome': 'Oliveira', 'telefone': '1111'},
        headers=a.h_admin,
    ).json()
    cliente.put(
        f'/api/loja/clientes/{maria["id"]}',
        json={'nome': 'Maria', 'sobrenome': 'Oliveira', 'telefone': '2222'},
        headers=a.h_recepcao,
    )
    cliente.post(
        '/api/loja/clientes', json={'nome': 'Bia', 'sobrenome': 'B', 'telefone': '3'}, headers=b.h_admin
    )
    return superadmin, h, a, b, maria


def test_lista_alteracoes_de_uma_loja_e_tabela(cliente, cenario):
    _, h, a, _, maria = cenario
    resposta = cliente.get(URL, params={'loja': str(a.loja.id), 'tabela': 'clientes'}, headers=h)
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['total'] == 2
    alterar, inserir = dados['itens']
    assert (alterar['operacao'], inserir['operacao']) == ('alterar', 'inserir')
    assert alterar['registro_id'] == maria['id']
    assert alterar['rotulo'] == 'Maria Oliveira'
    assert alterar['tabela_nome'] == 'Clientes'
    assert alterar['quem'] == {
        'tipo': 'funcionario',
        'id': str(a.recepcao.id),
        'nome': 'Recepção',
        'chave': f'f:{a.recepcao.id}',
    }
    assert alterar['mudancas'] == [{'campo': 'telefone', 'antes': '1111', 'depois': '2222'}]
    assert alterar['antes']['telefone'] == '1111'
    assert inserir['quem']['nome'] == 'Admin'
    assert inserir['mudancas'] == []
    assert alterar['criado_em'].endswith('-03:00')


def test_uma_loja_nao_ve_a_auditoria_da_outra(cliente, cenario):
    _, h, _, b, _ = cenario
    dados = cliente.get(URL, params={'loja': str(b.loja.id), 'tabela': 'clientes'}, headers=h).json()
    assert [i['rotulo'] for i in dados['itens']] == ['Bia B']


def test_filtro_por_pessoa_e_lista_de_pessoas(cliente, cenario):
    superadmin, h, a, _, _ = cenario
    cliente.put(
        f'/api/superadmin/lojas/{a.loja.id}/funcionarios/{a.prof.id}',
        json={
            'nome': 'Prof. Editado',
            'email': 'prof@loja-a.com',
            'perfil_id': str(a.perfis['Profissional'].id),
        },
        headers=h,
    )
    params = {'loja': str(a.loja.id)}
    pessoas = cliente.get(f'{URL}/pessoas', params=params, headers=h).json()
    assert [p['nome'] for p in pessoas][:1] == ['Admin']  # superadmin primeiro
    assert pessoas[0]['tipo'] == 'superadmin'
    chaves = {p['chave'] for p in pessoas}
    assert {f's:{superadmin.id}', f'f:{a.admin.id}', f'f:{a.recepcao.id}', 'sistema'} <= chaves

    so_admin = cliente.get(URL, params={**params, 'quem': f's:{superadmin.id}'}, headers=h).json()
    assert so_admin['total'] == 1
    item = so_admin['itens'][0]
    assert (item['tabela'], item['origem'], item['quem']['tipo']) == (
        'funcionarios',
        'superadmin',
        'superadmin',
    )
    assert item['mudancas'] == [{'campo': 'nome', 'antes': 'Profissional', 'depois': 'Prof. Editado'}]

    assert cliente.get(URL, params={**params, 'quem': 'x:1'}, headers=h).status_code == 422


def test_area_plataforma(cliente, cenario):
    superadmin, h, _, _, _ = cenario
    cliente.post('/api/superadmin/planos', json={'nome': 'Básico', 'preco_mensal': 89.9}, headers=h)
    dados = cliente.get(URL, params={'loja': 'plataforma', 'tabela': 'planos'}, headers=h).json()
    assert dados['total'] == 1
    assert dados['itens'][0]['loja_id'] is None
    assert dados['itens'][0]['rotulo'] == 'Básico'
    assert dados['itens'][0]['quem']['id'] == str(superadmin.id)

    tabelas = cliente.get(f'{URL}/tabelas', headers=h).json()
    assert 'planos' in tabelas['plataforma']
    assert 'agendamentos' in tabelas['loja']
    # Tabela de loja na área da plataforma (e o contrário)
    assert cliente.get(URL, params={'loja': 'plataforma', 'tabela': 'clientes'}, headers=h).status_code == 422
    assert cliente.get(URL, params={'loja': 'nao-e-uuid'}, headers=h).status_code == 422


def test_filtros_de_periodo(cliente, engine_dono, cenario):
    _, h, a, _, _ = cenario
    with engine_dono.begin() as conexao:
        conexao.execute(
            text(
                'INSERT INTO auditoria (loja_id, tabela, registro_id, operacao, depois, origem, criado_em)'
                " VALUES (:l, 'clientes', 'antigo', 'inserir', '{\"nome\": \"Antigo\"}', 'sistema',"
                " now() - interval '40 days')"
            ),
            {'l': a.loja.id},
        )
    params = {'loja': str(a.loja.id), 'tabela': 'clientes'}

    def total(**extra):
        resposta = cliente.get(URL, params={**params, **extra}, headers=h)
        assert resposta.status_code == 200, resposta.json()
        return resposta.json()['total']

    assert total() == 2  # padrão: últimos 30 dias
    assert total(periodo='hoje') == 2
    assert total(periodo='7d') == 2
    assert total(periodo='90d') == 3
    assert total(periodo='ano') == 3
    hoje = date.today()
    antes = (hoje - timedelta(days=45)).isoformat()
    assert total(periodo='intervalo', inicio=antes, fim=(hoje - timedelta(days=35)).isoformat()) == 1
    assert total(por_pagina=1) == 2

    sem_datas = cliente.get(URL, params={**params, 'periodo': 'intervalo'}, headers=h)
    assert sem_datas.status_code == 422
    assert sem_datas.json()['detail'] == 'Informe o início e o fim do período.'
    invertido = cliente.get(
        URL, params={**params, 'periodo': 'intervalo', 'inicio': hoje.isoformat(), 'fim': antes}, headers=h
    )
    assert invertido.status_code == 422
    assert cliente.get(URL, params={**params, 'periodo': 'semana'}, headers=h).status_code == 422


def test_redefinir_senha_aparece_sem_o_valor(cliente, cenario):
    _, h, a, _, _ = cenario
    cliente.post(
        f'/api/superadmin/lojas/{a.loja.id}/funcionarios/{a.prof.id}/redefinir-senha', json={}, headers=h
    )
    dados = cliente.get(URL, params={'loja': str(a.loja.id), 'tabela': 'funcionarios'}, headers=h).json()
    item = dados['itens'][0]
    assert item['mudancas'] == [{'campo': 'senha', 'antes': '••••••', 'depois': 'redefinida'}]
    assert 'senha_hash' not in item['depois']


def test_acao_sem_alteracao_de_linha(cliente, engine_dono, cenario):
    superadmin, h, a, _, _ = cenario
    with sessao(engine_dono, 'superadmin', superadmin_id=superadmin.id) as db:
        registrar_acao(
            db,
            loja_id=a.loja.id,
            tabela='funcionarios',
            registro_id=str(a.prof.id),
            antes={'senha': '••••••'},
            depois={'senha': 'link de nova senha enviado'},
        )
    item = cliente.get(URL, params={'loja': str(a.loja.id), 'tabela': 'funcionarios'}, headers=h).json()[
        'itens'
    ][0]
    assert item['operacao'] == 'alterar'
    assert item['quem']['id'] == str(superadmin.id)
    assert item['origem'] == 'superadmin'
    assert item['mudancas'] == [{'campo': 'senha', 'antes': '••••••', 'depois': 'link de nova senha enviado'}]
