"""Locais de atendimento e configurações da loja (estrutura.md, 2.19 e 2.21)."""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ControleMixin, IdMixin, LojaMixin, gerado_pelo_banco
from app.models.enums import TipoLocal, pg_enum


class Local(IdMixin, LojaMixin, Base):
    __tablename__ = 'locais'

    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoLocal] = mapped_column(pg_enum(TipoLocal, 'tipo_local'), server_default='presencial')
    link_padrao: Mapped[str | None] = mapped_column(String(500))
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class LojaConfiguracao(ControleMixin, Base):
    """Opções da loja que não são dados cadastrais. Uma linha por loja."""

    __tablename__ = 'loja_configuracoes'

    loja_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rotulo_local: Mapped[str] = mapped_column(String(40), server_default='Local')
    rotulo_local_plural: Mapped[str] = mapped_column(String(40), server_default='Locais')
    atualizado_por: Mapped[uuid.UUID | None] = gerado_pelo_banco()
