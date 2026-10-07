"""Clientes da loja e a conta deles no site (estrutura.md, 2.7, 2.22 e 2.23)."""

from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, Integer, SmallInteger, String, Text
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


class ClienteConta(IdMixin, LojaMixin, Base):
    """Conta do site (SIT-16): uma por (loja, telefone). Vale para todos os clientes com o telefone."""

    __tablename__ = 'cliente_contas'

    telefone_digitos: Mapped[str] = mapped_column(String(11))
    senha_hash: Mapped[str] = mapped_column(Text)
    sessao_versao: Mapped[int] = mapped_column(Integer, server_default='1')
    ultimo_acesso_em: Mapped[datetime | None]


class ClienteCodigo(IdMixin, LojaMixin, Base):
    """Código que confirma o telefone no site (SIT-17)."""

    __tablename__ = 'cliente_codigos'

    telefone_digitos: Mapped[str] = mapped_column(String(11))
    codigo: Mapped[str] = mapped_column(CHAR(6))
    expira_em: Mapped[datetime]
    tentativas: Mapped[int] = mapped_column(SmallInteger, server_default='0')
    usado_em: Mapped[datetime | None]
    invalidado_em: Mapped[datetime | None]
    provedor: Mapped[str] = mapped_column(String(20))
