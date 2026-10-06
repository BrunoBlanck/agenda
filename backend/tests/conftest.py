"""Infraestrutura dos testes: banco Postgres real e separado (TEST_DATABASE_NAME).

No início da sessão o banco de teste é recriado do zero e recebe todas as migrações. Depois de cada
teste os dados são apagados (menos os catálogos da migração), com triggers e FKs desligados só
nessa limpeza (session_replication_role = replica, exige que o dono seja superusuário, como no
docker compose de desenvolvimento).

A aplicação e os testes de banco conectam com o usuário da aplicação (DATABASE_URL), sujeito ao
RLS e ao REVOKE da auditoria. O preparo de dados usa o dono do schema.
"""

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.config import get_settings


def _configurar_ambiente_de_teste() -> tuple[URL, URL]:
    base = get_settings()
    url_app = make_url(base.database_url.get_secret_value())
    url_dono = make_url(base.database_owner_url.get_secret_value())
    nome = base.test_database_name
    if nome in (url_app.database, url_dono.database):
        raise RuntimeError('TEST_DATABASE_NAME não pode ser o banco de desenvolvimento.')
    url_app, url_dono = url_app.set(database=nome), url_dono.set(database=nome)
    os.environ['DATABASE_URL'] = url_app.render_as_string(hide_password=False)
    os.environ['DATABASE_OWNER_URL'] = url_dono.render_as_string(hide_password=False)
    os.environ['AMBIENTE'] = 'teste'
    # Arquivos enviados (logo) numa pasta temporária, nunca em backend/arquivos
    os.environ['ARQUIVOS_DIR'] = tempfile.mkdtemp(prefix='agenda-arquivos-')
    get_settings.cache_clear()
    return url_app, url_dono


URL_APP, URL_DONO = _configurar_ambiente_de_teste()

# Importados depois de apontar a configuração para o banco de teste
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.limites import get_engine_limites  # noqa: E402
from scripts.criar_papel_app import criar_papel_app  # noqa: E402

TABELAS_PRESERVADAS = {'alembic_version', 'funcionalidades', 'recursos'}


def config_alembic(url: URL) -> Config:
    config = Config(os.path.join(os.path.dirname(__file__), '..', 'alembic.ini'))
    config.attributes['url'] = url.render_as_string(hide_password=False)
    config.attributes['sem_log'] = True
    return config


def recriar_banco(url: URL) -> None:
    servidor = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with servidor.connect() as conexao:
        conexao.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conexao.execute(text(f'CREATE DATABASE "{url.database}"'))
    servidor.dispose()


@pytest.fixture(scope='session', autouse=True)
def banco() -> Iterator[None]:
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    get_engine_limites.cache_clear()
    recriar_banco(URL_DONO)
    criar_papel_app(URL_DONO.render_as_string(hide_password=False))
    command.upgrade(config_alembic(URL_DONO), 'head')
    yield
    get_engine().dispose()
    get_engine_limites().dispose()
    shutil.rmtree(get_settings().arquivos_dir, ignore_errors=True)


@pytest.fixture(scope='session')
def engine_dono():
    engine = create_engine(URL_DONO)
    yield engine
    engine.dispose()


@pytest.fixture(scope='session')
def engine_app():
    return get_engine()


@pytest.fixture(autouse=True)
def limpar(engine_dono) -> Iterator[None]:
    yield
    with engine_dono.begin() as conexao:
        tabelas = conexao.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
        apagar = [t for t in tabelas if t not in TABELAS_PRESERVADAS]
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        for tabela in apagar:
            conexao.execute(text(f'DELETE FROM {tabela}'))
        conexao.execute(text("SELECT setval('auditoria_id_seq', 1, false)"))
        conexao.execute(text('DELETE FROM limites.contadores'))


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def navegador() -> Iterator[Callable[..., TestClient]]:
    """Fábrica de navegadores do site (cada um com os seus cookies), opcionalmente com um IP próprio.

    Usam ``https://testserver``: o cookie da sessão do cliente tem ``Secure`` fora de desenvolvimento.
    """
    from app.main import app

    abertos: list[TestClient] = []

    def abrir(ip: str | None = None) -> TestClient:
        extra = {'client': (ip, 50000)} if ip else {}
        c = TestClient(app, base_url='https://testserver', **extra)
        c.__enter__()
        abertos.append(c)
        return c

    yield abrir
    for c in abertos:
        c.__exit__(None, None, None)


@pytest.fixture
def lojas(engine_dono):
    """Duas lojas (A e B) com Administrador, Recepção e Profissional e todos os módulos ligados."""
    from tests.fabricas import criar_loja_teste

    return criar_loja_teste(engine_dono, 'loja-a'), criar_loja_teste(engine_dono, 'loja-b')


@pytest.fixture
def clinica(cliente, lojas):
    """Loja A com jornada, clientes, locais, materiais e serviços (ver tests/clinica.py)."""
    from tests.clinica import montar_clinica

    return montar_clinica(cliente, lojas[0])


@pytest.fixture(scope='session')
def servidor() -> Iterator[str]:
    """API rodando de verdade (uvicorn numa thread) para os testes de concorrência.

    Cada requisição usa uma conexão própria do pool, como em produção: duas requisições ao mesmo
    tempo disputam as mesmas linhas no banco (ver tests/concorrencia.py).
    """
    import socket
    import threading
    import time

    import uvicorn

    from app.main import app

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        porta = sock.getsockname()[1]
    servidor_uvicorn = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=porta, log_level='warning'))
    thread = threading.Thread(target=servidor_uvicorn.run, daemon=True)
    thread.start()
    limite = time.monotonic() + 15
    while not servidor_uvicorn.started:
        if time.monotonic() > limite:
            raise RuntimeError('O servidor de teste não subiu.')
        time.sleep(0.05)
    yield f'http://127.0.0.1:{porta}'
    servidor_uvicorn.should_exit = True
    thread.join(10)
