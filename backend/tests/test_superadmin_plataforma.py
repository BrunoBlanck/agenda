"""SUPERADMIN: planos, usuários admin, visão geral e a regra de token em todas as rotas."""

import re

import pytest
from sqlalchemy import text

from app.main import app
from app.models.enums import StatusLoja
from tests.fabricas import (
    cabecalho,
    cabecalho_superadmin,
    criar_funcionario,
    criar_loja,
    criar_loja_teste,
    criar_plano,
    criar_superadmin,
    login_superadmin,
    mudar_modulo,
)

UUID_FALSO = '00000000-0000-0000-0000-000000000000'
PUBLICAS = {('POST', '/api/superadmin/auth/login')}


def _rotas_superadmin():
    for caminho, operacoes in app.openapi()['paths'].items():
        if caminho.startswith('/api/superadmin'):
            for metodo in operacoes:
                if (metodo.upper(), caminho) not in PUBLICAS:
                    yield metodo.upper(), re.sub(r'\{[^}]+\}', UUID_FALSO, caminho)


ROTAS = sorted(_rotas_superadmin())


@pytest.fixture
def sa(engine_dono):
    superadmin = criar_superadmin(engine_dono)
    return superadmin, cabecalho_superadmin(superadmin)


def test_ha_rotas_para_todos_os_menus():
    caminhos = {c for _, c in ROTAS}
    for prefixo in ('visao-geral', 'lojas', 'planos', 'usuarios', 'auditoria'):
        assert any(c.startswith(f'/api/superadmin/{prefixo}') for c in caminhos), prefixo


@pytest.mark.parametrize(('metodo', 'caminho'), ROTAS)
def test_toda_rota_exige_token_de_superadmin(cliente, engine_dono, metodo, caminho):
    assert cliente.request(metodo, caminho).status_code == 401
    loja, perfis = criar_loja(engine_dono, 'loja-a')
    admin = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@loja-a.com')
    resposta = cliente.request(metodo, caminho, headers=cabecalho(admin))
    assert resposta.status_code == 401
    assert resposta.json()['detail'] == 'Este acesso não vale para esta área. Entre com o usuário correto.'


def test_superadmin_inativo_perde_o_acesso(cliente, engine_dono):
    superadmin = criar_superadmin(engine_dono)
    h = cabecalho_superadmin(superadmin)
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE superadmin_usuarios SET ativo = false WHERE id = :i'), {'i': superadmin.id}
        )
    assert cliente.get('/api/superadmin/planos', headers=h).status_code == 401


# --- Planos -------------------------------------------------------------------------------------


def test_crud_de_planos(cliente, engine_dono, sa):
    superadmin, h = sa
    resposta = cliente.post(
        '/api/superadmin/planos',
        json={'nome': 'Básico', 'descricao': 'Começo', 'preco_mensal': 89.9},
        headers=h,
    )
    assert resposta.status_code == 201
    plano = resposta.json()
    assert plano['preco_mensal'] == 89.9
    assert plano['lojas_ativas'] == 0

    repetido = cliente.post('/api/superadmin/planos', json={'nome': 'Básico', 'preco_mensal': 10}, headers=h)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um plano com este nome.'
    negativo = cliente.post('/api/superadmin/planos', json={'nome': 'X', 'preco_mensal': -1}, headers=h)
    assert negativo.status_code == 422

    editado = cliente.put(
        f'/api/superadmin/planos/{plano["id"]}', json={'nome': 'Básico', 'preco_mensal': 99.9}, headers=h
    ).json()
    assert editado['preco_mensal'] == 99.9

    auditoria = (
        engine_dono.connect()
        .execute(
            text(
                "SELECT loja_id, superadmin_id, campos_alterados FROM auditoria WHERE tabela = 'planos'"
                " AND operacao = 'alterar'"
            )
        )
        .all()
    )
    assert [(a.loja_id, a.superadmin_id, a.campos_alterados) for a in auditoria] == [
        (None, superadmin.id, ['descricao', 'preco_mensal'])
    ]

    assert cliente.delete(f'/api/superadmin/planos/{plano["id"]}', headers=h).status_code == 204
    assert cliente.get(f'/api/superadmin/planos/{plano["id"]}', headers=h).status_code == 404
    assert cliente.get('/api/superadmin/planos', headers=h).json() == []


