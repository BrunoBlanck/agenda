"""Pagamento do atendimento (AGE-26 a AGE-29): ``agendamento_pagamentos`` e o tipo ``forma_pagamento``.

- **agendamento_pagamentos:** o pagamento que conclui o atendimento (forma, valor, quando e quem registrou).
  Tabela da loja como as outras (GER-04, GER-08 a GER-12): ``loja_id`` + RLS, colunas de controle,
  triggers de alteração, exclusão lógica e auditoria, FKs de controle e FKs compostas.
- **Um pagamento ativo por agendamento** (AGE-27): índice único parcial ``agendamento_pagamentos_ativo_uk``.
  Reabrir o atendimento exclui o pagamento logicamente (AGE-28), e concluir de novo grava outro.
- ``valor >= 0`` (zero = cortesia). ``pago_em`` e ``criado_por`` vêm do banco (hora do servidor e o
  funcionário do contexto da transação).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-07
"""

from collections.abc import Sequence

from alembic import op

from migrations.auxiliares import CONTROLE_LOJA, fks_controle_loja, tabela_loja

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TYPE forma_pagamento AS ENUM ('credito', 'debito', 'dinheiro', 'pix');

        CREATE TABLE agendamento_pagamentos (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          agendamento_id  uuid NOT NULL,
          forma           forma_pagamento NOT NULL,
          valor           numeric(10,2) NOT NULL
                          CONSTRAINT ck_agendamento_pagamentos_valor CHECK (valor >= 0),
          pago_em         timestamptz NOT NULL DEFAULT now(),
          criado_por      uuid DEFAULT contexto_uuid('app.funcionario_id'),
          {CONTROLE_LOJA},
          -- Quem excluiu só existe com a exclusão (o superadmin e o sistema excluem com excluido_por NULL)
          CONSTRAINT ck_agendamento_pagamentos_exclusao CHECK (excluido_por IS NULL OR excluido_em IS NOT NULL),
          CONSTRAINT agendamento_pagamentos_agendamento_fk
            FOREIGN KEY (loja_id, agendamento_id) REFERENCES agendamentos (loja_id, id),
          CONSTRAINT agendamento_pagamentos_criado_por_fk
            FOREIGN KEY (loja_id, criado_por) REFERENCES funcionarios (loja_id, id)
        );
        -- AGE-27: um pagamento ativo por agendamento (também o índice da busca por agendamento)
        CREATE UNIQUE INDEX agendamento_pagamentos_ativo_uk
          ON agendamento_pagamentos (loja_id, agendamento_id) WHERE excluido_em IS NULL;
    """)
    tabela_loja('agendamento_pagamentos')
    fks_controle_loja('agendamento_pagamentos')


def downgrade() -> None:
    op.execute("""
        DROP TABLE agendamento_pagamentos;
        DROP TYPE forma_pagamento;
    """)
