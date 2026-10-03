"""Endereços reservados pelo sistema não podem ser slug de loja (PLA-16, GER-29).

O slug vira o primeiro trecho da URL (``/clinica-sorriso``, ``/clinica-sorriso/painel``), então não
pode coincidir com caminhos do sistema (``/superadmin``, ``/api``, ``/painel``...). CHECK
``ck_lojas_slug_reservado`` em ``lojas``, inclusive nas excluídas (a exclusão é lógica e a linha pode
ser restaurada).

Antes de criar o CHECK, a migração procura lojas (também as excluídas) que já usam um endereço
reservado e, se houver, para com a lista delas: o slug precisa ser trocado à mão (pelo SUPERADMIN ou
por SQL), porque mudar o endereço de uma loja quebra os links que ela já divulgou.

📌 A lista é a mesma de ``app/services/slugs.py`` (``SLUGS_RESERVADOS``), escrita por extenso porque a
migração não importa código da aplicação. ``tests/test_roteamento.py`` confere que as duas batem.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import bindparam, text

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESERVADOS = (
    'superadmin',
    'api',
    'painel',
    'site',
    'docs',
    'redoc',
    'openapi',
    'admin',
    'login',
    'static',
    'assets',
    'app',
    'www',
    'saude',
    'health',
)


def upgrade() -> None:
    em_uso = (
        op.get_bind()
        .execute(
            text(
                'SELECT id, slug, nome, excluido_em IS NOT NULL FROM lojas WHERE slug IN :reservados ORDER BY slug'
            ).bindparams(bindparam('reservados', expanding=True)),
            {'reservados': list(RESERVADOS)},
        )
        .all()
    )
    if em_uso:
        lojas = '; '.join(
            f'"{slug}" ({nome}{", excluída" if excluida else ""}, id {id_})'
            for id_, slug, nome, excluida in em_uso
        )
        raise RuntimeError(
            f'Há loja(s) usando um endereço reservado pelo sistema: {lojas}. '
            'Troque o slug dessas lojas (inclusive as excluídas) e rode a migração de novo.'
        )
    # Lista fixa do código (nenhum valor vem de fora): pode ir literal no DDL
    lista = ', '.join(f"'{slug}'" for slug in RESERVADOS)
    op.execute(f'ALTER TABLE lojas ADD CONSTRAINT ck_lojas_slug_reservado CHECK (slug NOT IN ({lista}))')


def downgrade() -> None:
    op.execute('ALTER TABLE lojas DROP CONSTRAINT ck_lojas_slug_reservado')
