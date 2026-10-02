"""Perfis, níveis de acesso, cargos e funcionários (estrutura.md, 2.1 a 2.4)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, LojaMixin, default_do_banco
from app.models.enums import NivelAcesso, pg_enum


class Perfil(IdMixin, LojaMixin, Base):
    __tablename__ = 'perfis'

    nome: Mapped[str] = mapped_column(String(60))
    descricao: Mapped[str | None] = mapped_column(Text)
    padrao: Mapped[bool] = mapped_column(Boolean, server_default='false')
    acesso_total: Mapped[bool] = mapped_column(Boolean, server_default='false')


class PerfilAcesso(LojaMixin, Base):
    __tablename__ = 'perfil_acessos'

    perfil_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    recurso_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    nivel: Mapped[NivelAcesso] = mapped_column(pg_enum(NivelAcesso, 'nivel_acesso'))


class Cargo(IdMixin, LojaMixin, Base):
    __tablename__ = 'cargos'

    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class Funcionario(IdMixin, LojaMixin, Base):
    """Funcionário da loja. Também é o usuário que faz login no painel."""

    __tablename__ = 'funcionarios'

    perfil_id: Mapped[uuid.UUID]
    cargo_id: Mapped[uuid.UUID | None]
    nome: Mapped[str] = mapped_column(String(150))
    cpf: Mapped[str | None] = mapped_column(String(14))
    email: Mapped[str] = mapped_column(String(150))
    senha_hash: Mapped[str] = mapped_column(String(255))
    telefone: Mapped[str | None] = mapped_column(String(20))
    cor_agenda: Mapped[str | None] = mapped_column(String(7))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')
    ultimo_login_em: Mapped[datetime | None]
    criado_por_funcionario: Mapped[uuid.UUID | None] = default_do_banco()
    criado_por_superadmin: Mapped[uuid.UUID | None] = default_do_banco()
