"""Roteamento por URL (GER-29, PLA-16, SIT-12): slugs reservados e páginas HTML fora de /api.

O fluxo de agendamento do site (/{slug}, /{slug}/agendar...) tem os testes em test_site_paginas.py.
"""

import re
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.auth.dependencias import ip_da_requisicao
from app.config import get_settings
from app.models.enums import StatusLoja
from app.routers.html import CSP_SITE
from app.services.slugs import MSG_SLUG_RESERVADO, SLUGS_RESERVADOS, endereco_de_loja
from tests.conftest import URL_DONO, config_alembic, recriar_banco
from tests.fabricas import cabecalho_superadmin, criar_loja, criar_plano, criar_superadmin

LOJAS = '/api/superadmin/lojas'
MSG_PAINEL = 'Acesse o painel pelo endereço da sua loja, por exemplo /nome-da-loja/painel.'
CSP = (
    "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
RESERVADOS = sorted(SLUGS_RESERVADOS)


@pytest.fixture
def sa(engine_dono):
    return cabecalho_superadmin(criar_superadmin(engine_dono))


@pytest.fixture
def plano(engine_dono):
    return criar_plano(engine_dono)


def nova_loja(plano, **extra):
    return {
        'tipo': 'barbearia',
        'nome': 'Navalha Cortes ME',
        'nome_fantasia': 'Barbearia Navalha',
        'slug': 'barbearia-navalha',
        'plano_id': str(plano.id),
        'admin': {'nome': 'Marcos Silva', 'email': 'marcos@navalha.com'},
        **extra,
    }


def alterar_loja(engine, slug_atual: str, /, **campos) -> None:
    atribuicoes = ', '.join(f'{campo} = :{campo}' for campo in campos)
    with engine.begin() as conexao:
        conexao.execute(
            text(f'UPDATE lojas SET {atribuicoes} WHERE slug = :slug_atual'),
            {'slug_atual': slug_atual, **campos},
        )


def eh_html(resposta, status: int, csp: str = CSP) -> None:
    assert resposta.status_code == status
    assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
    assert resposta.headers['content-security-policy'] == csp
    assert resposta.headers['cache-control'] == 'no-store'
    assert resposta.headers['x-content-type-options'] == 'nosniff'
    assert resposta.headers['referrer-policy'] == 'same-origin'


# --- PLA-16: slugs reservados --------------------------------------------------------------------


@pytest.mark.parametrize('slug', [*RESERVADOS, 'SuperAdmin', ' api '])
def test_criar_loja_com_slug_reservado_responde_422(cliente, sa, plano, slug):
    resposta = cliente.post(LOJAS, json=nova_loja(plano, slug=slug), headers=sa)
    assert resposta.status_code == 422
    assert resposta.json() == {
        'detail': 'Verifique os dados informados.',
        'erros': [{'campo': 'slug', 'mensagem': MSG_SLUG_RESERVADO}],
    }


@pytest.mark.parametrize('slug', ['painel', 'superadmin', 'api'])
def test_editar_loja_para_slug_reservado_responde_422(cliente, engine_dono, sa, plano, slug):
    loja = cliente.post(LOJAS, json=nova_loja(plano), headers=sa).json()
    corpo = {k: v for k, v in nova_loja(plano, slug=slug).items() if k != 'admin'}
    resposta = cliente.put(f'{LOJAS}/{loja["id"]}', json=corpo, headers=sa)
    assert resposta.status_code == 422
    assert resposta.json()['erros'] == [{'campo': 'slug', 'mensagem': MSG_SLUG_RESERVADO}]
    with engine_dono.connect() as conexao:
        atual = conexao.execute(text('SELECT slug FROM lojas WHERE id = :l'), {'l': loja['id']}).scalar()
    assert atual == 'barbearia-navalha'


@pytest.mark.parametrize('slug', ['superadmin-centro', 'minha-api', 'painel2', 'app-saude', 'apis'])
def test_slug_que_so_contem_um_reservado_e_aceito(cliente, sa, plano, slug):
    resposta = cliente.post(LOJAS, json=nova_loja(plano, slug=slug), headers=sa)
    assert resposta.status_code == 201, resposta.json()


@pytest.mark.parametrize('slug', RESERVADOS)
def test_banco_recusa_slug_reservado(engine_dono, slug):
    with pytest.raises(IntegrityError) as erro, engine_dono.begin() as conexao:
        conexao.execute(
            text("INSERT INTO lojas (tipo, nome, slug) VALUES ('clinica', 'Loja', :slug)"), {'slug': slug}
        )
    assert erro.value.orig.diag.constraint_name == 'ck_lojas_slug_reservado'


def test_banco_recusa_trocar_para_slug_reservado(engine_dono):
    criar_loja(engine_dono, 'loja-a')
    with pytest.raises(IntegrityError) as erro:
        alterar_loja(engine_dono, 'loja-a', slug='superadmin')
    assert erro.value.orig.diag.constraint_name == 'ck_lojas_slug_reservado'


def test_lista_do_banco_e_a_mesma_do_codigo(engine_dono):
    with engine_dono.connect() as conexao:
        definicao = conexao.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_lojas_slug_reservado'"
            )
        ).scalar()
    assert set(re.findall(r"'([a-z0-9-]+)'", definicao)) == SLUGS_RESERVADOS


