"""Notificações para o cliente e para o profissional (estrutura.md, 2.24; NOT-01 a NOT-08)."""

import uuid
from datetime import datetime

from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin


class Notificacao(IdMixin, LojaMixin, Base):
    """Um aviso, com o texto congelado na criação e o status de cada canal (NOT-04)."""

    __tablename__ = 'notificacoes'

    tipo: Mapped[str] = mapped_column(String(10))  # cliente | loja
    cliente_id: Mapped[uuid.UUID | None]
    funcionario_id: Mapped[uuid.UUID | None]
    agendamento_id: Mapped[uuid.UUID | None]
    evento: Mapped[str] = mapped_column(String(30))
    titulo: Mapped[str] = mapped_column(String(120))
    mensagem: Mapped[str] = mapped_column(String(1000))
    status_site: Mapped[int] = mapped_column(SmallInteger, server_default='1')
    visualizada_em: Mapped[datetime | None]
    status_email: Mapped[int] = mapped_column(SmallInteger)
    email_destino: Mapped[str | None] = mapped_column(String(254))
    email_tentativas: Mapped[int] = mapped_column(SmallInteger, server_default='0')
    email_proxima_tentativa_em: Mapped[datetime | None]
    email_enviado_em: Mapped[datetime | None]
    email_erro: Mapped[str | None] = mapped_column(String(300))
    status_whatsapp: Mapped[int] = mapped_column(SmallInteger)
    whatsapp_erro: Mapped[str | None] = mapped_column(String(300))
    lembrete_inicio: Mapped[datetime | None]
