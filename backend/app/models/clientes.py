"""Clientes da loja (estrutura.md, 2.7)."""

from datetime import date

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin
from app.models.enums import CanalCliente, pg_enum


class Cliente(IdMixin, LojaMixin, Base):
    __tablename__ = 'clientes'

    nome: Mapped[str] = mapped_column(String(60))
    sobrenome: Mapped[str] = mapped_column(String(100))
    cpf: Mapped[str | None] = mapped_column(String(14))
    telefone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)
    canais: Mapped[list[CanalCliente]] = mapped_column(
        ARRAY(pg_enum(CanalCliente, 'canal_cliente')), server_default='{}'
    )
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')
