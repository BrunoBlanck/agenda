"""Conta do cliente no site (SIT-16 a SIT-20): ``cliente_contas`` e ``cliente_codigos``.

- **cliente_contas:** uma por (loja, telefone só com dígitos), com a senha (Argon2) e a versão da
  sessão (``sessao_versao``: trocar a senha ou a loja remover o acesso incrementa e derruba todas as
  sessões). Não pertence a um registro de cliente: enxerga os agendamentos de todos os clientes da loja
  com aquele telefone (SIT-16). Remover o acesso = exclusão lógica (o telefone pode criar outra conta).
- **cliente_codigos:** códigos de 6 dígitos que confirmam o telefone (SIT-17). Legíveis de propósito: o
  provedor "painel" mostra o código à loja. "Pendente" = não usado, não invalidado, dentro da validade e
  com menos de 20 tentativas erradas no total (e no máximo 5 por IP, contadas em ``app/limites.py``).

As duas são tabelas da loja como as outras (GER-04, GER-08 a GER-12): ``loja_id`` + RLS, colunas de
controle, triggers de alteração, exclusão lógica e auditoria, FKs de controle.

A auditoria passa a mascarar também ``cliente_codigos.codigo`` (além de ``senha_hash`` em toda tabela).
O login do cliente (``ultimo_acesso_em``) fica fora do histórico como o do funcionário (``ultimo_login_em``,
migração 0004). O downgrade volta as duas funções ao corpo da 0004.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06
"""

from collections.abc import Sequence

from alembic import op

from migrations.auxiliares import CONTROLE_LOJA, fks_controle_loja, tabela_loja

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS = ('cliente_contas', 'cliente_codigos')

DESVIO_LOGIN_AUDITORIA = """
            IF current_setting('app.login', true) = 'sim' AND so_dados_de_login(velho, novo) THEN
              RETURN NULL; -- login: fora do histórico
            END IF;"""

# Colunas que nunca vão para antes/depois da auditoria (só aparecem em campos_alterados)
MASCARA_0004 = "'senha_hash'"
MASCARA_0007 = (
    "(ARRAY['senha_hash'] || CASE WHEN TG_TABLE_NAME = 'cliente_codigos' "
    "THEN ARRAY['codigo'] ELSE ARRAY[]::text[] END)"
)


def _auditoria(mascara: str) -> str:
    """``registrar_auditoria`` da 0004, com as colunas mascaradas em ``mascara``."""
    return f"""
        CREATE OR REPLACE FUNCTION registrar_auditoria() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          novo jsonb := to_jsonb(NEW);
          velho jsonb;
          op operacao_auditoria;
          campos text[];
          chave text;
        BEGIN
          IF TG_OP = 'UPDATE' THEN
            velho := to_jsonb(OLD);{DESVIO_LOGIN_AUDITORIA}
            SELECT array_agg(n.key ORDER BY n.key) INTO campos
              FROM jsonb_each(novo) n
             WHERE n.value IS DISTINCT FROM velho -> n.key
               AND n.key NOT IN ('atualizado_em', 'atualizado_por',
                                 'atualizado_por_funcionario', 'atualizado_por_superadmin');
            IF campos IS NULL THEN
              RETURN NULL;
            END IF;
          END IF;

          op := CASE
            WHEN TG_OP = 'INSERT' THEN 'inserir'
            WHEN OLD.excluido_em IS NULL AND NEW.excluido_em IS NOT NULL THEN 'excluir'
            WHEN OLD.excluido_em IS NOT NULL AND NEW.excluido_em IS NULL THEN 'restaurar'
            ELSE 'alterar'
          END;

          SELECT string_agg(novo ->> a.coluna, ':' ORDER BY a.ordem) INTO chave
            FROM unnest(TG_ARGV) WITH ORDINALITY AS a(coluna, ordem);

          INSERT INTO auditoria (loja_id, tabela, registro_id, operacao, antes, depois,
                                 campos_alterados, funcionario_id, superadmin_id, origem, ip)
          VALUES (
            CASE WHEN TG_TABLE_NAME = 'lojas' THEN (novo ->> 'id')::uuid
                 ELSE (novo ->> 'loja_id')::uuid END,
            TG_TABLE_NAME,
            chave,
            op,
            velho - {mascara},
            novo - {mascara},
            CASE WHEN op = 'alterar' THEN campos END,
            contexto_uuid('app.funcionario_id'),
            contexto_uuid('app.superadmin_id'),
            coalesce(nullif(current_setting('app.origem', true), ''), 'sistema')::origem_auditoria,
            nullif(current_setting('app.ip', true), '')::inet
          );
          RETURN NULL;
        END $$;
    """


