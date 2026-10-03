"""Validação de entrada: CPF e telefone canônicos (A7), valores extremos sem 500 (A8) e limites de
texto e de lista (A12). SEG-10, SEG-12, LOG-10.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.clinica import SEGUNDA
from tests.fabricas import cabecalho_superadmin, criar_superadmin

API = '/api/loja'
MSG_FAIXA = 'Informe uma data entre 2000 e 2100.'


@pytest.fixture
def sem_excecao():
    """Cliente que devolve o 500 em vez de levantar a exceção (para provar que não há 500)."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _cliente(**extra):
    return {'nome': 'Ana', 'sobrenome': 'Lima', 'telefone': '(11) 98888-1111', **extra}


def _erros(resposta) -> dict[str, str]:
    return {e['campo']: e['mensagem'] for e in resposta.json()['erros']}


# --- A7: CPF, telefone e nascimento ------------------------------------------------------------------


def test_cpf_com_e_sem_mascara_colidem_e_sao_gravados_iguais(cliente, lojas):
    a, _ = lojas
    com_mascara = cliente.post(f'{API}/clientes', json=_cliente(cpf='529.982.247-25'), headers=a.h_admin)
    assert com_mascara.status_code == 201
    assert com_mascara.json()['cpf'] == '529.982.247-25'
    sem_mascara = cliente.post(
        f'{API}/clientes',
        json=_cliente(nome='Bia', cpf='52998224725', telefone='11977776666'),
        headers=a.h_admin,
    )
    assert sem_mascara.status_code == 409
    assert sem_mascara.json()['detail'] == 'Já existe um cliente com este CPF.'


@pytest.mark.parametrize('cpf', ['xyz', '123', '529.982.247-26', '111.111.111-11', '5299822472'])
def test_cpf_invalido_e_recusado(cliente, lojas, cpf):
    a, _ = lojas
    resposta = cliente.post(f'{API}/clientes', json=_cliente(cpf=cpf), headers=a.h_admin)
    assert resposta.status_code == 422
    assert _erros(resposta) == {'cpf': 'CPF inválido.'}


@pytest.mark.parametrize('telefone', ['abc', '1', '1234567', '(01) 98888-1111', '119888811112'])
def test_telefone_invalido_e_recusado(cliente, lojas, telefone):
    a, _ = lojas
    resposta = cliente.post(f'{API}/clientes', json=_cliente(telefone=telefone), headers=a.h_admin)
    assert resposta.status_code == 422
    assert _erros(resposta) == {'telefone': 'Informe o telefone com DDD (ex.: (11) 99999-9999).'}


@pytest.mark.parametrize(
    ('enviado', 'gravado'),
    [
        ('11988881111', '(11) 98888-1111'),
        ('(21) 3222-1010', '(21) 3222-1010'),
        ('21 32221010', '(21) 3222-1010'),
    ],
)
def test_telefone_e_gravado_com_mascara(cliente, lojas, enviado, gravado):
    a, _ = lojas
    resposta = cliente.post(f'{API}/clientes', json=_cliente(telefone=enviado), headers=a.h_admin)
    assert resposta.status_code == 201
    assert resposta.json()['telefone'] == gravado


@pytest.mark.parametrize('nascimento', ['2999-01-01', '1800-05-10', '1899-12-31'])
def test_nascimento_no_futuro_ou_absurdo_e_recusado(cliente, lojas, nascimento):
    a, _ = lojas
    resposta = cliente.post(f'{API}/clientes', json=_cliente(data_nascimento=nascimento), headers=a.h_admin)
    assert resposta.status_code == 422
    assert 'data_nascimento' in _erros(resposta)


def test_nascimento_valido_ou_vazio(cliente, lojas):
    a, _ = lojas
    assert (
        cliente.post(
            f'{API}/clientes', json=_cliente(data_nascimento='1900-01-01'), headers=a.h_admin
        ).status_code
        == 201
    )
    vazio = cliente.post(
        f'{API}/clientes', json=_cliente(telefone='11977776666', data_nascimento=''), headers=a.h_admin
    )
    assert vazio.status_code == 201
    assert vazio.json()['data_nascimento'] is None