def test_plano_com_lojas_nao_e_excluido(cliente, engine_dono, sa):
    _, h = sa
    plano = criar_plano(engine_dono)
    loja, _ = criar_loja(engine_dono, 'loja-a')
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET plano_id = :p WHERE id = :l'), {'p': plano.id, 'l': loja.id})
    assert cliente.get('/api/superadmin/planos', headers=h).json()[0]['lojas_ativas'] == 1
    resposta = cliente.delete(f'/api/superadmin/planos/{plano.id}', headers=h)
    assert resposta.status_code == 409


# --- Usuários admin -----------------------------------------------------------------------------


def test_crud_de_usuarios_admin(cliente, sa):
    _superadmin, h = sa
    lista = cliente.get('/api/superadmin/usuarios', headers=h).json()
    assert [(u['email'], u['voce']) for u in lista] == [('admin@plataforma.com', True)]

    resposta = cliente.post(
        '/api/superadmin/usuarios', json={'nome': 'Camila', 'email': 'camila@plataforma.com'}, headers=h
    )
    assert resposta.status_code == 201
    camila = resposta.json()
    assert camila['voce'] is False
    login_superadmin(cliente, 'camila@plataforma.com', camila['senha_provisoria'])

    repetido = cliente.post(
        '/api/superadmin/usuarios', json={'nome': 'Outra', 'email': 'CAMILA@plataforma.com'}, headers=h
    )
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um usuário admin com este e-mail.'

    url = f'/api/superadmin/usuarios/{camila["id"]}'
    editado = cliente.put(
        url, json={'nome': 'Camila Rocha', 'email': 'camila@plataforma.com', 'senha': 'trocada123'}, headers=h
    ).json()
    assert editado['nome'] == 'Camila Rocha'
    login_superadmin(cliente, 'camila@plataforma.com', 'trocada123')

    assert cliente.delete(url, headers=h).status_code == 204
    assert cliente.get(url, headers=h).status_code == 404


def test_nao_se_exclui_nem_se_desativa(cliente, sa):
    superadmin, h = sa
    url = f'/api/superadmin/usuarios/{superadmin.id}'
    resposta = cliente.delete(url, headers=h)
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'Você não pode excluir o seu próprio usuário.'
    resposta = cliente.put(
        url, json={'nome': 'Admin', 'email': 'admin@plataforma.com', 'ativo': False}, headers=h
    )
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'Você não pode desativar o seu próprio usuário.'


def test_um_admin_desativa_outro(cliente, engine_dono, sa):
    """Como ninguém se desativa, quem age continua ativo: a plataforma nunca fica sem superadmin."""
    _, h = sa
    outro = criar_superadmin(engine_dono, 'outro@plataforma.com')
    h_outro = cabecalho_superadmin(outro)
    # O outro desativa o primeiro: ainda sobra ele mesmo ativo
    primeiro = cliente.get('/api/superadmin/usuarios', headers=h).json()
    id_primeiro = next(u['id'] for u in primeiro if u['voce'])
    corpo = {'nome': 'Admin', 'email': 'admin@plataforma.com', 'ativo': False}
    assert (
        cliente.put(f'/api/superadmin/usuarios/{id_primeiro}', json=corpo, headers=h_outro).status_code == 200
    )
    # Excluir um usuário inativo
    terceiro = criar_superadmin(engine_dono, 'terceiro@plataforma.com', ativo=False)
    assert cliente.delete(f'/api/superadmin/usuarios/{terceiro.id}', headers=h_outro).status_code == 204
    # O primeiro (inativo) perdeu o acesso
    assert cliente.get('/api/superadmin/usuarios', headers=h).status_code == 401


# --- Visão geral --------------------------------------------------------------------------------


