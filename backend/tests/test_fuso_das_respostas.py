"""GER-15: toda data/hora das rotas da loja sai no fuso da loja (nunca em UTC), de forma central.

O contexto da transação (app.db.definir_contexto) troca o TimeZone da sessão do Postgres para o fuso
da loja; os testes varrem as respostas das rotas de leitura procurando qualquer data/hora.
"""

import re

from sqlalchemy import text

from app.db import definir_contexto, get_sessionmaker
from app.models import Loja
from tests.clinica import SEGUNDA
from tests.fabricas import SENHA, cabecalho_superadmin, criar_superadmin, login_loja, sessao

MOMENTO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')


def _momentos(valor) -> list[str]:
    """Todas as datas/horas (texto ISO com hora) dentro de um JSON."""
    if isinstance(valor, dict):
        return [m for v in valor.values() for m in _momentos(v)]
    if isinstance(valor, list):
        return [m for v in valor for m in _momentos(v)]
    return [valor] if isinstance(valor, str) and MOMENTO.match(valor) else []


def _rotas(clinica, agendamento: str) -> list[str]:
    lt = clinica.lt
    return [
        '/eu',
        '/inicio',
        '/clientes',
        f'/clientes/{clinica.maria}',
        f'/clientes/{clinica.maria}/historico',
        '/funcionarios',
        f'/funcionarios/{lt.prof.id}',
        '/cargos',
        '/perfis',
        f'/perfis/{lt.perfis["Profissional"].id}',
        '/horarios',
        '/bloqueios',
        '/servicos',
        f'/servicos/{clinica.limpeza}',
        '/locais',
        f'/locais/{clinica.sala1}',
        '/materiais',
        f'/materiais/{clinica.luvas}',
        f'/materiais/{clinica.luvas}/movimentacoes',
        '/categorias-material',
        '/agendamentos',
        f'/agendamentos/{agendamento}',
        f'/agenda?inicio={SEGUNDA}&fim=2030-01-13',
        '/ponto',
        '/ponto/aberto',
        '/configuracoes/loja',
    ]


def test_rotas_da_loja_respondem_no_fuso_da_loja(cliente, clinica):
    h = clinica.lt.h_admin
    criado = cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=h)
    assert criado.status_code == 201, criado.json()
    assert criado.json()['inicio'] == f'{SEGUNDA}T09:00:00-03:00'
    bloqueio = {'inicio': '2030-01-08T10:00', 'fim': '2030-01-08T11:00', 'motivo': 'Reunião'}
    assert cliente.post('/api/loja/bloqueios', json=bloqueio, headers=h).status_code == 201
    assert cliente.post('/api/loja/cargos', json={'nome': 'Dentista'}, headers=h).status_code == 201
    ponto = cliente.post('/api/loja/ponto/registrar', json={'acao': 'entrada'}, headers=h)
    assert ponto.status_code == 200, ponto.json()

    encontrados = []
    for rota in _rotas(clinica, criado.json()['id']):
        resposta = cliente.get(f'/api/loja{rota}', headers=h)
        assert resposta.status_code == 200, (rota, resposta.json())
        momentos = _momentos(resposta.json())
        assert all(m.endswith('-03:00') for m in momentos), (rota, momentos)
        encontrados += momentos
    assert len(encontrados) > 50


def test_cada_loja_no_seu_fuso(cliente, lojas, engine_dono):
    a, b = lojas
    with sessao(engine_dono) as db:
        db.get(Loja, b.loja.id).fuso_horario = 'America/Manaus'
    corpo = {'nome': 'Ana', 'sobrenome': 'Lima', 'telefone': '(92) 98888-1111'}
    em_b = cliente.post('/api/loja/clientes', json=corpo, headers=b.h_admin).json()
    em_a = cliente.post('/api/loja/clientes', json=corpo, headers=a.h_admin).json()
    assert em_b['criado_em'].endswith('-04:00')
    assert em_a['criado_em'].endswith('-03:00')
    token = cliente.post(
        '/api/loja/auth/login', json={'slug': 'loja-b', 'email': b.admin.email, 'senha': SENHA}
    ).json()
    assert token['expira_em'].endswith('-04:00')


def test_fuso_da_loja_nao_vaza_para_a_proxima_transacao(cliente, lojas):
    a, _ = lojas
    with get_sessionmaker()() as db, db.begin():
        definir_contexto(db, origem='painel', loja_id=a.loja.id)
        assert db.execute(text("SELECT current_setting('TimeZone')")).scalar() == 'America/Sao_Paulo'
        definir_contexto(db, origem='superadmin')
        assert db.execute(text("SELECT current_setting('TimeZone')")).scalar() == 'UTC'
        definir_contexto(db, origem='painel', loja_id=a.loja.id)
    login_loja(cliente, 'loja-a', a.admin.email)
    with get_sessionmaker()() as db, db.begin():
        assert db.execute(text("SELECT current_setting('TimeZone')")).scalar() == 'UTC'


def test_superadmin_nao_responde_em_utc(cliente, lojas, engine_dono):
    """SUPERADMIN: o que é de uma loja sai no fuso dela; o da plataforma, em America/Sao_Paulo."""
    a, _ = lojas
    admin = criar_superadmin(engine_dono)
    h = cabecalho_superadmin(admin)
    plano = cliente.post('/api/superadmin/planos', json={'nome': 'Básico', 'preco_mensal': 10}, headers=h)
    assert plano.status_code == 201, plano.json()
    rotas = [
        '/lojas',
        f'/lojas/{a.loja.id}',
        f'/lojas/{a.loja.id}/modulos',
        f'/lojas/{a.loja.id}/funcionarios',
        '/planos',
        '/usuarios',
        f'/usuarios/{admin.id}',
        '/visao-geral',
        f'/auditoria?loja={a.loja.id}',
        '/auditoria?loja=plataforma',
    ]
    encontrados = []
    for rota in rotas:
        resposta = cliente.get(f'/api/superadmin{rota}', headers=h)
        assert resposta.status_code == 200, (rota, resposta.json())
        momentos = _momentos(resposta.json())
        assert all(m.endswith('-03:00') for m in momentos), (rota, momentos)
        encontrados += momentos
    assert encontrados
    login = cliente.post('/api/superadmin/auth/login', json={'email': admin.email, 'senha': SENHA}).json()
    assert login['expira_em'].endswith('-03:00')
