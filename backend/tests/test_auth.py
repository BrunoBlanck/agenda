"""Login de funcionário e superadmin, tokens e separação entre as áreas."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.models import Auditoria
from app.models.enums import StatusLoja
from tests.fabricas import (
    SENHA,
    criar_funcionario,
    criar_loja,
    criar_superadmin,
    login_loja,
    login_superadmin,
    sessao,
)


@pytest.fixture
def loja_a(engine_dono):
    loja, perfis = criar_loja(engine_dono, 'loja-a')
    admin = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@a.com', nome='Admin A')
    return loja, perfis, admin


def _login(cliente, slug, email, senha=SENHA):
    return cliente.post('/api/loja/auth/login', json={'slug': slug, 'email': email, 'senha': senha})


def _token_forjado(**dados):
    """Token assinado com o segredo certo, mas com dados escolhidos pelo teste."""
    agora = datetime.now(UTC)
    base = {'iat': agora, 'exp': agora + timedelta(minutes=5)}
    return jwt.encode({**base, **dados}, get_settings().jwt_secret.get_secret_value(), algorithm='HS256')


# --- Login do funcionário -----------------------------------------------------------------------


def test_login_do_funcionario_devolve_token(cliente, loja_a, engine_dono):
    loja, _, admin = loja_a
    resposta = _login(cliente, 'loja-a', 'ADMIN@a.com')  # e-mail sem diferenciar maiúsculas
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo['tipo_token'] == 'bearer'
    dados = jwt.decode(corpo['token'], options={'verify_signature': False})
    assert dados['tipo'] == 'funcionario'
    assert dados['sub'] == str(admin.id)
    assert dados['loja_id'] == str(loja.id)

    assert corpo['expira_em'].endswith('-03:00')  # no fuso da loja (America/Sao_Paulo)

    with sessao(engine_dono) as db:
        ultimo, atualizado_em = db.execute(
            text('SELECT ultimo_login_em, atualizado_em FROM funcionarios WHERE id = :id'), {'id': admin.id}
        ).one()
        alteracoes = db.scalars(
            select(Auditoria).where(Auditoria.tabela == 'funcionarios', Auditoria.operacao == 'alterar')
        ).all()
    assert ultimo is not None
    # O login não é alteração do cadastro: fora da auditoria e da "última alteração"
    assert alteracoes == []
    assert atualizado_em < ultimo


@pytest.mark.parametrize(
    ('slug', 'email', 'senha'),
    [
        ('loja-a', 'admin@a.com', 'errada'),
        ('loja-a', 'naoexiste@a.com', SENHA),
        ('loja-inexistente', 'admin@a.com', SENHA),
    ],
)
def test_login_invalido_nao_revela_o_motivo(cliente, loja_a, slug, email, senha):
    resposta = _login(cliente, slug, email, senha)
    assert resposta.status_code == 401
    assert resposta.json() == {'detail': 'Loja, e-mail ou senha inválidos.'}


def test_funcionario_de_outra_loja_nao_entra_pelo_slug_errado(cliente, engine_dono, loja_a):
    loja_b, perfis_b = criar_loja(engine_dono, 'loja-b')
    criar_funcionario(engine_dono, loja_b, perfis_b['Administrador'], 'admin@b.com')
    assert _login(cliente, 'loja-a', 'admin@b.com').status_code == 401


def test_funcionario_inativo_nao_faz_login(cliente, engine_dono, loja_a):
    loja, perfis, _ = loja_a
    criar_funcionario(engine_dono, loja, perfis['Recepção'], 'inativo@a.com', ativo=False)
    resposta = _login(cliente, 'loja-a', 'inativo@a.com')
    assert resposta.status_code == 403
    assert 'desativado' in resposta.json()['detail']
    # Senha errada continua sem revelar nada
    assert _login(cliente, 'loja-a', 'inativo@a.com', 'errada').status_code == 401


def test_funcionario_excluido_nao_faz_login(cliente, engine_dono, loja_a):
    _, _, admin = loja_a
    with sessao(engine_dono) as db:
        db.execute(text('DELETE FROM funcionarios WHERE id = :id'), {'id': admin.id})
    assert _login(cliente, 'loja-a', 'admin@a.com').status_code == 401


@pytest.mark.parametrize('status_loja', [StatusLoja.suspensa, StatusLoja.cancelada])
def test_loja_suspensa_ou_cancelada_nao_faz_login(cliente, engine_dono, status_loja):
    loja, perfis = criar_loja(engine_dono, 'loja-parada', status=status_loja)
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@p.com')
    resposta = _login(cliente, 'loja-parada', 'admin@p.com')
    assert resposta.status_code == 403
    assert status_loja.value[:-1] in resposta.json()['detail']  # "suspens" / "cancelad"


# --- Uso do token -------------------------------------------------------------------------------


def test_sem_token_responde_401(cliente):
    resposta = cliente.get('/api/loja/eu')
    assert resposta.status_code == 401
    assert resposta.json() == {'detail': 'Faça login para continuar.'}
    assert resposta.headers['www-authenticate'] == 'Bearer'


@pytest.mark.parametrize('token', ['lixo', 'a.b.c'])
def test_token_invalido_responde_401(cliente, token):
    assert cliente.get('/api/loja/eu', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_token_expirado_responde_401(cliente, loja_a):
    loja, _, admin = loja_a
    agora = datetime.now(UTC)
    token = _token_forjado(
        sub=str(admin.id),
        tipo='funcionario',
        loja_id=str(loja.id),
        iat=agora - timedelta(hours=2),
        exp=agora - timedelta(hours=1),
    )
    assert cliente.get('/api/loja/eu', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_token_com_outro_segredo_responde_401(cliente, loja_a):
    loja, _, admin = loja_a
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            'sub': str(admin.id),
            'tipo': 'funcionario',
            'loja_id': str(loja.id),
            'iat': agora,
            'exp': agora + timedelta(hours=1),
        },
        'outro-segredo-qualquer-com-tamanho-suficiente',
        algorithm='HS256',
    )
    assert cliente.get('/api/loja/eu', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_token_com_loja_trocada_nao_da_acesso_a_outra_loja(cliente, engine_dono, loja_a):
    """A loja vem do token; se ela não bate com o funcionário, nada é encontrado."""
    _, _, admin = loja_a
    loja_b, _ = criar_loja(engine_dono, 'loja-b')
    token = _token_forjado(sub=str(admin.id), tipo='funcionario', loja_id=str(loja_b.id))
    assert cliente.get('/api/loja/eu', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_loja_suspensa_depois_do_login_bloqueia_o_token(cliente, engine_dono, loja_a):
    loja, _, _ = loja_a
    cabecalho = login_loja(cliente, 'loja-a', 'admin@a.com')
    with sessao(engine_dono) as db:
        db.execute(text("UPDATE lojas SET status = 'suspensa' WHERE id = :id"), {'id': loja.id})
    resposta = cliente.get('/api/loja/eu', headers=cabecalho)
    assert resposta.status_code == 403
    assert 'suspensa' in resposta.json()['detail']


def test_funcionario_inativado_depois_do_login_perde_o_acesso(cliente, engine_dono, loja_a):
    _, _, admin = loja_a
    cabecalho = login_loja(cliente, 'loja-a', 'admin@a.com')
    with sessao(engine_dono) as db:
        db.execute(text('UPDATE funcionarios SET ativo = false WHERE id = :id'), {'id': admin.id})
    assert cliente.get('/api/loja/eu', headers=cabecalho).status_code == 401


# --- Superadmin ---------------------------------------------------------------------------------


def test_login_do_superadmin(cliente, engine_dono):
    superadmin = criar_superadmin(engine_dono, 'rafael@plataforma.com')
    cabecalho = login_superadmin(cliente, 'Rafael@Plataforma.com')
    resposta = cliente.get('/api/superadmin/eu', headers=cabecalho)
    assert resposta.status_code == 200
    assert resposta.json()['id'] == str(superadmin.id)


@pytest.mark.parametrize(
    ('email', 'senha'), [('rafael@plataforma.com', 'errada'), ('ninguem@plataforma.com', SENHA)]
)
def test_login_do_superadmin_invalido(cliente, engine_dono, email, senha):
    criar_superadmin(engine_dono, 'rafael@plataforma.com')
    resposta = cliente.post('/api/superadmin/auth/login', json={'email': email, 'senha': senha})
    assert resposta.status_code == 401
    assert resposta.json() == {'detail': 'E-mail ou senha inválidos.'}


def test_superadmin_inativo_nao_faz_login(cliente, engine_dono):
    criar_superadmin(engine_dono, 'rafael@plataforma.com', ativo=False)
    resposta = cliente.post(
        '/api/superadmin/auth/login', json={'email': 'rafael@plataforma.com', 'senha': SENHA}
    )
    assert resposta.status_code == 401


def test_token_de_superadmin_nao_vale_nas_rotas_da_loja(cliente, engine_dono):
    criar_superadmin(engine_dono, 'rafael@plataforma.com')
    cabecalho = login_superadmin(cliente, 'rafael@plataforma.com')
    resposta = cliente.get('/api/loja/eu', headers=cabecalho)
    assert resposta.status_code == 401
    assert 'não vale para esta área' in resposta.json()['detail']


def test_token_de_funcionario_nao_vale_nas_rotas_do_superadmin(cliente, loja_a):
    cabecalho = login_loja(cliente, 'loja-a', 'admin@a.com')
    resposta = cliente.get('/api/superadmin/eu', headers=cabecalho)
    assert resposta.status_code == 401
    assert 'não vale para esta área' in resposta.json()['detail']
