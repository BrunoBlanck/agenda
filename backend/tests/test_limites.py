"""Proteção contra abuso (SEG-09, ABE-23): limite por IP, bloqueio progressivo de login (conta + IP) e pedidos do site.

Os limites são baixados com monkeypatch na configuração. Cada cliente HTTP finge um IP diferente
(TestClient(client=(ip, porta))), lido do mesmo jeito que a auditoria (ip_da_requisicao).
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from tests.clinica import SEGUNDA
from tests.fabricas import SENHA, criar_superadmin

LOGIN = '/api/loja/auth/login'
LOGIN_SUPER = '/api/superadmin/auth/login'
MSG_LIMITE = 'Muitas requisições. Aguarde um pouco e tente novamente.'
MSG_BLOQUEIO = 'Muitas tentativas de login. Aguarde {} minuto(s) e tente novamente.'


@pytest.fixture
def limites(monkeypatch) -> Callable[..., None]:
    def ajustar(**valores: int) -> None:
        for nome, valor in valores.items():
            monkeypatch.setattr(get_settings(), nome, valor)

    return ajustar


@pytest.fixture
def com_ip():
    from app.main import app

    abertos: list[TestClient] = []

    def criar(ip: str) -> TestClient:
        cliente = TestClient(app, client=(ip, 50000))
        abertos.append(cliente)
        return cliente

    yield criar
    for cliente in abertos:
        cliente.close()


def _login(c, email, senha=SENHA, slug='loja-a'):
    return c.post(LOGIN, json={'slug': slug, 'email': email, 'senha': senha})


def _retry_after(resposta) -> int:
    return int(resposta.headers['Retry-After'])


# --- Login: limite por IP -----------------------------------------------------------------------------


def test_login_limitado_por_ip(lojas, limites, com_ip):
    limites(limite_login_por_ip=3, limite_login_janela=60)
    c, outro = com_ip('203.0.113.10'), com_ip('203.0.113.11')
    # E-mails diferentes: só o limite por IP entra em jogo (não o bloqueio por conta)
    for i in range(3):
        assert _login(c, f'x{i}@loja-a.com', 'errada').status_code == 401
    passou = _login(c, 'admin@loja-a.com')
    assert passou.status_code == 429
    assert passou.json() == {'detail': MSG_LIMITE}
    assert 1 <= _retry_after(passou) <= 60
    # O login do superadmin divide o contador do IP
    assert c.post(LOGIN_SUPER, json={'email': 'a@b.com', 'senha': 'x'}).status_code == 429
    # Outro IP não é afetado
    assert _login(outro, 'admin@loja-a.com').status_code == 200


# --- Login: bloqueio progressivo por conta ------------------------------------------------------------


def test_bloqueio_por_conta_depois_de_n_falhas(lojas, limites, com_ip):
    limites(login_falhas_para_bloquear=3, login_bloqueio_inicial=60, login_bloqueio_maximo=900)
    c = com_ip('203.0.113.20')
    for _ in range(3):
        assert _login(c, 'admin@loja-a.com', 'errada').status_code == 401
    # Bloqueada: nem a senha certa entra, e a resposta não confere a senha
    bloqueado = _login(c, 'admin@loja-a.com')
    assert bloqueado.status_code == 429
    assert bloqueado.json() == {'detail': MSG_BLOQUEIO.format(1)}
    assert 1 <= _retry_after(bloqueado) <= 60
    # O e-mail é comparado sem diferenciar maiúsculas
    assert _login(c, 'ADMIN@loja-a.com').status_code == 429
    # Outras contas, do mesmo IP, seguem normais
    assert _login(c, 'recepcao@loja-a.com').status_code == 200
    # O dono da conta, de outro IP, entra normalmente (o bloqueio é da conta naquele IP)
    assert _login(com_ip('203.0.113.21'), 'admin@loja-a.com').status_code == 200


def test_bloqueio_renovado_por_terceiro_nao_tranca_o_dono(lojas, limites, com_ip, engine_dono):
    """A18: quem só sabe o e-mail não consegue manter a conta trancada para o dono."""
    limites(login_falhas_para_bloquear=5, login_bloqueio_inicial=60, login_bloqueio_maximo=900)
    atacante, dono = com_ip('203.0.113.90'), com_ip('203.0.113.91')
    for _ in range(5):
        assert _login(atacante, 'admin@loja-a.com', 'errada').status_code == 401
    assert _login(atacante, 'admin@loja-a.com', 'errada').status_code == 429  # atacante bloqueado
    # Durante o bloqueio do atacante, o dono entra com a senha certa de outro IP
    assert _login(dono, 'admin@loja-a.com').status_code == 200
    # O bloqueio vence; uma nova falha do atacante renova só o bloqueio dele
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE limites.contadores SET bloqueado_ate = now() - interval '1 second'"))
    assert _login(atacante, 'admin@loja-a.com', 'errada').status_code == 401
    assert _login(atacante, 'admin@loja-a.com').status_code == 429
    assert _login(dono, 'admin@loja-a.com').status_code == 200
    # O mesmo vale para o superadmin
    criar_superadmin(engine_dono, 'root@plataforma.com')
    for _ in range(6):
        atacante.post(LOGIN_SUPER, json={'email': 'root@plataforma.com', 'senha': 'errada'})
    assert (
        atacante.post(LOGIN_SUPER, json={'email': 'root@plataforma.com', 'senha': SENHA}).status_code == 429
    )
    assert dono.post(LOGIN_SUPER, json={'email': 'root@plataforma.com', 'senha': SENHA}).status_code == 200


def test_bloqueio_nao_revela_se_o_email_existe(lojas, limites, com_ip):
    limites(login_falhas_para_bloquear=2)
    c = com_ip('203.0.113.30')
    respostas = {}
    for email in ('admin@loja-a.com', 'ninguem@loja-a.com'):
        respostas[email] = [(r.status_code, r.json()) for r in (_login(c, email, 'errada') for _ in range(3))]
    assert respostas['admin@loja-a.com'] == respostas['ninguem@loja-a.com']
    assert [s for s, _ in respostas['ninguem@loja-a.com']] == [401, 401, 429]


def test_bloqueio_dobra_a_cada_nova_falha(lojas, limites, com_ip, engine_dono):
    limites(login_falhas_para_bloquear=2, login_bloqueio_inicial=60, login_bloqueio_maximo=200)
    c = com_ip('203.0.113.40')

    def expirar_bloqueio():
        with engine_dono.begin() as conexao:
            conexao.execute(text("UPDATE limites.contadores SET bloqueado_ate = now() - interval '1 second'"))

    for _ in range(2):
        _login(c, 'admin@loja-a.com', 'errada')
    assert _retry_after(_login(c, 'admin@loja-a.com')) <= 60
    expirar_bloqueio()
    assert _login(c, 'admin@loja-a.com', 'errada').status_code == 401  # 3ª falha: 120 s
    segundo = _login(c, 'admin@loja-a.com')
    assert 60 < _retry_after(segundo) <= 120
    assert segundo.json() == {'detail': MSG_BLOQUEIO.format(2)}
    expirar_bloqueio()
    _login(c, 'admin@loja-a.com', 'errada')  # 4ª falha: 240 s, limitado ao máximo (200 s)
    assert 120 < _retry_after(_login(c, 'admin@loja-a.com')) <= 200


def test_acertar_a_senha_zera_as_falhas(lojas, limites, com_ip):
    limites(login_falhas_para_bloquear=3)
    c = com_ip('203.0.113.50')
    for _ in range(2):
        assert _login(c, 'admin@loja-a.com', 'errada').status_code == 401
    assert _login(c, 'admin@loja-a.com').status_code == 200
    for _ in range(2):
        assert _login(c, 'admin@loja-a.com', 'errada').status_code == 401
    assert _login(c, 'admin@loja-a.com').status_code == 200


def test_bloqueio_do_login_do_superadmin(engine_dono, limites, com_ip):
    criar_superadmin(engine_dono, 'root@plataforma.com')
    limites(login_falhas_para_bloquear=2)
    c = com_ip('203.0.113.60')
    for _ in range(2):
        assert c.post(LOGIN_SUPER, json={'email': 'root@plataforma.com', 'senha': 'x'}).status_code == 401
    bloqueado = c.post(LOGIN_SUPER, json={'email': 'root@plataforma.com', 'senha': SENHA})
    assert bloqueado.status_code == 429
    assert 'Retry-After' in bloqueado.headers
    # A conta de mesmo e-mail numa loja é outra conta (outro contador)
    assert _login(c, 'admin@loja-a.com', 'errada').status_code == 401


def test_contadores_nao_guardam_ip_nem_email(lojas, com_ip, engine_dono):
    c = com_ip('203.0.113.70')
    _login(c, 'admin@loja-a.com', 'errada')
    with engine_dono.connect() as conexao:
        chaves = conexao.execute(text('SELECT chave FROM limites.contadores')).scalars().all()
    assert len(chaves) == 2  # IP e conta
    for chave in chaves:
        assert len(chave) == 64
        assert 'admin' not in chave
        assert '203.0.113.70' not in chave


# --- Site do consumidor -------------------------------------------------------------------------------


def test_site_limitado_por_ip(clinica, limites, com_ip):
    limites(limite_site_por_ip=3, limite_site_janela=60)
    c = com_ip('198.51.100.10')
    assert c.get('/api/site/loja-a').status_code == 200
    assert c.get('/api/site/nao-existe').status_code == 404  # loja inexistente também conta
    assert c.get('/api/site/loja-a/servicos').status_code == 200
    excesso = c.get('/api/site/loja-a/horarios', params={'inicio': SEGUNDA})
    assert excesso.status_code == 429
    assert excesso.json() == {'detail': MSG_LIMITE}
    assert 1 <= _retry_after(excesso) <= 60
    assert com_ip('198.51.100.11').get('/api/site/loja-a').status_code == 200


def _pedido(clinica, hora, telefone='(11) 97777-6666'):
    return {
        'servico_id': clinica.limpeza,
        'funcionario_id': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T{hora}',
        'nome': 'Ana',
        'sobrenome': 'Souza',
        'telefone': telefone,
    }


def test_site_pedidos_por_ip_em_cada_loja(clinica, limites, com_ip):
    limites(limite_site_pedidos_por_ip=2)
    c = com_ip('198.51.100.20')
    url = '/api/site/loja-a/agendamentos'
    assert c.post(url, json=_pedido(clinica, '08:00', '(11) 91111-0001')).status_code == 201
    assert c.post(url, json=_pedido(clinica, '09:00', '(11) 91111-0002')).status_code == 201
    terceiro = c.post(url, json=_pedido(clinica, '10:00', '(11) 91111-0003'))
    assert terceiro.status_code == 429
    assert 'Retry-After' in terceiro.headers
    # Em outra loja o contador é outro (a loja-b não tem serviços: o pedido é recusado, mas não por limite)
    assert c.post('/api/site/loja-b/agendamentos', json=_pedido(clinica, '10:00')).status_code != 429
    # Outro IP pede normalmente
    assert (
        com_ip('198.51.100.21').post(url, json=_pedido(clinica, '10:00', '(11) 91111-0003')).status_code
        == 201
    )


def test_site_limita_pedidos_pendentes_por_telefone(cliente, clinica, limites, engine_dono):
    limites(site_pendentes_por_telefone=2)
    url = '/api/site/loja-a/agendamentos'
    primeiro = cliente.post(url, json=_pedido(clinica, '08:00', '(11) 97777-6666'))
    assert primeiro.status_code == 201
    assert cliente.post(url, json=_pedido(clinica, '09:00', '11977776666')).status_code == 201
    terceiro = cliente.post(url, json=_pedido(clinica, '10:00', '11 97777-6666'))
    assert terceiro.status_code == 409
    assert terceiro.json()['detail'] == (
        'Já há pedidos deste telefone aguardando a confirmação da loja. '
        'Aguarde a resposta antes de pedir outro horário.'
    )
    # Outro telefone pede normalmente
    assert cliente.post(url, json=_pedido(clinica, '10:00', '(11) 96666-5555')).status_code == 201
    # Depois que a loja responde um pedido, o telefone pode pedir de novo
    aceitar = cliente.post(
        f'/api/loja/agendamentos/{primeiro.json()["id"]}/aceitar', headers=clinica.lt.h_admin
    )
    assert aceitar.status_code == 200
    assert cliente.post(url, json=_pedido(clinica, '11:00', '(11) 97777-6666')).status_code == 201
    with engine_dono.connect() as conexao:
        clientes = conexao.execute(
            text("SELECT count(*) FROM clientes WHERE telefone = '(11) 97777-6666'")
        ).scalar()
    assert clientes == 1
