"""SUPERADMIN: lojas, situação, módulos e funcionários pelo suporte (estrutura.md, 1.6, 1.7 e 2.4)."""

import pytest
from sqlalchemy import text

from app.models.enums import StatusLoja
from tests.fabricas import (
    SENHA,
    cabecalho,
    cabecalho_superadmin,
    criar_loja,
    criar_loja_teste,
    criar_plano,
    criar_superadmin,
    login_loja,
)

URL = '/api/superadmin/lojas'


@pytest.fixture
def sa(engine_dono):
    superadmin = criar_superadmin(engine_dono)
    return superadmin, cabecalho_superadmin(superadmin)


@pytest.fixture
def plano(engine_dono):
    return criar_plano(engine_dono)


def nova_loja(**extra):
    return {
        'tipo': 'barbearia',
        'nome': 'Navalha Cortes ME',
        'nome_fantasia': 'Barbearia Navalha',
        'slug': 'barbearia-navalha',
        'email': 'contato@navalha.com',
        'cidade': 'Campinas',
        'uf': 'sp',
        'modulos': ['servicos', 'locais'],
        'admin': {'nome': 'Marcos Silva', 'email': 'marcos@navalha.com'},
        'rotulo_local': 'Cadeira',
        'rotulo_local_plural': 'Cadeiras',
        **extra,
    }


def criar(cliente, h, plano, **extra):
    resposta = cliente.post(URL, json={'plano_id': str(plano.id), **nova_loja(**extra)}, headers=h)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def consultar(engine, sql, **params):
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).mappings().all()


# --- Criação ------------------------------------------------------------------------------------


def test_cria_loja_com_perfis_modulos_e_primeiro_administrador(cliente, engine_dono, sa, plano):
    superadmin, h = sa
    loja = criar(cliente, h, plano)

    assert loja['slug'] == 'barbearia-navalha'
    assert loja['uf'] == 'SP'
    assert loja['status'] == 'ativa'
    assert loja['plano_nome'] == 'Básico'
    assert loja['modulos'] == {'servicos': True, 'locais': True, 'materiais': False, 'controle_tempo': False}
    assert loja['rotulo_local'] == 'Cadeira'
    assert loja['funcionarios_ativos'] == 1
    assert loja['atualizado_por'] == 'superadmin'
    assert loja['atualizado_por_nome'] == 'Admin'
    admin = loja['admin']
    assert admin['perfil_nome'] == 'Administrador'
    assert admin['perfil_acesso_total'] is True
    assert admin['criado_por'] == 'superadmin'
    assert loja['senha_provisoria']

    perfis = consultar(engine_dono, 'SELECT nome, padrao FROM perfis WHERE loja_id = :l', l=loja['id'])
    assert {p['nome'] for p in perfis} == {'Administrador', 'Recepção', 'Profissional'}
    linha = consultar(engine_dono, 'SELECT criado_por FROM lojas WHERE id = :l', l=loja['id'])[0]
    assert linha['criado_por'] == superadmin.id
    func = consultar(
        engine_dono,
        'SELECT criado_por_superadmin, criado_por_funcionario, atualizado_por FROM funcionarios WHERE id = :f',
        f=admin['id'],
    )[0]
    assert func == {
        'criado_por_superadmin': superadmin.id,
        'criado_por_funcionario': None,
        'atualizado_por': None,
    }

    # Tudo foi auditado como superadmin
    origens = consultar(
        engine_dono,
        'SELECT DISTINCT origem::text AS origem, superadmin_id FROM auditoria WHERE loja_id = :l',
        l=loja['id'],
    )
    assert origens == [{'origem': 'superadmin', 'superadmin_id': superadmin.id}]

    # O Administrador entra com a senha provisória
    token = login_loja(cliente, 'barbearia-navalha', 'marcos@navalha.com', loja['senha_provisoria'])
    eu = cliente.get('/api/loja/eu', headers=token).json()
    assert eu['loja']['rotulo_local'] == 'Cadeira'
    assert eu['modulos']['materiais'] is False


def test_criar_loja_com_senha_informada_nao_gera_provisoria(cliente, sa, plano):
    _, h = sa
    loja = criar(
        cliente, h, plano, admin={'nome': 'Marcos', 'email': 'marcos@navalha.com', 'senha': 'segredo123'}
    )
    assert loja['senha_provisoria'] is None
    login_loja(cliente, 'barbearia-navalha', 'marcos@navalha.com', 'segredo123')


