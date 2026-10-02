"""Plataforma (SUPERADMIN): estrutura.md, seção 1."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ControleMixin, IdMixin, default_do_banco, gerado_pelo_banco
from app.models.enums import (
    OperacaoAuditoria,
    OrigemAuditoria,
    StatusLoja,
    TipoLoja,
    pg_enum,
)


class SuperadminUsuario(IdMixin, ControleMixin, Base):
    __tablename__ = 'superadmin_usuarios'

    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150))
    senha_hash: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')
    ultimo_login_em: Mapped[datetime | None]


class Plano(IdMixin, ControleMixin, Base):
    __tablename__ = 'planos'

    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str | None] = mapped_column(Text)
    preco_mensal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class Funcionalidade(IdMixin, ControleMixin, Base):
    """Catálogo fixo de módulos (mantido por migração)."""

    __tablename__ = 'funcionalidades'

    codigo: Mapped[str] = mapped_column(String(50))
    nome: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(Text)
    opcional: Mapped[bool] = mapped_column(Boolean)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class Recurso(IdMixin, ControleMixin, Base):
    """Catálogo fixo de áreas com nível de acesso (mantido por migração)."""

    __tablename__ = 'recursos'

    funcionalidade_id: Mapped[uuid.UUID]
    codigo: Mapped[str] = mapped_column(String(50))
    nome: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(Text)
    ordem: Mapped[int | None] = mapped_column(SmallInteger)


class Loja(IdMixin, ControleMixin, Base):
    __tablename__ = 'lojas'

    tipo: Mapped[TipoLoja] = mapped_column(pg_enum(TipoLoja, 'tipo_loja'))
    nome: Mapped[str] = mapped_column(String(150))
    nome_fantasia: Mapped[str | None] = mapped_column(String(150))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(150))
    telefone: Mapped[str | None] = mapped_column(String(20))
    cep: Mapped[str | None] = mapped_column(String(9))
    logradouro: Mapped[str | None] = mapped_column(String(150))
    numero: Mapped[str | None] = mapped_column(String(10))
    complemento: Mapped[str | None] = mapped_column(String(80))
    bairro: Mapped[str | None] = mapped_column(String(80))
    cidade: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(2))
    fuso_horario: Mapped[str] = mapped_column(String(50), server_default='America/Sao_Paulo')
    plano_id: Mapped[uuid.UUID | None]
    status: Mapped[StatusLoja] = mapped_column(pg_enum(StatusLoja, 'status_loja'), server_default='ativa')
    criado_por: Mapped[uuid.UUID | None] = default_do_banco()
    atualizado_por_funcionario: Mapped[uuid.UUID | None] = gerado_pelo_banco()
    atualizado_por_superadmin: Mapped[uuid.UUID | None] = gerado_pelo_banco()


class LojaFuncionalidade(ControleMixin, Base):
    """Módulos opcionais ligados ou desligados em cada loja."""

    __tablename__ = 'loja_funcionalidades'

    loja_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    funcionalidade_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    habilitado: Mapped[bool] = mapped_column(Boolean)
    observacao: Mapped[str | None] = mapped_column(Text)
    expira_em: Mapped[datetime | None]
    atualizado_por: Mapped[uuid.UUID | None] = gerado_pelo_banco()


class Auditoria(Base):
    """Histórico de alterações. Somente inserção, preenchida por trigger."""

    __tablename__ = 'auditoria'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    loja_id: Mapped[uuid.UUID | None]
    tabela: Mapped[str] = mapped_column(String(60))
    registro_id: Mapped[str] = mapped_column(Text)
    operacao: Mapped[OperacaoAuditoria] = mapped_column(pg_enum(OperacaoAuditoria, 'operacao_auditoria'))
    antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    depois: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    campos_alterados: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    funcionario_id: Mapped[uuid.UUID | None]
    superadmin_id: Mapped[uuid.UUID | None]
    origem: Mapped[OrigemAuditoria] = mapped_column(pg_enum(OrigemAuditoria, 'origem_auditoria'))
    ip: Mapped[str | None] = mapped_column(INET)
    criado_em: Mapped[datetime] = gerado_pelo_banco()