def test_visao_geral(cliente, engine_dono, sa):
    _superadmin, h = sa
    basico = criar_plano(engine_dono, 'Básico', '89.90')
    pro = criar_plano(engine_dono, 'Profissional', '189.90')
    a = criar_loja_teste(engine_dono, 'loja-a')  # 3 funcionários, todos os módulos
    b = criar_loja_teste(engine_dono, 'loja-b')
    suspensa, perfis = criar_loja(engine_dono, 'suspensa', status=StatusLoja.suspensa)
    criar_funcionario(engine_dono, suspensa, perfis['Administrador'], 'x@suspensa.com')
    criar_funcionario(engine_dono, a.loja, a.perfis['Profissional'], 'inativo@loja-a.com', ativo=False)
    mudar_modulo(engine_dono, b.loja.id, 'materiais', habilitado=False)
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE lojas SET plano_id = :p WHERE id = :l'), {'p': basico.id, 'l': a.loja.id}
        )
        conexao.execute(text('UPDATE lojas SET plano_id = :p WHERE id = :l'), {'p': pro.id, 'l': b.loja.id})
        conexao.execute(
            text("UPDATE lojas SET plano_id = :p, tipo = 'escola' WHERE id = :l"),
            {'p': pro.id, 'l': suspensa.id},
        )

    # Uma ação de superadmin para a lista de últimas ações
    cliente.post(f'/api/superadmin/lojas/{a.loja.id}/status', json={'status': 'ativa'}, headers=h)
    cliente.patch(
        f'/api/superadmin/lojas/{a.loja.id}/modulos/locais', json={'observacao': 'Teste'}, headers=h
    )

    visao = cliente.get('/api/superadmin/visao-geral', headers=h).json()
    assert (visao['lojas_ativas'], visao['lojas_suspensas'], visao['lojas_canceladas']) == (2, 1, 0)
    assert visao['funcionarios_ativos'] == 6
    assert visao['receita_mensal'] == pytest.approx(89.9 + 189.9)
    assert visao['lojas_por_tipo']['clinica'] == {'ativa': 2, 'suspensa': 0, 'cancelada': 0}
    assert visao['lojas_por_tipo']['escola'] == {'ativa': 0, 'suspensa': 1, 'cancelada': 0}
    em_uso = {m['codigo']: m['lojas'] for m in visao['modulos_em_uso']}
    assert em_uso == {'servicos': 2, 'materiais': 1, 'controle_tempo': 2, 'locais': 2}
    acao = visao['ultimas_acoes'][0]
    assert (acao['tabela'], acao['tabela_nome'], acao['superadmin_nome'], acao['loja_nome']) == (
        'loja_funcionalidades',
        'Módulos da loja',
        'Admin',
        'Loja loja-a',
    )


def test_visao_geral_sem_dados(cliente, sa):
    _, h = sa
    visao = cliente.get('/api/superadmin/visao-geral', headers=h).json()
    assert visao['lojas_ativas'] == 0
    assert visao['receita_mensal'] == 0
    assert visao['ultimas_acoes'] == []


def test_rotas_com_os_dados_do_seed(cliente, engine_app):
    """SUPERADMIN e site do consumidor com os dados de exemplo (mock.js e plataforma.js)."""
    from datetime import date, timedelta

    from scripts import seed

    seed.executar(engine_app)
    h = login_superadmin(cliente, 'rafael@agendaplataforma.com', seed.SENHA_SUPERADMIN)
    visao = cliente.get('/api/superadmin/visao-geral', headers=h).json()
    assert (visao['lojas_ativas'], visao['lojas_suspensas'], visao['lojas_canceladas']) == (3, 1, 1)
    lojas = cliente.get('/api/superadmin/lojas', headers=h).json()
    assert lojas['total'] == 5
    sorriso = next(i for i in lojas['itens'] if i['slug'] == 'clinica-sorriso')
    for caminho in ('', '/modulos', '/funcionarios', '/perfis'):
        assert cliente.get(f'/api/superadmin/lojas/{sorriso["id"]}{caminho}', headers=h).status_code == 200
    for caminho in (
        '/api/superadmin/planos',
        '/api/superadmin/usuarios',
        '/api/superadmin/auditoria/tabelas',
    ):
        assert cliente.get(caminho, headers=h).status_code == 200
    auditoria = cliente.get(
        '/api/superadmin/auditoria', params={'loja': sorriso['id'], 'periodo': 'ano'}, headers=h
    )
    assert auditoria.status_code == 200

    site = cliente.get('/api/site/clinica-sorriso').json()
    assert site['nome_fantasia'] == 'Clínica Sorriso'
    servicos = cliente.get('/api/site/clinica-sorriso/servicos').json()
    assert servicos
    hoje = date.today()
    dias = cliente.get(
        '/api/site/clinica-sorriso/horarios',
        params={
            'servico_id': servicos[0]['id'],
            'inicio': hoje.isoformat(),
            'fim': (hoje + timedelta(days=13)).isoformat(),
        },
    )
    assert dias.status_code == 200
    assert any(d['horarios'] for d in dias.json())
    assert cliente.get('/api/site/clinica-bem-estar').status_code == 404