@pytest.mark.parametrize(
    ('extra', 'campo'),
    [
        ({'slug': 'Com Espaço'}, 'slug'),
        ({'slug': '-comeca-com-hifen'}, 'slug'),
        ({'tipo': 'padaria'}, 'tipo'),
        ({'modulos': ['agenda']}, 'modulos'),
        ({'fuso_horario': 'Lua/Base'}, 'fuso_horario'),
        ({'cnpj': '11.111.111/1111-11'}, 'cnpj'),
        ({'admin': {'nome': 'X', 'email': 'nao-e-email'}}, 'admin.email'),
        ({'admin': {'nome': 'X', 'email': 'x@x.com', 'senha': 'curta'}}, 'admin.senha'),
    ],
)
def test_criar_loja_valida_os_dados(cliente, sa, plano, extra, campo):
    _, h = sa
    resposta = cliente.post(URL, json={'plano_id': str(plano.id), **nova_loja(**extra)}, headers=h)
    assert resposta.status_code == 422
    assert campo in {e['campo'] for e in resposta.json()['erros']}


def test_slug_repetido_e_plano_inativo(cliente, engine_dono, sa, plano):
    _, h = sa
    criar(cliente, h, plano)
    resposta = cliente.post(URL, json={'plano_id': str(plano.id), **nova_loja()}, headers=h)
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'Este endereço de acesso já está em uso por outra loja.'

    inativo = criar_plano(engine_dono, 'Antigo', ativo=False)
    resposta = cliente.post(URL, json={'plano_id': str(inativo.id), **nova_loja(slug='outra')}, headers=h)
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == 'Este plano está inativo e não pode ser escolhido.'


# --- Lista e detalhe ----------------------------------------------------------------------------


def test_lista_com_filtros_e_paginacao(cliente, engine_dono, sa, plano):
    _, h = sa
    criar(cliente, h, plano)
    criar(
        cliente,
        h,
        plano,
        slug='escola-harmonia',
        nome_fantasia='Escola Harmonia',
        tipo='escola',
        cidade='Belo Horizonte',
        admin={'nome': 'Paula', 'email': 'paula@harmonia.com'},
    )
    criar_loja(engine_dono, 'clinica-suspensa', status=StatusLoja.suspensa)

    todas = cliente.get(URL, headers=h).json()
    assert todas['total'] == 3
    assert cliente.get(URL, params={'tipo': 'escola'}, headers=h).json()['total'] == 1
    assert (
        cliente.get(URL, params={'status': 'suspensa'}, headers=h).json()['itens'][0]['slug']
        == 'clinica-suspensa'
    )
    busca = cliente.get(URL, params={'busca': 'belo'}, headers=h).json()
    assert [i['slug'] for i in busca['itens']] == ['escola-harmonia']
    pagina = cliente.get(URL, params={'por_pagina': 2, 'pagina': 2}, headers=h).json()
    assert len(pagina['itens']) == 1
    assert pagina['total'] == 3

    opcoes = cliente.get(f'{URL}/opcoes', headers=h).json()
    assert len(opcoes) == 3


def test_detalhe_de_loja_inexistente(cliente, sa):
    _, h = sa
    resposta = cliente.get(f'{URL}/00000000-0000-0000-0000-000000000000', headers=h)
    assert resposta.status_code == 404
    assert resposta.json()['detail'] == 'Loja não encontrada.'


# --- Edição e situação --------------------------------------------------------------------------


def test_editar_loja_inclui_dados_da_plataforma(cliente, engine_dono, sa, plano):
    superadmin, h = sa
    loja = criar(cliente, h, plano)
    outro = criar_plano(engine_dono, 'Profissional', '189.90')
    corpo = {
        'plano_id': str(outro.id),
        **{k: v for k, v in nova_loja().items() if k not in ('admin', 'modulos')},
        'tipo': 'clinica',
        'slug': 'navalha-centro',
        'fuso_horario': 'America/Manaus',
        'status': 'suspensa',
    }
    resposta = cliente.put(f'{URL}/{loja["id"]}', json=corpo, headers=h)
    assert resposta.status_code == 200, resposta.json()
    dados = resposta.json()
    assert (dados['tipo'], dados['slug'], dados['plano_nome'], dados['fuso_horario'], dados['status']) == (
        'clinica',
        'navalha-centro',
        'Profissional',
        'America/Manaus',
        'suspensa',
    )
    linha = consultar(
        engine_dono,
        'SELECT atualizado_por_superadmin, atualizado_por_funcionario FROM lojas WHERE id = :l',
        l=loja['id'],
    )[0]
    assert linha == {'atualizado_por_superadmin': superadmin.id, 'atualizado_por_funcionario': None}