def test_check_do_banco_vira_422_com_a_mensagem(cliente, sa, plano, monkeypatch):
    """Se a validação do schema falhar (lista desatualizada), o CHECK barra e a resposta é a mesma frase."""
    monkeypatch.setattr('app.schemas.superadmin.SLUGS_RESERVADOS', frozenset())
    resposta = cliente.post(LOJAS, json=nova_loja(plano, slug='admin'), headers=sa)
    assert resposta.status_code == 422
    assert resposta.json() == {'detail': MSG_SLUG_RESERVADO}


def test_slugs_do_seed_nao_sao_reservados():
    from scripts.seed import LOJAS as LOJAS_SEED

    slugs = [modelo['dados']['slug'] for modelo in LOJAS_SEED]
    assert slugs
    assert all(endereco_de_loja(slug) for slug in slugs), slugs


def test_migracao_para_se_alguma_loja_usa_slug_reservado():
    """Antes do CHECK, a 0005 lista as lojas (inclusive excluídas) com slug reservado e não renomeia nada."""
    url = URL_DONO.set(database=f'{URL_DONO.database}_migracao5')
    recriar_banco(url)
    config = config_alembic(url)
    engine = create_engine(url)
    try:
        command.upgrade(config, '0004')
        criar_loja(engine, 'admin')
        criar_loja(engine, 'painel')
        alterar_loja(engine, 'admin', excluido_em='2026-01-01T00:00:00Z')
        with pytest.raises(RuntimeError) as erro:
            command.upgrade(config, 'head')
        mensagem = str(erro.value)
        assert '"admin" (Loja admin, excluída' in mensagem
        assert '"painel" (Loja painel, id ' in mensagem

        with engine.begin() as conexao:
            conexao.execute(text("UPDATE lojas SET slug = slug || '-antiga'"))
        command.upgrade(config, 'head')
        with engine.connect() as conexao:
            slugs = set(conexao.execute(text('SELECT slug FROM lojas')).scalars())
            existe = conexao.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'ck_lojas_slug_reservado'")
            ).scalar()
        assert (slugs, existe) == ({'admin-antiga', 'painel-antiga'}, 1)

        command.downgrade(config, '0004')
        with engine.connect() as conexao:
            existe = conexao.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'ck_lojas_slug_reservado'")
            ).scalar()
        assert existe == 0
    finally:
        engine.dispose()
        servidor = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
        with servidor.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        servidor.dispose()


# --- GER-29 / SIT-11: páginas HTML ---------------------------------------------------------------