@pytest.mark.parametrize('fuso', ['Pacific/Pago_Pago', 'America/Sao_Paulo', 'Pacific/Kiritimati'])
def test_nascimento_usa_o_dia_de_hoje_no_fuso_da_loja(cliente, lojas, engine_dono, fuso):
    """LOG-05/GER-15: "hoje" é o dia da loja, não o do servidor nem o UTC.

    Pago Pago (UTC-11) fica até 11 h atrás do UTC (com "hoje" em UTC, aceitaria amanhã); Kiritimati
    (UTC+14) fica à frente (com "hoje" em UTC, recusaria quem nasceu hoje).
    """
    a, _ = lojas
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET fuso_horario = :f WHERE id = :i'), {'f': fuso, 'i': a.loja.id})
    hoje = datetime.now(ZoneInfo(fuso)).date()
    amanha = (hoje + timedelta(days=1)).isoformat()

    criado = cliente.post(
        f'{API}/clientes', json=_cliente(data_nascimento=hoje.isoformat()), headers=a.h_admin
    )
    assert criado.status_code == 201, criado.json()
    for resposta in (
        cliente.post(
            f'{API}/clientes',
            json=_cliente(telefone='11977776666', data_nascimento=amanha),
            headers=a.h_admin,
        ),
        cliente.put(
            f'{API}/clientes/{criado.json()["id"]}', json=_cliente(data_nascimento=amanha), headers=a.h_admin
        ),
    ):
        assert resposta.status_code == 422
        assert resposta.json()['erros'] == [
            {
                'campo': 'data_nascimento',
                'mensagem': 'Data de nascimento inválida (não pode ser no futuro nem antes de 1900).',
            }
        ]


def test_busca_de_clientes_acha_telefone_e_cpf_com_e_sem_mascara(cliente, lojas):
    a, _ = lojas
    cliente.post(
        f'{API}/clientes', json=_cliente(telefone='11988881111', cpf='52998224725'), headers=a.h_admin
    )
    cliente.post(f'{API}/clientes', json=_cliente(nome='Bia', telefone='(21) 3222-1010'), headers=a.h_admin)

    def nomes(busca):
        resposta = cliente.get(f'{API}/clientes', params={'busca': busca}, headers=a.h_admin)
        return [c['nome'] for c in resposta.json()['itens']]

    for busca in ('11988881111', '(11) 98888-1111', '98888-1111', '529.982.247-25', '52998224725'):
        assert nomes(busca) == ['Ana'], busca
    assert nomes('2132221010') == ['Bia']
    assert nomes('Ana 1') == []  # texto com dígitos não vira busca por número


def test_site_reaproveita_o_cliente_cadastrado_no_painel(cliente, clinica, engine_dono):
    criado = cliente.post(
        f'{API}/clientes',
        json={'nome': 'Rita', 'sobrenome': 'Paz', 'telefone': '11966665555'},
        headers=clinica.lt.h_admin,
    ).json()
    pedido = {
        'servico_id': clinica.limpeza,
        'funcionario_id': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T14:00',
        'nome': 'Outro',
        'sobrenome': 'Nome',
        'telefone': '(11) 96666-5555',
    }
    assert cliente.post('/api/site/loja-a/agendamentos', json=pedido).status_code == 201
    with engine_dono.connect() as conexao:
        linhas = conexao.execute(
            text("SELECT id, nome, canais::text[] FROM clientes WHERE nome IN ('Rita', 'Outro')")
        ).all()
    assert len(linhas) == 1
    assert str(linhas[0].id) == criado['id']
    assert 'site' in linhas[0].canais


