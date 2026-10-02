"""SQL repetido pelas migrações: colunas de controle, triggers, FKs de controle e RLS.

Toda tabela nova deve, na mesma migração:

* ter as colunas de controle (CONTROLE_LOJA ou CONTROLE_PLATAFORMA);
* ligar os triggers com ``ligar_triggers`` (alteração, exclusão lógica e auditoria);
* se for tabela da loja: ``UNIQUE (loja_id, id)``, ``fks_controle_loja`` e ``ligar_rls``;
* usar índice único parcial (``WHERE excluido_em IS NULL``) no lugar de ``UNIQUE``.

📌 Migrações antigas importam estas funções. Não mude o SQL que elas geram: se precisar de outro
comportamento, crie uma função nova (ou uma variante com outro nome).
"""

from collections.abc import Sequence
from typing import Literal

from alembic import op

# Colunas de controle (estrutura.md, "Colunas de controle")
CONTROLE_PLATAFORMA = """
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    excluido_em    timestamptz,
    excluido_por   uuid REFERENCES superadmin_usuarios (id)
"""

CONTROLE_LOJA = """
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    atualizado_por uuid,
    excluido_em    timestamptz,
    excluido_por   uuid
"""

# Qual função de alteração cada tipo de tabela usa (ver 0001: criar_funcoes)
Area = Literal['loja', 'plataforma', 'lojas', 'loja_funcionalidades']
_FUNCAO_ALTERACAO: dict[str, str] = {
    'loja': 'registrar_alteracao_loja',
    'plataforma': 'registrar_alteracao',
    'lojas': 'registrar_alteracao_lojas',
    'loja_funcionalidades': 'registrar_alteracao_superadmin',
}


def _args(chave: Sequence[str]) -> str:
    return ', '.join(f"'{c}'" for c in chave)


def ligar_triggers(tabela: str, area: Area, chave: Sequence[str] = ('id',)) -> None:
    """Liga os três triggers de controle na tabela.

    chave: colunas da chave primária (tabelas de ligação usam a chave composta).
    """
    op.execute(f"""
        CREATE TRIGGER {tabela}_alteracao BEFORE INSERT OR UPDATE ON {tabela}
          FOR EACH ROW EXECUTE FUNCTION {_FUNCAO_ALTERACAO[area]}();
        CREATE TRIGGER {tabela}_excluir BEFORE DELETE ON {tabela}
          FOR EACH ROW EXECUTE FUNCTION excluir_logicamente({_args(chave)});
        CREATE TRIGGER {tabela}_auditoria AFTER INSERT OR UPDATE ON {tabela}
          FOR EACH ROW EXECUTE FUNCTION registrar_auditoria({_args(chave)});
    """)


def fks_controle_loja(tabela: str) -> None:
    """FKs compostas de atualizado_por e excluido_por para funcionários da mesma loja."""
    op.execute(f"""
        ALTER TABLE {tabela}
          ADD CONSTRAINT {tabela}_atualizado_por_fk
            FOREIGN KEY (loja_id, atualizado_por) REFERENCES funcionarios (loja_id, id),
          ADD CONSTRAINT {tabela}_excluido_por_fk
            FOREIGN KEY (loja_id, excluido_por) REFERENCES funcionarios (loja_id, id);
    """)


def ligar_rls(tabela: str) -> None:
    """Row Level Security: só enxerga e grava linhas da loja do contexto (app.loja_id).

    O superadmin (app.superadmin_id preenchido) enxerga todas. O dono do schema não é afetado.
    """
    op.execute(f"""
        ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;
        CREATE POLICY {tabela}_isolamento_loja ON {tabela}
          USING (pode_acessar_loja(loja_id))
          WITH CHECK (pode_acessar_loja(loja_id));
    """)


def tabela_loja(tabela: str, chave: Sequence[str] = ('id',)) -> None:
    """Tudo o que uma tabela do Painel da Loja precisa depois do CREATE TABLE."""
    if chave == ('id',):
        op.execute(f'ALTER TABLE {tabela} ADD CONSTRAINT {tabela}_loja_id_uk UNIQUE (loja_id, id);')
    ligar_triggers(tabela, 'loja', chave)
    ligar_rls(tabela)