def test_suspender_bloqueia_o_painel_e_reativar_libera(cliente, sa, plano):
    _, h = sa
    loja = criar(cliente, h, plano, admin={'nome': 'M', 'email': 'm@navalha.com', 'senha': 'segredo123'})
    token = login_loja(cliente, 'barbearia-navalha', 'm@navalha.com', 'segredo123')

    resposta = cliente.post(f'{URL}/{loja["id"]}/status', json={'status': 'suspensa'}, headers=h)
    assert resposta.json()['status'] == 'suspensa'
    assert cliente.get('/api/loja/eu', headers=token).status_code == 403
    login = cliente.post(
        '/api/loja/auth/login',
        json={'slug': 'barbearia-navalha', 'email': 'm@navalha.com', 'senha': 'segredo123'},
    )
    assert login.status_code == 403

    cliente.post(f'{URL}/{loja["id"]}/status', json={'status': 'ativa'}, headers=h)
    assert cliente.get('/api/loja/eu', headers=token).status_code == 200

    invalido = cliente.post(f'{URL}/{loja["id"]}/status', json={'status': 'fechada'}, headers=h)
    assert invalido.status_code == 422


def test_excluir_so_loja_cancelada_e_libera_o_slug(cliente, engine_dono, sa, plano):
    superadmin, h = sa
    loja = criar(cliente, h, plano)
    resposta = cliente.delete(f'{URL}/{loja["id"]}', headers=h)
    assert resposta.status_code == 409

    cliente.post(f'{URL}/{loja["id"]}/status', json={'status': 'cancelada'}, headers=h)
    assert cliente.delete(f'{URL}/{loja["id"]}', headers=h).status_code == 204
    assert cliente.get(f'{URL}/{loja["id"]}', headers=h).status_code == 404
    assert cliente.get(URL, headers=h).json()['total'] == 0

    linha = consultar(engine_dono, 'SELECT excluido_em, excluido_por FROM lojas WHERE id = :l', l=loja['id'])[
        0
    ]
    assert linha['excluido_em'] is not None
    assert linha['excluido_por'] == superadmin.id
    excluir = consultar(
        engine_dono,
        "SELECT superadmin_id FROM auditoria WHERE tabela = 'lojas' AND operacao = 'excluir' AND loja_id = :l",
        l=loja['id'],
    )
    assert excluir == [{'superadmin_id': superadmin.id}]

    # O endereço volta a ficar livre
    criar(cliente, h, plano, admin={'nome': 'Novo', 'email': 'novo@navalha.com'})


# --- Módulos ------------------------------------------------------------------------------------