def test_funcionario_valida_cpf_e_telefone(cliente, lojas, engine_dono):
    a, _ = lojas
    base = {
        'nome': 'Bia',
        'email': 'bia@loja-a.com',
        'perfil_id': str(a.perfis['Profissional'].id),
        'senha': 'senha-forte-1',
    }
    invalido = cliente.post(
        f'{API}/funcionarios', json={**base, 'cpf': '123', 'telefone': 'abc'}, headers=a.h_admin
    )
    assert invalido.status_code == 422
    assert set(_erros(invalido)) == {'cpf', 'telefone'}
    criado = cliente.post(
        f'{API}/funcionarios',
        json={**base, 'cpf': '52998224725', 'telefone': '11988881111'},
        headers=a.h_admin,
    )
    assert criado.status_code == 201
    assert (criado.json()['cpf'], criado.json()['telefone']) == ('529.982.247-25', '(11) 98888-1111')
    repetido = cliente.post(
        f'{API}/funcionarios',
        json={**base, 'email': 'outra@loja-a.com', 'cpf': '529.982.247-25'},
        headers=a.h_admin,
    )
    assert repetido.status_code == 409
    # O suporte (superadmin) grava o telefone no mesmo formato
    h = cabecalho_superadmin(criar_superadmin(engine_dono))
    suporte = cliente.post(
        f'/api/superadmin/lojas/{a.loja.id}/funcionarios',
        json={'nome': 'Caio', 'email': 'caio@loja-a.com', 'perfil_id': base['perfil_id'], 'telefone': '1'},
        headers=h,
    )
    assert suporte.status_code == 422


# --- A8: valores extremos -----------------------------------------------------------------------------


def test_datas_fora_da_faixa_viram_422_e_nao_500(sem_excecao, clinica, engine_dono):
    h = clinica.lt.h_admin
    prof = str(clinica.lt.prof.id)
    pedidos = [
        ('GET', f'{API}/agendamentos', {'fim': '9999-12-31'}, None, 'fim'),
        ('GET', f'{API}/agenda', {'inicio': '9999-12-31'}, None, 'inicio'),
        ('GET', f'{API}/bloqueios', {'fim': '9999-12-31'}, None, 'fim'),
        ('GET', f'{API}/ponto', {'inicio': '9999-12-31'}, None, 'inicio'),
        (
            'GET',
            f'{API}/apoio/disponibilidade',
            {'funcionario_id': prof, 'inicio': '9999-12-31T23:30:00', 'duracao_minutos': 60},
            None,
            'inicio',
        ),
        ('POST', f'{API}/agendamentos', None, clinica.dados(inicio='9999-12-31T23:30'), 'inicio'),
        (
            'POST',
            f'{API}/bloqueios',
            None,
            {'inicio': '1999-12-31T08:00', 'fim': '2030-01-01T08:00'},
            'inicio',
        ),
        (
            'POST',
            f'{API}/ponto',
            None,
            {'funcionario_id': prof, 'entrada': '0001-01-01T08:00', 'justificativa': 'x'},
            'entrada',
        ),
    ]
    for metodo, url, params, corpo, campo in pedidos:
        resposta = sem_excecao.request(metodo, url, params=params, json=corpo, headers=h)
        assert resposta.status_code == 422, (url, resposta.status_code)
        assert _erros(resposta) == {campo: MSG_FAIXA}, url

    site = [
        ('GET', '/api/site/loja-a/horarios', {'servico_id': clinica.limpeza, 'inicio': '9999-12-31'}, None),
        (
            'POST',
            '/api/site/loja-a/agendamentos',
            None,
            {
                'servico_id': clinica.limpeza,
                'funcionario_id': prof,
                'inicio': '9999-12-31T09:00',
                'nome': 'A',
                'sobrenome': 'B',
                'telefone': '11999998888',
            },
        ),
    ]
    for metodo, url, params, corpo in site:
        resposta = sem_excecao.request(metodo, url, params=params, json=corpo)
        assert resposta.status_code == 422, url

    h_super = cabecalho_superadmin(criar_superadmin(engine_dono))
    auditoria = sem_excecao.get(
        '/api/superadmin/auditoria',
        params={
            'loja': str(clinica.lt.loja.id),
            'periodo': 'intervalo',
            'inicio': '2030-01-01',
            'fim': '9999-12-31',
        },
        headers=h_super,
    )
    assert auditoria.status_code == 422


