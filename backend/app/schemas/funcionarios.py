"""Funcionários e cargos (estrutura.md, 2.3 e 2.4)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, EmailStr, Field, StringConstraints

from app.schemas.comum import Controle, Entrada, texto, texto_opcional, vazio_para_none

CorAgenda = Annotated[
    Annotated[str, StringConstraints(pattern=r'^#[0-9a-fA-F]{6}$')] | None,
    BeforeValidator(vazio_para_none),
    Field(description='Cor no calendário, no formato #rrggbb'),
]
Senha = Annotated[str, StringConstraints(min_length=8, max_length=200)]


class CargoEntrada(Entrada):
    nome: texto(80)
    ativo: bool = True


class CargoSaida(Controle):
    id: UUID
    nome: str
    ativo: bool


class FuncionarioEntrada(Entrada):
    nome: texto(150)
    email: EmailStr = Field(description='E-mail de login (único na loja)')
    perfil_id: UUID
    cargo_id: UUID | None = None
    cpf: texto_opcional(14) = None
    telefone: texto_opcional(20) = None
    cor_agenda: CorAgenda = None
    ativo: bool = True
    senha: Senha | None = Field(
        default=None, description='Obrigatória no cadastro. Na edição, só se for trocar a senha.'
    )


class FuncionarioSaida(Controle):
    id: UUID
    nome: str
    email: str
    perfil_id: UUID
    perfil_nome: str | None = None
    perfil_acesso_total: bool = False
    cargo_id: UUID | None
    cargo_nome: str | None = None
    cpf: str | None
    telefone: str | None
    cor_agenda: str | None
    ativo: bool
    ultimo_login_em: datetime | None
