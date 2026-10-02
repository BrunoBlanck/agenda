"""Cria (ou atualiza a senha do) papel do Postgres usado pela aplicação.

O nome e a senha vêm do usuário de DATABASE_URL; a conexão usa DATABASE_OWNER_URL, que precisa
poder criar papéis (no docker compose de desenvolvimento ele é superusuário).

O papel é separado do dono do schema para que o REVOKE na auditoria e o RLS tenham efeito.

Uso: uv run python -m scripts.criar_papel_app
"""

from sqlalchemy import create_engine, make_url, text

from app.config import get_settings


def criar_papel_app(url_dono: str | None = None) -> str:
    settings = get_settings()
    url_app = make_url(settings.database_url.get_secret_value())
    papel, senha = url_app.username, url_app.password
    if not papel or not senha:
        raise SystemExit('DATABASE_URL precisa ter usuário e senha.')

    engine = create_engine(url_dono or settings.database_owner_url.get_secret_value())
    with engine.begin() as conexao:
        existe = conexao.execute(text('SELECT 1 FROM pg_roles WHERE rolname = :p'), {'p': papel}).scalar()
        # Nome vem da configuração (não do usuário final); a senha é passada já escapada pelo próprio Postgres
        comando = 'ALTER ROLE' if existe else 'CREATE ROLE'
        senha_sql = conexao.execute(text('SELECT quote_literal(:s)'), {'s': senha}).scalar()
        papel_sql = conexao.execute(text('SELECT quote_ident(:p)'), {'p': papel}).scalar()
        restricoes = 'NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'
        conexao.execute(text(f'{comando} {papel_sql} LOGIN PASSWORD {senha_sql} {restricoes}'))
    engine.dispose()
    return papel


if __name__ == '__main__':
    nome = criar_papel_app()
    print(f'Papel da aplicação pronto: {nome}')
