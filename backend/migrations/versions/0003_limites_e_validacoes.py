"""Proteção contra abuso, CPF/telefone no formato canônico e ponto sem períodos sobrepostos.

- Schema ``limites`` (tabela ``contadores``): estado do limite de requisições e do bloqueio de
  login (app/limites.py). É uma tabela técnica, fora do domínio: sem colunas de controle, auditoria
  nem RLS (contaria cada requisição), e sem dado pessoal legível (as chaves são HMAC).
- CPF (clientes e funcionários) passa a ser gravado sempre como 000.000.000-00 e o telefone como
  (11) 98888-1111. Os registros existentes são normalizados quando dá: CPF com 11 dígitos e
  telefone com DDD (10 ou 11 dígitos). Um CPF que colidiria com outro cadastro ativo da mesma loja
  fica como está (precisa de conferência manual). O que não pode ser normalizado também fica.
- Índice pelos dígitos do telefone do cliente: a busca do painel e o site acham o cadastro com ou
  sem máscara.
- Registros de ponto do mesmo funcionário não se sobrepõem (EXCLUDE com tstzrange; registro em
  aberto vale até o infinito).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.config import get_settings

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DIGITOS = "regexp_replace({coluna}, '\\D', '', 'g')"


def _cpf_canonico(tabela: str) -> str:
    d = _DIGITOS.format(coluna='t.cpf')
    o = _DIGITOS.format(coluna='o.cpf')
    return f"""
        UPDATE {tabela} t
           SET cpf = substr({d}, 1, 3) || '.' || substr({d}, 4, 3) || '.' || substr({d}, 7, 3)
                     || '-' || substr({d}, 10, 2)
         WHERE t.cpf IS NOT NULL
           AND length({d}) = 11
           AND t.cpf !~ '^[0-9]{{3}}\\.[0-9]{{3}}\\.[0-9]{{3}}-[0-9]{{2}}$'
           AND (t.excluido_em IS NOT NULL OR NOT EXISTS (
                 SELECT 1 FROM {tabela} o
                  WHERE o.loja_id = t.loja_id AND o.id <> t.id AND o.excluido_em IS NULL
                    AND o.cpf IS NOT NULL AND {o} = {d}));
    """


def _telefone_canonico(tabela: str) -> str:
    d = _DIGITOS.format(coluna='telefone')
    return f"""
        UPDATE {tabela}
           SET telefone = '(' || substr({d}, 1, 2) || ') ' || substr({d}, 3, length({d}) - 6)
                          || '-' || right({d}, 4)
         WHERE telefone IS NOT NULL
           AND length({d}) IN (10, 11)
           AND left({d}, 1) <> '0'
           AND telefone !~ '^\\([0-9]{{2}}\\) [0-9]{{4,5}}-[0-9]{{4}}$';
    """


def upgrade() -> None:
    papel = get_settings().papel_app
    op.execute(f"""
        CREATE SCHEMA limites;
        CREATE TABLE limites.contadores (
          chave          text PRIMARY KEY,
          contagem       integer NOT NULL CHECK (contagem > 0),
          expira_em      timestamptz NOT NULL,
          bloqueado_ate  timestamptz
        );
        CREATE INDEX contadores_expira_idx ON limites.contadores (expira_em);
        GRANT USAGE ON SCHEMA limites TO "{papel}";
        GRANT SELECT, INSERT, UPDATE, DELETE ON limites.contadores TO "{papel}";
    """)

    # A normalização passa pelos triggers: fica na auditoria como alteração do sistema
    op.execute("SELECT set_config('app.origem', 'sistema', true)")
    for tabela in ('clientes', 'funcionarios'):
        op.execute(_cpf_canonico(tabela))
        op.execute(_telefone_canonico(tabela))
    op.execute(
        f'CREATE INDEX clientes_telefone_digitos_idx ON clientes (loja_id, {_DIGITOS.format(coluna="telefone")})'
    )

    sobrepostos = (
        op.get_bind()
        .execute(
            text("""
                SELECT count(*) FROM registros_ponto a
                  JOIN registros_ponto b ON b.funcionario_id = a.funcionario_id AND b.id > a.id
                 WHERE a.excluido_em IS NULL AND b.excluido_em IS NULL
                   AND tstzrange(a.entrada, a.saida) && tstzrange(b.entrada, b.saida)
            """)
        )
        .scalar()
    )
    if sobrepostos:
        raise RuntimeError(
            f'Há {sobrepostos} par(es) de registros de ponto sobrepostos do mesmo funcionário. '
            'Corrija (ou exclua) esses registros antes de rodar esta migração.'
        )
    op.execute("""
        ALTER TABLE registros_ponto ADD CONSTRAINT registros_ponto_sem_sobreposicao EXCLUDE USING gist (
          funcionario_id WITH =,
          tstzrange(entrada, saida) WITH &&
        ) WHERE (excluido_em IS NULL);
    """)


def downgrade() -> None:
    # Os CPFs e telefones normalizados continuam no formato novo (não há como voltar ao texto original)
    op.execute("""
        ALTER TABLE registros_ponto DROP CONSTRAINT registros_ponto_sem_sobreposicao;
        DROP INDEX clientes_telefone_digitos_idx;
        DROP SCHEMA limites CASCADE;
    """)
