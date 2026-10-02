"""Materiais e estoque (estrutura.md, 2.10, 2.11 e 2.15)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin, default_do_banco, gerado_pelo_banco
from app.models.enums import TipoMovimentacao, pg_enum


class CategoriaMaterial(IdMixin, LojaMixin, Base):
    __tablename__ = 'categorias_material'

    nome: Mapped[str] = mapped_column(String(80))


class Material(IdMixin, LojaMixin, Base):
    __tablename__ = 'materiais'

    categoria_id: Mapped[uuid.UUID | None]
    nome: Mapped[str] = mapped_column(String(150))
    unidade: Mapped[str] = mapped_column(String(10))
    # Só muda por movimentacoes_estoque (o banco recusa alteração direta)
    quantidade_atual: Mapped[Decimal] = gerado_pelo_banco(type_=Numeric(10, 2))
    estoque_minimo: Mapped[Decimal] = mapped_column(Numeric(10, 2), server_default='0')
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class MovimentacaoEstoque(IdMixin, LojaMixin, Base):
    """Entrada ou saída de material. Positiva = entrada, negativa = saída."""

    __tablename__ = 'movimentacoes_estoque'

    material_id: Mapped[uuid.UUID]
    tipo: Mapped[TipoMovimentacao] = mapped_column(pg_enum(TipoMovimentacao, 'tipo_movimentacao'))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    agendamento_id: Mapped[uuid.UUID | None]
    funcionario_id: Mapped[uuid.UUID | None] = default_do_banco()
    motivo: Mapped[str | None] = mapped_column(String(200))