def test_raiz_responde_404_sem_revelar_nada(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    resposta = cliente.get('/')
    eh_html(resposta, 404)
    assert 'Página não encontrada' in resposta.text
    assert 'loja-a' not in resposta.text
    assert 'superadmin' not in resposta.text.lower()
    assert '<script' not in resposta.text


@pytest.mark.parametrize('caminho', ['/painel', '/painel/', '/painel/agenda', '/painel/login/x'])
def test_painel_sem_loja_orienta_o_endereco(cliente, caminho):
    resposta = cliente.get(caminho)
    eh_html(resposta, 404)
    assert MSG_PAINEL in resposta.text


def test_pagina_da_loja_ativa_com_dados_publicos(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    alterar_loja(
        engine_dono,
        'loja-a',
        nome_fantasia='Clínica Sorriso',
        nome='Sorriso Odontologia LTDA',
        cnpj='11.222.333/0001-81',
        telefone='(11) 98888-1111',
        email='contato@sorriso.com',
        logradouro='Rua das Flores',
        numero='120',
        complemento='Sala 3',
        bairro='Centro',
        cidade='Campinas',
        uf='SP',
        logo_url='/api/arquivos/logos/x/logo.png',
    )
    resposta = cliente.get('/loja-a')
    eh_html(resposta, 200, CSP_SITE)
    html = resposta.text
    assert '<title>Clínica Sorriso</title>' in html
    assert '<h1 class="nome">Clínica Sorriso</h1>' in html
    assert 'Agendamento online em breve.' not in html  # a página provisória (SIT-11) saiu
    assert '<p class="tipo">Clínica</p>' in html  # tipo da loja
    assert '<a href="tel:11988881111">(11) 98888-1111</a>' in html
    assert 'Rua das Flores, 120 - Sala 3 · Centro · Campinas/SP' in html
    assert '<img class="logo" src="/api/arquivos/logos/x/logo.png"' in html
    # Só o que LojaPublica expõe: nada de razão social nem CNPJ
    assert 'LTDA' not in html
    assert '11.222.333' not in html
    assert '<script>' not in html  # só o script da própria origem (/static/site/site.js)


def test_pagina_da_loja_sem_dados_opcionais(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    alterar_loja(engine_dono, 'loja-a', nome_fantasia=None)
    resposta = cliente.get('/loja-a')
    eh_html(resposta, 200, CSP_SITE)
    assert '<h1 class="nome">Loja loja-a</h1>' in resposta.text  # sem nome fantasia: o nome
    assert '<img' not in resposta.text
    assert 'class="contato"' not in resposta.text


def test_pagina_da_loja_nao_leva_ao_painel_nem_ao_login(cliente, engine_dono):
    """DIR-003: o site do consumidor não tem caminho para o painel, o login ou o SUPERADMIN."""
    criar_loja(engine_dono, 'loja-a')
    alterar_loja(
        engine_dono,
        'loja-a',
        telefone='(11) 98888-1111',
        email='contato@sorriso.com',
        logradouro='Rua das Flores',
        cidade='Campinas',
        uf='SP',
        logo_url='/api/arquivos/logos/x/logo.png',
    )
    for caminho in ('/loja-a', '/loja-a/'):
        resposta = cliente.get(caminho, follow_redirects=True)
        eh_html(resposta, 200, CSP_SITE)
        html = resposta.text.lower()
        for proibido in ('painel', 'superadmin', 'login'):  # 'painel' cobre /painel e /{slug}/painel
            assert proibido not in html, proibido


def test_pagina_da_loja_escapa_o_html(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    alterar_loja(
        engine_dono, 'loja-a', nome_fantasia='<script>alert(1)</script>', logo_url='" onerror="alert(1)'
    )
    html = cliente.get('/loja-a').text
    assert '<script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert 'src="&#34; onerror=&#34;alert(1)"' in html


@pytest.mark.parametrize('situacao', [StatusLoja.suspensa, StatusLoja.cancelada])
def test_loja_suspensa_ou_cancelada_responde_404(cliente, engine_dono, situacao):
    criar_loja(engine_dono, 'fechada', status=situacao)
    resposta = cliente.get('/fechada')
    eh_html(resposta, 404)
    assert 'Loja não encontrada' in resposta.text
    assert 'Loja fechada' not in resposta.text


def test_loja_excluida_responde_404(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    alterar_loja(engine_dono, 'loja-a', excluido_em='2026-01-01T00:00:00Z')
    eh_html(cliente.get('/loja-a'), 404)


@pytest.mark.parametrize(
    'caminho', ['/nao-existe', '/LOJA-A', '/loja_a', '/-loja-a', f'/{"a" * 61}', '/favicon.ico', '/admin']
)
def test_slug_inexistente_invalido_ou_reservado_responde_404(cliente, engine_dono, caminho):
    criar_loja(engine_dono, 'loja-a')
    resposta = cliente.get(caminho)
    eh_html(resposta, 404)
    assert 'Loja não encontrada' in resposta.text


def test_barra_no_fim_redireciona_308(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    resposta = cliente.get('/loja-a/', follow_redirects=False)
    assert resposta.status_code == 308
    assert resposta.headers['location'] == '/loja-a'
    assert cliente.get('/loja-a/').status_code == 200


@pytest.mark.parametrize('caminho', ['/LOJA-A/', '/admin/', '/loja_a/'])
def test_barra_no_fim_com_slug_invalido_nao_redireciona(cliente, caminho):
    resposta = cliente.get(caminho, follow_redirects=False)
    eh_html(resposta, 404)


@pytest.mark.parametrize(
    'caminho', ['/loja-a/xyz', '/loja-a/painel', '/loja-a/painel/agenda', '/loja-a/a/b/']
)
def test_outras_paginas_da_loja_respondem_404(cliente, engine_dono, caminho):
    criar_loja(engine_dono, 'loja-a')
    resposta = cliente.get(caminho)
    eh_html(resposta, 404)
    assert 'Página não encontrada' in resposta.text


@pytest.mark.parametrize('caminho', ['/', '/painel', '/loja-a', '/nao-existe', '/loja-a/xyz'])
def test_head_responde_como_o_get(cliente, engine_dono, caminho):
    criar_loja(engine_dono, 'loja-a')
    get, head = cliente.get(caminho), cliente.head(caminho)
    assert head.status_code == get.status_code
    assert head.headers['content-type'] == get.headers['content-type']
    assert head.headers['content-security-policy'] == get.headers['content-security-policy']


def test_head_no_servidor_real_vem_sem_corpo(servidor, engine_dono):
    import httpx

    criar_loja(engine_dono, 'loja-a')
    for caminho, codigo in (('/loja-a', 200), ('/', 404)):
        resposta = httpx.head(f'{servidor}{caminho}')
        assert resposta.status_code == codigo
        assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
        assert int(resposta.headers['content-length']) > 0
        assert resposta.content == b''


# --- Não captura /api nem /docs --------------------------------------------------------------------


@pytest.mark.parametrize('metodo', ['GET', 'POST', 'HEAD'])
@pytest.mark.parametrize('caminho', ['/api', '/api/', '/api/nao-existe', '/api/loja/nao-existe'])
def test_api_inexistente_continua_404_em_json(cliente, metodo, caminho):
    resposta = cliente.request(metodo, caminho)
    assert resposta.status_code == 404
    assert resposta.headers['content-type'] == 'application/json'
    if metodo != 'HEAD':
        assert resposta.json() == {'detail': 'Não encontrado.'}


def test_rotas_da_api_continuam_respondendo(cliente, engine_dono):
    criar_loja(engine_dono, 'loja-a')
    assert cliente.get('/api/saude').json() == {'status': 'ok'}
    assert cliente.get('/api/site/loja-a').json()['slug'] == 'loja-a'
    resposta = cliente.get('/api/site/nao-existe')
    assert (resposta.status_code, resposta.json()) == (404, {'detail': 'Loja não encontrada.'})
    assert cliente.get('/api/loja/eu').status_code == 401
    assert cliente.get('/api/superadmin/eu').status_code == 401


def test_documentacao_nao_e_capturada(cliente):
    docs = cliente.get('/docs')
    assert docs.status_code == 200
    assert 'swagger' in docs.text.lower()
    esquema = cliente.get('/openapi.json')
    assert esquema.status_code == 200
    caminhos = set(esquema.json()['paths'])
    assert all(c.startswith('/api/') for c in caminhos), caminhos  # páginas HTML fora do OpenAPI


def test_em_producao_sem_documentacao_as_rotas_viram_404_html(monkeypatch):
    from app.main import criar_app

    monkeypatch.setattr(get_settings(), 'ambiente', 'producao')
    with TestClient(criar_app()) as c:
        for caminho in ('/docs', '/openapi.json', '/redoc'):
            eh_html(c.get(caminho), 404)
        assert c.get('/api/nao-existe').json() == {'detail': 'Não encontrado.'}


# --- Limite de requisições do site -----------------------------------------------------------------


def test_pagina_da_loja_usa_o_limite_do_site(engine_dono, monkeypatch):
    from app.main import app

    criar_loja(engine_dono, 'loja-a')
    monkeypatch.setattr(get_settings(), 'limite_site_por_ip', 2)
    with TestClient(app, client=('198.51.100.20', 50000)) as c:
        for _ in range(3):  # endereço inválido ou reservado não consulta o banco e não conta
            eh_html(c.get('/admin'), 404)
        eh_html(c.get('/loja-a'), 200, CSP_SITE)
        assert c.get('/api/site/loja-a').status_code == 200  # mesmo contador da API do site
        excesso = c.get('/loja-a')
        eh_html(excesso, 429)
        assert 'Muitas requisições' in excesso.text
        assert 1 <= int(excesso.headers['retry-after']) <= 60
    with TestClient(app, client=('198.51.100.21', 50000)) as outro:
        eh_html(outro.get('/loja-a'), 200, CSP_SITE)


# --- Atrás do proxy (uvicorn --proxy-headers) ------------------------------------------------------


def _app_que_mostra_o_ip() -> ProxyHeadersMiddleware:
    def ip(request: Request) -> PlainTextResponse:
        return PlainTextResponse(ip_da_requisicao(request) or '')

    return ProxyHeadersMiddleware(Starlette(routes=[Route('/', ip)]), trusted_hosts='127.0.0.1')


def test_ip_do_cliente_vem_do_proxy_confiavel():
    with TestClient(_app_que_mostra_o_ip(), client=('127.0.0.1', 50000)) as c:
        assert c.get('/', headers={'X-Forwarded-For': '203.0.113.7'}).text == '203.0.113.7'
        assert c.get('/').text == '127.0.0.1'


def test_proxy_nao_confiavel_nao_troca_o_ip():
    with TestClient(_app_que_mostra_o_ip(), client=('198.51.100.9', 50000)) as c:
        assert c.get('/', headers={'X-Forwarded-For': '203.0.113.7'}).text == '198.51.100.9'


def test_dockerfile_liga_os_cabecalhos_do_proxy():
    dockerfile = (Path(__file__).resolve().parent.parent / 'Dockerfile').read_text(encoding='utf-8')
    assert '--proxy-headers' in dockerfile
    assert 'FORWARDED_ALLOW_IPS=127.0.0.1' in dockerfile
