"""Nível efetivo (perfil + módulo ligado + status da loja), /api/loja/eu e exigir()."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.auth.dependencias import ContextoLoja, exigir
from app.main import criar_app
from app.models import PerfilAcesso, Recurso
from app.models.enums import NivelAcesso
from tests.fabricas import criar_funcionario, criar_loja, login_loja, mudar_modulo, sessao

TODOS_ESCRITA = {
    'agenda_propria': 'escrita',
    'agenda_equipe': 'escrita',
    'config_agendamentos': 'escrita',
    'clientes': 'escrita',
    'funcionarios': 'escrita',
    'perfis_acesso': 'escrita',
    'servicos': 'escrita',
    'materiais': 'escrita',
    'locais': 'escrita',
    'ponto_proprio': 'escrita',
    'ponto_equipe': 'escrita',
    'config_loja': 'escrita',
}


@pytest.fixture
def loja(engine_dono):
    loja, perfis = criar_loja(engine_dono, 'loja-a')
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@a.com')
    criar_funcionario(engine_dono, loja, perfis['Recepção'], 'recepcao@a.com')
    criar_funcionario(engine_dono, loja, perfis['Profissional'], 'prof@a.com')
    return loja, perfis


def _eu(cliente, email, slug='loja-a'):
    resposta = cliente.get('/api/loja/eu', headers=login_loja(cliente, slug, email))
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


# --- /api/loja/eu -------------------------------------------------------------------------------


def test_eu_do_administrador_tem_escrita_em_tudo(cliente, loja):
    eu = _eu(cliente, 'admin@a.com')
    assert eu['perfil']['nome'] == 'Administrador'
    assert eu['perfil']['acesso_total'] is True
    assert eu['acessos'] == TODOS_ESCRITA
    assert all(eu['modulos'].values())
    assert eu['loja']['slug'] == 'loja-a'
    assert eu['funcionario']['email'] == 'admin@a.com'
    assert 'senha_hash' not in eu['funcionario']


def test_eu_dos_perfis_padrao_segue_o_estrutura(cliente, loja):
    recepcao = _eu(cliente, 'recepcao@a.com')['acessos']
    assert recepcao == {
        **dict.fromkeys(TODOS_ESCRITA, 'nenhum'),
        'agenda_propria': 'escrita',
        'agenda_equipe': 'escrita',
        'config_agendamentos': 'leitura',
        'clientes': 'escrita',
        'servicos': 'leitura',
        'locais': 'leitura',
        'ponto_proprio': 'escrita',
    }
    profissional = _eu(cliente, 'prof@a.com')['acessos']
    assert profissional == {
        **dict.fromkeys(TODOS_ESCRITA, 'nenhum'),
        'agenda_propria': 'escrita',
        'clientes': 'leitura',
        'ponto_proprio': 'escrita',
    }


def test_modulo_desligado_zera_o_acesso_ate_do_administrador(cliente, engine_dono, loja):
    loja, _ = loja
    mudar_modulo(engine_dono, loja.id, 'materiais', habilitado=False)
    eu = _eu(cliente, 'admin@a.com')
    assert eu['modulos']['materiais'] is False
    assert eu['acessos']['materiais'] == 'nenhum'
    assert eu['acessos']['servicos'] == 'escrita'


def test_modulo_vencido_conta_como_desligado(cliente, engine_dono, loja):
    loja, _ = loja
    mudar_modulo(engine_dono, loja.id, 'locais', expira_em=datetime.now(UTC) - timedelta(minutes=1))
    mudar_modulo(engine_dono, loja.id, 'servicos', expira_em=datetime.now(UTC) + timedelta(days=30))
    eu = _eu(cliente, 'recepcao@a.com')
    assert eu['modulos']['locais'] is False
    assert eu['acessos']['locais'] == 'nenhum'
    assert eu['modulos']['servicos'] is True
    assert eu['acessos']['servicos'] == 'leitura'


def test_modulo_sem_registro_na_loja_conta_como_desligado(cliente, engine_dono):
    loja, perfis = criar_loja(engine_dono, 'loja-sem-modulos', modulos={})
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@s.com')
    eu = _eu(cliente, 'admin@s.com', 'loja-sem-modulos')
    assert eu['modulos'] == {
        'inicio': True,
        'agenda': True,
        'clientes': True,
        'funcionarios': True,
        'configuracoes': True,
        'servicos': False,
        'materiais': False,
        'controle_tempo': False,
        'locais': False,
    }
    assert eu['acessos']['ponto_proprio'] == 'nenhum'


def test_recurso_sem_linha_no_perfil_e_nenhum(cliente, engine_dono, loja):
    loja, perfis = loja
    with sessao(engine_dono) as db:
        recurso_id = db.scalar(select(Recurso.id).where(Recurso.codigo == 'clientes'))
        db.execute(
            text('DELETE FROM perfil_acessos WHERE perfil_id = :p AND recurso_id = :r'),
            {'p': perfis['Profissional'].id, 'r': recurso_id},
        )
    assert _eu(cliente, 'prof@a.com')['acessos']['clientes'] == 'nenhum'


def test_eu_nao_mostra_dados_de_outra_loja(cliente, engine_dono, loja):
    loja_b, perfis_b = criar_loja(engine_dono, 'loja-b')
    criar_funcionario(engine_dono, loja_b, perfis_b['Administrador'], 'admin@b.com', nome='Admin B')
    eu_a = _eu(cliente, 'admin@a.com')
    eu_b = _eu(cliente, 'admin@b.com', 'loja-b')
    assert eu_a['loja']['id'] == str(loja[0].id)
    assert eu_b['loja']['id'] == str(loja_b.id)
    assert eu_a['perfil']['id'] != eu_b['perfil']['id']


# --- exigir(recurso, nivel) ---------------------------------------------------------------------


@pytest.fixture
def cliente_exigir():
    """App com rotas de teste protegidas por exigir()."""
    router = APIRouter(prefix='/api/loja/teste')

    @router.get('/clientes')
    def ler_clientes(ctx: ContextoLoja = Depends(exigir('clientes'))):
        return {'loja_id': str(ctx.loja_id)}

    @router.post('/clientes')
    def gravar_clientes(ctx: ContextoLoja = Depends(exigir('clientes', 'escrita'))):
        return {'ok': True}

    @router.post('/materiais')
    def gravar_materiais(ctx: ContextoLoja = Depends(exigir('materiais', NivelAcesso.escrita))):
        return {'ok': True}

    @router.get('/agenda')
    def ver_agenda(ctx: ContextoLoja = Depends(exigir(('agenda_propria', 'agenda_equipe')))):
        return {'ok': True}

    @router.get('/funcionarios')
    def ler_funcionarios(ctx: ContextoLoja = Depends(exigir('funcionarios'))):
        return {'ok': True}

    app = criar_app()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_exigir_libera_quem_tem_o_nivel(cliente_exigir, loja):
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'recepcao@a.com')
    resposta = cliente_exigir.get('/api/loja/teste/clientes', headers=cabecalho)
    assert resposta.status_code == 200
    assert resposta.json() == {'loja_id': str(loja[0].id)}
    assert cliente_exigir.post('/api/loja/teste/clientes', headers=cabecalho).status_code == 200


def test_exigir_recusa_escrita_para_quem_so_le(cliente_exigir, loja):
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'prof@a.com')
    assert cliente_exigir.get('/api/loja/teste/clientes', headers=cabecalho).status_code == 200
    resposta = cliente_exigir.post('/api/loja/teste/clientes', headers=cabecalho)
    assert resposta.status_code == 403
    assert resposta.json() == {'detail': 'Você só tem permissão de leitura aqui.'}


def test_exigir_recusa_nivel_nenhum(cliente_exigir, loja):
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'prof@a.com')
    resposta = cliente_exigir.get('/api/loja/teste/funcionarios', headers=cabecalho)
    assert resposta.status_code == 403
    assert resposta.json() == {'detail': 'Você não tem permissão para acessar esta área.'}


def test_exigir_aceita_qualquer_um_dos_recursos(cliente_exigir, loja):
    # Profissional só tem agenda_propria; Recepção tem as duas
    for email in ('prof@a.com', 'recepcao@a.com'):
        cabecalho = login_loja(cliente_exigir, 'loja-a', email)
        assert cliente_exigir.get('/api/loja/teste/agenda', headers=cabecalho).status_code == 200


def test_exigir_recusa_modulo_desligado_ate_para_o_administrador(cliente_exigir, engine_dono, loja):
    mudar_modulo(engine_dono, loja[0].id, 'materiais', habilitado=False)
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'admin@a.com')
    resposta = cliente_exigir.post('/api/loja/teste/materiais', headers=cabecalho)
    assert resposta.status_code == 403
    assert resposta.json() == {'detail': 'Este módulo não está ativo na sua loja.'}


def test_exigir_reflete_mudanca_de_nivel_sem_novo_login(cliente_exigir, engine_dono, loja):
    _, perfis = loja
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'prof@a.com')
    assert cliente_exigir.post('/api/loja/teste/clientes', headers=cabecalho).status_code == 403
    with sessao(engine_dono) as db:
        recurso_id = db.scalar(select(Recurso.id).where(Recurso.codigo == 'clientes'))
        acesso = db.get(PerfilAcesso, (perfis['Profissional'].id, recurso_id))
        acesso.nivel = NivelAcesso.escrita
    assert cliente_exigir.post('/api/loja/teste/clientes', headers=cabecalho).status_code == 200


def test_exigir_recusa_loja_suspensa(cliente_exigir, engine_dono, loja):
    cabecalho = login_loja(cliente_exigir, 'loja-a', 'admin@a.com')
    with sessao(engine_dono) as db:
        db.execute(text("UPDATE lojas SET status = 'suspensa' WHERE id = :id"), {'id': loja[0].id})
    assert cliente_exigir.get('/api/loja/teste/clientes', headers=cabecalho).status_code == 403


def test_exigir_com_recurso_desconhecido_falha_ao_montar_a_rota():
    with pytest.raises(ValueError, match='Recurso desconhecido'):
        exigir('agendamentos', 'escrita')
