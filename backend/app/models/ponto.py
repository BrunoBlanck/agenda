"""Controle de tempo (estrutura.md, 2.16)."""

import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin
from app.models.enums import OrigemPonto, pg_enum


class RegistroPonto(IdMixin, LojaMixin, Base):
    __tablename__ = 'registros_ponto'

    funcionario_id: Mapped[uuid.UUID]
    entrada: Mapped[datetime]
    saida: Mapped[datetime | None]
    origem: Mapped[OrigemPonto] = mapped_column(
        pg_enum(OrigemPonto, 'origem_ponto'), server_default='sistema'
    )
    editado_por: Mapped[uuid.UUID | None]
    justificativa: Mapped[str | None] = mapped_column(Text)