def _dados_de_login(colunas: str) -> str:
    """``so_dados_de_login`` da 0004 com a lista de colunas de acesso."""
    return f"""
        CREATE OR REPLACE FUNCTION so_dados_de_login(velho jsonb, novo jsonb) RETURNS boolean
          LANGUAGE sql IMMUTABLE AS
        $$ SELECT NOT EXISTS (
             SELECT 1 FROM jsonb_each(novo) n
              WHERE n.value IS DISTINCT FROM velho -> n.key
                AND n.key NOT IN ({colunas})) $$;
    """


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE cliente_contas (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id           uuid NOT NULL REFERENCES lojas (id),
          telefone_digitos  varchar(11) NOT NULL
                            CONSTRAINT ck_cliente_contas_telefone CHECK (telefone_digitos ~ '^[0-9]{{10,11}}$'),
          senha_hash        text NOT NULL,
          sessao_versao     integer NOT NULL DEFAULT 1
                            CONSTRAINT ck_cliente_contas_versao CHECK (sessao_versao >= 1),
          ultimo_acesso_em  timestamptz,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX cliente_contas_telefone_uk
          ON cliente_contas (loja_id, telefone_digitos) WHERE excluido_em IS NULL;

        CREATE TABLE cliente_codigos (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id           uuid NOT NULL REFERENCES lojas (id),
          telefone_digitos  varchar(11) NOT NULL
                            CONSTRAINT ck_cliente_codigos_telefone CHECK (telefone_digitos ~ '^[0-9]{{10,11}}$'),
          codigo            char(6) NOT NULL CONSTRAINT ck_cliente_codigos_codigo CHECK (codigo ~ '^[0-9]{{6}}$'),
          expira_em         timestamptz NOT NULL,
          tentativas        smallint NOT NULL DEFAULT 0
                            CONSTRAINT ck_cliente_codigos_tentativas CHECK (tentativas BETWEEN 0 AND 20),
          usado_em          timestamptz,
          invalidado_em     timestamptz,
          provedor          varchar(20) NOT NULL
                            CONSTRAINT ck_cliente_codigos_provedor CHECK (provedor ~ '^[a-z_]{{1,20}}$'),
          {CONTROLE_LOJA},
          CONSTRAINT ck_cliente_codigos_validade CHECK (expira_em > criado_em)
        );
        CREATE INDEX cliente_codigos_telefone_idx
          ON cliente_codigos (loja_id, telefone_digitos, criado_em DESC);
        -- Lista de códigos aguardando uso no painel (GET /api/loja/clientes/codigos-site)
        CREATE INDEX cliente_codigos_abertos_idx ON cliente_codigos (loja_id, criado_em DESC)
          WHERE usado_em IS NULL AND invalidado_em IS NULL AND excluido_em IS NULL;
    """)
    for tabela in TABELAS:
        tabela_loja(tabela)
        fks_controle_loja(tabela)

    op.execute(_auditoria(MASCARA_0007))
    op.execute(_dados_de_login("'ultimo_login_em', 'ultimo_acesso_em', 'senha_hash'"))


def downgrade() -> None:
    op.execute(_dados_de_login("'ultimo_login_em', 'senha_hash'"))
    op.execute(_auditoria(MASCARA_0004))
    for tabela in reversed(TABELAS):
        op.execute(f'DROP TABLE {tabela}')