def test_modulos_ligar_desligar_observacao_e_prazo(cliente, engine_dono, sa, plano):
    superadmin, h = sa
    loja = criar(cliente, h, plano, admin={'nome': 'M', 'email': 'm@navalha.com', 'senha': 'segredo123'})
    token = login_loja(cliente, 'barbearia-navalha', 'm@navalha.com', 'segredo123')

    modulos = {m['codigo']: m for m in cliente.get(f'{URL}/{loja["id"]}/modulos', headers=h).json()}
    assert len(modulos) == 9
    assert modulos['agenda']['opcional'] is False
    assert modulos['agenda']['ativo'] is True
    assert modulos['locais']['ativo'] is True
    assert modulos['materiais']['ativo'] is False

    url = f'{URL}/{loja["id"]}/modulos'
    resposta = cliente.patch(f'{url}/locais', json={'habilitado': False}, headers=h)
    assert resposta.status_code == 200
    assert resposta.json()['ativo'] is False
    assert resposta.json()['atualizado_por_nome'] == 'Admin'
    assert cliente.get('/api/loja/eu', headers=token).json()['modulos']['locais'] is False

    # Só a observação: não mexe no resto
    resposta = cliente.patch(
        f'{url}/materiais', json={'observacao': 'Cortesia até dez/2030'}, headers=h
    ).json()
    assert (resposta['observacao'], resposta['habilitado']) == ('Cortesia até dez/2030', False)
    resposta = cliente.patch(
        f'{url}/materiais', json={'habilitado': True, 'expira_em': '2030-12-31T23:59'}, headers=h
    ).json()
    assert resposta['ativo'] is True
    assert resposta['expira_em'].startswith('2030-12-31T23:59:00-03:00')

    # Prazo vencido = módulo desativado
    vencido = cliente.patch(f'{url}/materiais', json={'expira_em': '2020-01-01T00:00'}, headers=h).json()
    assert (vencido['habilitado'], vencido['ativo']) == (True, False)
    assert cliente.get('/api/loja/eu', headers=token).json()['modulos']['materiais'] is False
    sem_prazo = cliente.patch(f'{url}/materiais', json={'expira_em': None}, headers=h).json()
    assert sem_prazo['ativo'] is True

    assert cliente.patch(f'{url}/agenda', json={'habilitado': False}, headers=h).status_code == 422
    assert cliente.patch(f'{url}/inexistente', json={'habilitado': False}, headers=h).status_code == 404
    assert cliente.patch(f'{url}/locais', json={'habilitado': None}, headers=h).status_code == 422

    auditoria = consultar(
        engine_dono,
        "SELECT superadmin_id, campos_alterados FROM auditoria WHERE tabela = 'loja_funcionalidades'"
        " AND operacao = 'alterar' AND loja_id = :l ORDER BY id LIMIT 1",
        l=loja['id'],
    )[0]
    assert auditoria['superadmin_id'] == superadmin.id
    assert 'habilitado' in auditoria['campos_alterados']


# --- Funcionários pelo suporte ------------------------------------------------------------------


@pytest.fixture
def duas_lojas(engine_dono):
    return criar_loja_teste(engine_dono, 'loja-a'), criar_loja_teste(engine_dono, 'loja-b')


def test_lista_funcionarios_e_perfis_so_da_loja(cliente, sa, duas_lojas):
    _, h = sa
    a, b = duas_lojas
    funcionarios = cliente.get(f'{URL}/{a.loja.id}/funcionarios', headers=h).json()
    assert {f['email'] for f in funcionarios} == {
        'admin@loja-a.com',
        'recepcao@loja-a.com',
        'prof@loja-a.com',
    }
    perfis = cliente.get(f'{URL}/{a.loja.id}/perfis', headers=h).json()
    assert perfis[0]['nome'] == 'Administrador'
    assert {p['id'] for p in perfis} == {str(p.id) for p in a.perfis.values()}
    assert not {p['id'] for p in perfis} & {str(p.id) for p in b.perfis.values()}


def test_criar_funcionario_pelo_suporte(cliente, engine_dono, sa, duas_lojas):
    superadmin, h = sa
    a, b = duas_lojas
    url = f'{URL}/{a.loja.id}/funcionarios'

    # Perfil de outra loja não serve
    corpo = {'nome': 'Novo', 'email': 'novo@loja-a.com', 'perfil_id': str(b.perfis['Administrador'].id)}
    assert cliente.post(url, json=corpo, headers=h).status_code == 422

    corpo['perfil_id'] = str(a.perfis['Administrador'].id)
    resposta = cliente.post(url, json=corpo, headers=h)
    assert resposta.status_code == 201
    novo = resposta.json()
    assert novo['criado_por'] == 'superadmin'
    assert novo['perfil_acesso_total'] is True
    login_loja(cliente, 'loja-a', 'novo@loja-a.com', novo['senha_provisoria'])

    repetido = cliente.post(url, json={**corpo, 'email': 'NOVO@loja-a.com'}, headers=h)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um funcionário com este e-mail.'

    auditoria = consultar(
        engine_dono,
        "SELECT origem::text AS origem, superadmin_id, funcionario_id FROM auditoria WHERE tabela = 'funcionarios'"
        " AND operacao = 'inserir' AND registro_id = :r",
        r=novo['id'],
    )
    assert auditoria == [{'origem': 'superadmin', 'superadmin_id': superadmin.id, 'funcionario_id': None}]


