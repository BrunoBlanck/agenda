"""Jornadas, bloqueios e agendamentos (estrutura.md, 2.5, 2.6, 2.13 e 2.14)."""

import uuid
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import Numeric, SmallInteger, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin, default_do_banco
from app.models.enums import OrigemAgendamento, StatusAgendamento, pg_enum


class PerfilHorario(IdMixin, LojaMixin, Base):
    """Faixa da jornada semanal de um perfil (0 = domingo ... 6 = sábado)."""

    __tablename__ = 'perfil_horarios'

    perfil_id: Mapped[uuid.UUID]
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fim: Mapped[time] = mapped_column(Time)


class BloqueioAgenda(IdMixin, LojaMixin, Base):
    """Período sem agendamento: loja inteira, um perfil ou um funcionário."""

    __tablename__ = 'bloqueios_agenda'

    perfil_id: Mapped[uuid.UUID | None]
    funcionario_id: Mapped[uuid.UUID | None]
    inicio: Mapped[datetime]
    fim: Mapped[datetime]
    motivo: Mapped[str | None] = mapped_column(String(150))
    criado_por: Mapped[uuid.UUID | None] = default_do_banco()


class Agendamento(IdMixin, LojaMixin, Base):
    __tablename__ = 'agendamentos'

    cliente_id: Mapped[uuid.UUID]
    servico_id: Mapped[uuid.UUID | None]
    funcionario_id: Mapped[uuid.UUID]
    local_id: Mapped[uuid.UUID | None]
    link_reuniao: Mapped[str | None] = mapped_column(String(500))
    inicio: Mapped[datetime]
    fim: Mapped[datetime]
    preco: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[StatusAgendamento] = mapped_column(
        pg_enum(StatusAgendamento, 'status_agendamento'), server_default='agendado'
    )
    origem: Mapped[OrigemAgendamento] = mapped_column(
        pg_enum(OrigemAgendamento, 'origem_agendamento'), server_default='painel'
    )
    observacoes: Mapped[str | None] = mapped_column(Text)
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = default_do_banco()


class AgendamentoMaterial(LojaMixin, Base):
    """Materiais efetivamente usados no atendimento."""

    __tablename__ = 'agendamento_materiais'

    agendamento_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    material_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(10, 2))
