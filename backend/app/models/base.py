"""Base declarativa e colunas comuns.

O DDL de verdade está nas migrações (SQL explícito). Os modelos descrevem as colunas para o ORM;
colunas preenchidas pelo banco (triggers e defaults) usam FetchedValue e são relidas após o flush.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, FetchedValue, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }


def gerado_pelo_banco(**kwargs):
    """Coluna preenchida pelo banco no INSERT e no UPDATE (trigger)."""
    return mapped_column(server_default=FetchedValue(), server_onupdate=FetchedValue(), **kwargs)


def default_do_banco(**kwargs):
    """Coluna com DEFAULT no banco (ex.: quem criou, lido do contexto da transação)."""
    return mapped_column(server_default=FetchedValue(), **kwargs)


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text('gen_random_uuid()'))


class ControleMixin:
    """Colunas de controle de todas as tabelas (menos auditoria). Preenchidas por trigger."""

    criado_em: Mapped[datetime] = gerado_pelo_banco()
    atualizado_em: Mapped[datetime] = gerado_pelo_banco()
    excluido_em: Mapped[datetime | None] = gerado_pelo_banco()
    excluido_por: Mapped[uuid.UUID | None] = gerado_pelo_banco()

    @declared_attr.directive
    def __mapper_args__(cls) -> dict:  # noqa: N805
        # Relê os valores gravados pelos triggers logo após INSERT/UPDATE (via RETURNING)
        return {'eager_defaults': True}


class LojaMixin(ControleMixin):
    """Tabelas do Painel da Loja: loja_id obrigatório e quem fez a última alteração."""

    loja_id: Mapped[uuid.UUID] = mapped_column()
    atualizado_por: Mapped[uuid.UUID | None] = gerado_pelo_banco()
