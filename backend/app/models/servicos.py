"""Serviços e seus vínculos (estrutura.md, 2.8, 2.9, 2.12 e 2.20)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin


class Servico(IdMixin, LojaMixin, Base):
    __tablename__ = 'servicos'

    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text)
    duracao_minutos: Mapped[int] = mapped_column(Integer)
    preco: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class ServicoFuncionario(LojaMixin, Base):
    """Profissionais que podem realizar o serviço."""

    __tablename__ = 'servico_funcionarios'

    servico_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    funcionario_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)


class ServicoMaterial(LojaMixin, Base):
    """Materiais consumidos por um atendimento do serviço."""

    __tablename__ = 'servico_materiais'

    servico_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    material_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class ServicoLocal(LojaMixin, Base):
    """Locais onde o serviço pode acontecer. Nenhum vínculo = qualquer local ativo."""

    __tablename__ = 'servico_locais'

    servico_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    local_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
