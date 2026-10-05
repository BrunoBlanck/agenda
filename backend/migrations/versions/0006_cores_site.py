"""Cores do site do consumidor escolhidas pela loja (SIT-13, SIT-14).

``loja_configuracoes`` ganha ``cor_site_topo`` e ``cor_site_destaque`` (``#rrggbb`` em minúsculas, ou
NULL = cor da paleta do tipo da loja, SIT-09). O CHECK de formato é a última barreira: a API normaliza
(maiúsculas viram minúsculas) e confere o contraste com o texto branco antes de gravar. Os triggers de
alteração e de auditoria da tabela já existem e passam a registrar as colunas novas.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUNAS = ('cor_site_topo', 'cor_site_destaque')


def upgrade() -> None:
    for coluna in COLUNAS:  # nomes fixos do código (nada vem de fora)
        op.execute(f"""
            ALTER TABLE loja_configuracoes
              ADD COLUMN {coluna} varchar(7),
              ADD CONSTRAINT ck_loja_configuracoes_{coluna}
                CHECK ({coluna} IS NULL OR {coluna} ~ '^#[0-9a-f]{{6}}$')
        """)


def downgrade() -> None:
    for coluna in COLUNAS:
        op.execute(f'ALTER TABLE loja_configuracoes DROP COLUMN {coluna}')