def test_editar_funcionario_pelo_suporte_grava_contexto_de_superadmin(cliente, engine_dono, sa, duas_lojas):
    superadmin, h = sa
    a, _ = duas_lojas
    url = f'{URL}/{a.loja.id}/funcionarios/{a.prof.id}'
    corpo = {
        'nome': 'Profissional Editado',
        'email': 'prof@loja-a.com',
        'perfil_id': str(a.perfis['Recepção'].id),
        'ativo': True,
    }
    resposta = cliente.put(url, json=corpo, headers=h)
    assert resposta.status_code == 200
    assert resposta.json()['perfil_nome'] == 'Recepção'

    linha = consultar(
        engine_dono, 'SELECT atualizado_por, nome FROM funcionarios WHERE id = :f', f=a.prof.id
    )[0]
    assert linha == {'atualizado_por': None, 'nome': 'Profissional Editado'}
    alteracao = consultar(
        engine_dono,
        'SELECT superadmin_id, funcionario_id, origem::text AS origem, campos_alterados FROM auditoria'
        " WHERE tabela = 'funcionarios' AND operacao = 'alterar' AND registro_id = :r",
        r=str(a.prof.id),
    )
    assert alteracao == [
        {
            'superadmin_id': superadmin.id,
            'funcionario_id': None,
            'origem': 'superadmin',
            'campos_alterados': ['nome', 'perfil_id'],
        }
    ]


def test_nao_deixa_a_loja_sem_administrador(cliente, sa, duas_lojas):
    _, h = sa
    a, _ = duas_lojas
    url = f'{URL}/{a.loja.id}/funcionarios/{a.admin.id}'
    corpo = {'nome': 'Admin', 'email': 'admin@loja-a.com', 'perfil_id': str(a.perfis['Administrador'].id)}
    resposta = cliente.put(url, json={**corpo, 'ativo': False}, headers=h)
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'A loja precisa de pelo menos um Administrador ativo.'
    resposta = cliente.put(url, json={**corpo, 'perfil_id': str(a.perfis['Recepção'].id)}, headers=h)
    assert resposta.status_code == 409


def test_redefinir_senha_pelo_suporte(cliente, engine_dono, sa, duas_lojas):
    superadmin, h = sa
    a, _ = duas_lojas
    url = f'{URL}/{a.loja.id}/funcionarios/{a.prof.id}/redefinir-senha'

    resposta = cliente.post(url, json={}, headers=h)
    assert resposta.status_code == 200
    provisoria = resposta.json()['senha_provisoria']
    assert provisoria
    login_loja(cliente, 'loja-a', 'prof@loja-a.com', provisoria)
    antiga = cliente.post(
        '/api/loja/auth/login', json={'slug': 'loja-a', 'email': 'prof@loja-a.com', 'senha': SENHA}
    )
    assert antiga.status_code == 401

    informada = cliente.post(url, json={'senha': 'nova-senha-1'}, headers=h).json()
    assert informada['senha_provisoria'] is None
    login_loja(cliente, 'loja-a', 'prof@loja-a.com', 'nova-senha-1')

    registros = consultar(
        engine_dono,
        "SELECT superadmin_id, campos_alterados, antes ? 'senha_hash' AS vazou FROM auditoria"
        " WHERE tabela = 'funcionarios' AND registro_id = :r AND superadmin_id IS NOT NULL",
        r=str(a.prof.id),
    )
    assert len(registros) == 2
    assert all(r['campos_alterados'] == ['senha_hash'] and not r['vazou'] for r in registros)
    assert all(r['superadmin_id'] == superadmin.id for r in registros)


def test_funcionario_de_outra_loja_responde_404(cliente, sa, duas_lojas):
    _, h = sa
    a, b = duas_lojas
    corpo = {'nome': 'X', 'email': 'x@loja-b.com', 'perfil_id': str(b.perfis['Recepção'].id)}
    # Funcionário da loja B pelo endereço da loja A
    assert (
        cliente.put(f'{URL}/{a.loja.id}/funcionarios/{b.prof.id}', json=corpo, headers=h).status_code == 404
    )
    resposta = cliente.post(f'{URL}/{a.loja.id}/funcionarios/{b.prof.id}/redefinir-senha', json={}, headers=h)
    assert resposta.status_code == 404
    assert resposta.json()['detail'] == 'Funcionário não encontrado.'
    # Nada mudou na loja B
    assert (
        cliente.get('/api/loja/eu', headers=cabecalho(b.prof)).json()['funcionario']['nome'] == 'Profissional'
    )
