"""Regras que valem para todas as rotas do painel da loja, e as rotas com os dados do seed."""

import re
from datetime import date

import pytest

from app.main import app
from app.models.enums import StatusLoja
from scripts import seed
from tests.fabricas import (
    cabecalho,
    criar_funcionario,
    criar_loja,
    criar_superadmin,
    login_loja,
    login_superadmin,
)

PUBLICAS = {('POST', '/api/loja/auth/login')}
UUID_FALSO = '00000000-0000-0000-0000-000000000000'


def _rotas_da_loja():
    for caminho, operacoes in app.openapi()['paths'].items():
        if caminho.startswith('/api/loja'):
            for metodo in operacoes:
                if (metodo.upper(), caminho) not in PUBLICAS:
                    yield metodo.upper(), re.sub(r'\{[^}]+\}', UUID_FALSO, caminho)


ROTAS = sorted(_rotas_da_loja())


def test_ha_rotas_para_todos_os_menus():
    caminhos = {c for _, c in ROTAS}
    for prefixo in (
        'clientes',
        'funcionarios',
        'cargos',
        'perfis',
        'horarios',
        'bloqueios',
        'recursos',
        'servicos',
        'locais',
        'materiais',
        'categorias-material',
        'agendamentos',
        'agenda',
        'apoio',
        'ponto',
        'configuracoes',
        'inicio',
    ):
        assert any(c.startswith(f'/api/loja/{prefixo}') for c in caminhos), prefixo


@pytest.mark.parametrize(('metodo', 'caminho'), ROTAS)
def test_toda_rota_exige_token_de_funcionario(cliente, metodo, caminho, engine_dono):
    assert cliente.request(metodo, caminho).status_code == 401
    criar_superadmin(engine_dono)
    superadmin = login_superadmin(cliente, 'admin@plataforma.com')
    assert cliente.request(metodo, caminho, headers=superadmin).status_code == 401


@pytest.mark.parametrize(('metodo', 'caminho'), ROTAS)
def test_loja_suspensa_nao_acessa_nenhuma_rota(cliente, metodo, caminho, engine_dono):
    loja, perfis = criar_loja(engine_dono, 'suspensa', status=StatusLoja.suspensa)
    admin = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@suspensa.com')
    resposta = cliente.request(metodo, caminho, headers=cabecalho(admin))
    assert resposta.status_code == 403
    assert resposta.json()['detail'] == 'Esta loja está suspensa. Fale com o suporte da plataforma.'


def test_rotas_de_leitura_com_os_dados_do_seed(cliente, engine_app):
    seed.executar(engine_app)
    admin = login_loja(cliente, 'clinica-sorriso', 'ana@clinica.com', seed.SENHA_FUNCIONARIO)
    hoje = date.today().isoformat()
    for caminho, params in (
        ('/api/loja/inicio', {}),
        ('/api/loja/clientes', {}),
        ('/api/loja/funcionarios', {}),
        ('/api/loja/cargos', {}),
        ('/api/loja/perfis', {}),
        ('/api/loja/recursos', {}),
        ('/api/loja/horarios', {}),
        ('/api/loja/bloqueios', {}),
        ('/api/loja/servicos', {}),
        ('/api/loja/locais', {}),
        ('/api/loja/locais/rotulos', {}),
        ('/api/loja/materiais', {}),
        ('/api/loja/categorias-material', {}),
        ('/api/loja/agendamentos', {}),
        ('/api/loja/agenda', {'inicio': hoje}),
        ('/api/loja/apoio/agendamento', {}),
        ('/api/loja/ponto', {}),
        ('/api/loja/configuracoes/loja', {}),
    ):
        resposta = cliente.get(caminho, params=params, headers=admin)
        assert resposta.status_code == 200, (caminho, resposta.json())
    agendamentos = cliente.get('/api/loja/agendamentos', headers=admin).json()
    assert agendamentos['total'] == 10
    primeiro = agendamentos['itens'][0]['id']
    assert cliente.get(f'/api/loja/agendamentos/{primeiro}', headers=admin).status_code == 200
    resumo = cliente.get('/api/loja/inicio', headers=admin).json()
    assert len(resumo['solicitacoes_site']) == 1
    assert resumo['clientes_cadastrados'] == 3
    assert cliente.get('/api/loja/locais/rotulos', headers=admin).json()['rotulo_local'] == 'Consultório'