def test_fronteiras_da_faixa_de_datas_sao_aceitas(cliente, lojas):
    a, _ = lojas
    for params in ({'inicio': '2000-01-01'}, {'fim': '2100-12-31'}):
        assert cliente.get(f'{API}/agendamentos', params=params, headers=a.h_admin).status_code == 200
    assert cliente.get(f'{API}/agenda', params={'inicio': '2100-12-31'}, headers=a.h_admin).status_code == 200


def test_pagina_tem_maximo(sem_excecao, lojas):
    a, _ = lojas
    assert sem_excecao.get(f'{API}/clientes', params={'pagina': 10**19}, headers=a.h_admin).status_code == 422
    assert sem_excecao.get(f'{API}/clientes', params={'pagina': 10001}, headers=a.h_admin).status_code == 422
    ultima = sem_excecao.get(f'{API}/clientes', params={'pagina': 10000}, headers=a.h_admin)
    assert ultima.status_code == 200
    assert ultima.json()['itens'] == []


def test_movimentacao_de_estoque_tem_maximo(cliente, lojas):
    a, _ = lojas
    grande = cliente.post(
        f'{API}/materiais', json={'nome': 'Gaze', 'quantidade_inicial': 99999999.99}, headers=a.h_admin
    )
    assert grande.status_code == 422
    material = cliente.post(
        f'{API}/materiais', json={'nome': 'Gaze', 'quantidade_inicial': 1000000}, headers=a.h_admin
    )
    assert material.status_code == 201
    url = f'{API}/materiais/{material.json()["id"]}/movimentacoes'
    acima = cliente.post(url, json={'tipo': 'entrada', 'quantidade': 1000000.01}, headers=a.h_admin)
    assert acima.status_code == 422
    perda = cliente.post(
        url, json={'tipo': 'perda', 'quantidade': 1000000.01, 'motivo': 'x'}, headers=a.h_admin
    )
    assert perda.status_code == 422


def _saldo_direto(engine, material_id, valor):
    """Põe o saldo direto no banco (sem triggers), para testar a fronteira do numeric(10,2)."""
    with engine.begin() as conexao:
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text('UPDATE materiais SET quantidade_atual = :v WHERE id = :i'), {'v': valor, 'i': material_id}
        )


def test_saldo_do_estoque_nao_estoura(sem_excecao, lojas, engine_dono):
    a, _ = lojas
    material = sem_excecao.post(f'{API}/materiais', json={'nome': 'Gaze'}, headers=a.h_admin).json()
    url = f'{API}/materiais/{material["id"]}/movimentacoes'
    _saldo_direto(engine_dono, material['id'], '99500000.00')
    estouro = sem_excecao.post(url, json={'tipo': 'entrada', 'quantidade': 500000}, headers=a.h_admin)
    assert estouro.status_code == 422
    assert (
        estouro.json()['detail']
        == 'Com esta movimentação o estoque passaria do limite permitido (99.999.999,99).'
    )
    no_limite = sem_excecao.post(url, json={'tipo': 'entrada', 'quantidade': 499999.99}, headers=a.h_admin)
    assert no_limite.status_code == 201
    assert (
        sem_excecao.get(f'{API}/materiais/{material["id"]}', headers=a.h_admin).json()['quantidade_atual']
        == 99999999.99
    )
    # Para baixo também (o estoque pode ficar negativo, mas não passar do limite)
    _saldo_direto(engine_dono, material['id'], '-99500000.00')
    perda = sem_excecao.post(
        url, json={'tipo': 'perda', 'quantidade': 500000, 'motivo': 'x'}, headers=a.h_admin
    )
    assert perda.status_code == 422


# --- A12: textos e listas com limite ------------------------------------------------------------------


