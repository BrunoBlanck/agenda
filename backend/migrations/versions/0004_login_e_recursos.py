"""Login fora do histórico e textos de leitura/escrita do catálogo de recursos.

- **Login não é alteração.** O login grava ``ultimo_login_em`` (e, quando o Argon2 pede, o novo hash
  da mesma senha). Com a transação marcada como login (``app.login = 'sim'``, ver
  ``app.db.definir_contexto``), o UPDATE que só muda essas duas colunas não troca
  ``atualizado_em``/``atualizado_por`` nem grava linha na ``auditoria``. Qualquer outra coluna
  alterada na mesma linha faz o UPDATE ser tratado normalmente; a troca de senha de verdade
  (edição do funcionário ou do usuário admin, redefinição) não é marcada e continua auditada.
- **recursos.leitura / recursos.escrita:** o que cada nível permite, em colunas próprias (antes só no
  texto ``descricao``, "Leitura: ... Escrita: ...", que continua igual).

As funções de alteração e de auditoria são recriadas (``CREATE OR REPLACE``) com o desvio do login;
o downgrade volta exatamente ao corpo da 0001.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCIONARIO = "contexto_uuid('app.funcionario_id')"
SUPERADMIN = "contexto_uuid('app.superadmin_id')"

# Funções de alteração da 0001: nome -> (quem exclui, comandos extras)
FUNCOES_ALTERACAO = {
    'registrar_alteracao': (SUPERADMIN, ''),
    'registrar_alteracao_loja': (FUNCIONARIO, f'NEW.atualizado_por := {FUNCIONARIO};'),
    'registrar_alteracao_superadmin': (SUPERADMIN, f'NEW.atualizado_por := {SUPERADMIN};'),
    'registrar_alteracao_lojas': (
        SUPERADMIN,
        f"""IF {FUNCIONARIO} IS NOT NULL THEN NEW.atualizado_por_funcionario := {FUNCIONARIO}; END IF;
  IF {SUPERADMIN} IS NOT NULL THEN NEW.atualizado_por_superadmin := {SUPERADMIN}; END IF;""",
    ),
}

# Em transação de login, um UPDATE que só mexe nestas colunas não é alteração do cadastro
LOGIN = "TG_OP = 'UPDATE' AND current_setting('app.login', true) = 'sim'"

DESVIO_LOGIN_ALTERACAO = f"""
  IF {LOGIN} THEN
    IF so_dados_de_login(to_jsonb(OLD), to_jsonb(NEW)) THEN
      RETURN NEW; -- login: não muda a "última alteração"
    END IF;
  END IF;"""

DESVIO_LOGIN_AUDITORIA = """
            IF current_setting('app.login', true) = 'sim' AND so_dados_de_login(velho, novo) THEN
              RETURN NULL; -- login: fora do histórico
            END IF;"""


def _corpo_alteracao(quem_exclui: str, atualizacao: str, desvio_login: str) -> str:
    """Mesmo corpo da 0001 (``_corpo_alteracao``), com o desvio do login no início."""
    return f"""
BEGIN{desvio_login}
  NEW.atualizado_em := now();
  IF TG_OP = 'INSERT' THEN
    NEW.criado_em := now();
    NEW.excluido_em := NULL;
    NEW.excluido_por := NULL;
  ELSE
    NEW.criado_em := OLD.criado_em;
    IF OLD.excluido_em IS NULL AND NEW.excluido_em IS NOT NULL THEN
      NEW.excluido_em := now();
      NEW.excluido_por := {quem_exclui};
    ELSIF NEW.excluido_em IS NULL THEN
      NEW.excluido_por := NULL;
    ELSE
      NEW.excluido_em := OLD.excluido_em;
      NEW.excluido_por := OLD.excluido_por;
    END IF;
  END IF;
  {atualizacao}
  RETURN NEW;
END
"""


def _auditoria(desvio_login: str) -> str:
    """Mesma função da 0001 (``registrar_auditoria``), com o desvio do login no UPDATE."""
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
            velho := to_jsonb(OLD);{desvio_login}
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
            velho - 'senha_hash',
            novo - 'senha_hash',
            CASE WHEN op = 'alterar' THEN campos END,
            contexto_uuid('app.funcionario_id'),
            contexto_uuid('app.superadmin_id'),
            coalesce(nullif(current_setting('app.origem', true), ''), 'sistema')::origem_auditoria,
            nullif(current_setting('app.ip', true), '')::inet
          );
          RETURN NULL;
        END $$;
    """


def _recriar_funcoes(desvio_alteracao: str, desvio_auditoria: str) -> None:
    for nome, (quem_exclui, atualizacao) in FUNCOES_ALTERACAO.items():
        op.execute(
            f'CREATE OR REPLACE FUNCTION {nome}() RETURNS trigger LANGUAGE plpgsql AS $$'
            f'{_corpo_alteracao(quem_exclui, atualizacao, desvio_alteracao)}$$;'
        )
    op.execute(_auditoria(desvio_auditoria))


def upgrade() -> None:
    op.execute("""
        -- O UPDATE só mudou dados de acesso (último login e hash da senha)?
        CREATE FUNCTION so_dados_de_login(velho jsonb, novo jsonb) RETURNS boolean
          LANGUAGE sql IMMUTABLE AS
        $$ SELECT NOT EXISTS (
             SELECT 1 FROM jsonb_each(novo) n
              WHERE n.value IS DISTINCT FROM velho -> n.key
                AND n.key NOT IN ('ultimo_login_em', 'senha_hash')) $$;
    """)
    _recriar_funcoes(DESVIO_LOGIN_ALTERACAO, DESVIO_LOGIN_AUDITORIA)

    # Textos de leitura e escrita a partir da descrição gravada pela 0002 ("Leitura: X. Escrita: Y.")
    op.execute(r"""
        ALTER TABLE recursos ADD COLUMN leitura varchar(200), ADD COLUMN escrita varchar(200);
        UPDATE recursos r
           SET leitura = p.partes[1], escrita = p.partes[2]
          FROM (SELECT id, regexp_match(descricao, '^Leitura: (.*)\. Escrita: (.*)\.$') AS partes
                  FROM recursos) p
         WHERE p.id = r.id;
        ALTER TABLE recursos ALTER COLUMN leitura SET NOT NULL, ALTER COLUMN escrita SET NOT NULL;
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE recursos DROP COLUMN leitura, DROP COLUMN escrita;')
    _recriar_funcoes('', '')
    op.execute('DROP FUNCTION so_dados_de_login(jsonb, jsonb);')
