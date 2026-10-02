"""Ambiente do Alembic. Conecta como dono do schema (DATABASE_OWNER_URL).

Para apontar para outro banco (ex.: testes), passe a URL em config.attributes['url'].
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None and not config.attributes.get('sem_log'):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get('url') or get_settings().database_owner_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