def test_textos_livres_tem_tamanho_maximo(cliente, clinica):
    h = clinica.lt.h_admin
    longo, no_limite = 'x' * 2001, 'x' * 2000
    msg = 'Texto muito longo (máximo de 2000 caracteres).'

    resposta = cliente.post(f'{API}/clientes', json=_cliente(observacoes=longo), headers=h)
    assert _erros(resposta) == {'observacoes': msg}
    assert cliente.post(f'{API}/clientes', json=_cliente(observacoes=no_limite), headers=h).status_code == 201

    servico = {'nome': 'S', 'duracao_minutos': 30, 'funcionario_ids': [str(clinica.lt.admin.id)]}
    assert _erros(cliente.post(f'{API}/servicos', json={**servico, 'descricao': longo}, headers=h)) == {
        'descricao': msg
    }
    assert _erros(cliente.post(f'{API}/agendamentos', json=clinica.dados(observacoes=longo), headers=h)) == {
        'observacoes': msg
    }
    ag = cliente.post(f'{API}/agendamentos', json=clinica.dados(), headers=h).json()
    cancelar = cliente.post(
        f'{API}/agendamentos/{ag["id"]}/status',
        json={'status': 'cancelado', 'motivo_cancelamento': longo},
        headers=h,
    )
    assert _erros(cancelar) == {'motivo_cancelamento': msg}
    ponto = cliente.post(
        f'{API}/ponto',
        json={
            'funcionario_id': str(clinica.lt.prof.id),
            'entrada': '2026-01-05T08:00',
            'justificativa': longo,
        },
        headers=h,
    )
    assert _erros(ponto) == {'justificativa': msg}
    perfil = cliente.post(f'{API}/perfis', json={'nome': 'P', 'descricao': longo}, headers=h)
    assert _erros(perfil) == {'descricao': msg}
    local = cliente.post(f'{API}/locais', json={'nome': 'L', 'descricao': longo}, headers=h)
    assert _erros(local) == {'descricao': msg}


def test_listas_tem_quantidade_maxima(cliente, clinica, engine_dono):
    import uuid

    h = clinica.lt.h_admin
    ids = [str(uuid.uuid4()) for _ in range(201)]
    msg_lista = 'Itens demais (máximo de 200).'
    servico = cliente.post(
        f'{API}/servicos', json={'nome': 'S', 'duracao_minutos': 30, 'funcionario_ids': ids}, headers=h
    )
    assert servico.status_code == 422
    assert _erros(servico) == {'funcionario_ids': msg_lista}
    locais = cliente.post(
        f'{API}/servicos',
        json={'nome': 'S', 'duracao_minutos': 30, 'funcionario_ids': ids[:1], 'local_ids': ids},
        headers=h,
    )
    assert 'local_ids' in _erros(locais)
    materiais = [{'material_id': i, 'quantidade': 1} for i in ids]
    ag = cliente.post(f'{API}/agendamentos', json=clinica.dados(), headers=h).json()
    ajuste = cliente.put(f'{API}/agendamentos/{ag["id"]}/materiais', json={'materiais': materiais}, headers=h)
    assert ajuste.status_code == 422
    assert 'materiais' in _erros(ajuste)
    acessos = {f'recurso_{i}': 'leitura' for i in range(201)}
    perfil = cliente.post(f'{API}/perfis', json={'nome': 'P'}, headers=h).json()
    resposta = cliente.put(f'{API}/perfis/{perfil["id"]}/acessos', json={'acessos': acessos}, headers=h)
    assert resposta.status_code == 422
    assert 'acessos' in _erros(resposta)
    canais = cliente.post(f'{API}/clientes', json=_cliente(canais=['loja'] * 11), headers=h)
    assert 'canais' in _erros(canais)
    h_super = cabecalho_superadmin(criar_superadmin(engine_dono))
    loja = cliente.post('/api/superadmin/lojas', json={'modulos': ['servicos'] * 201}, headers=h_super)
    assert 'modulos' in _erros(loja)
