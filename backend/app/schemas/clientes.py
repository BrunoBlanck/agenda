"""Clientes (estrutura.md, 2.7)."""

from datetime import date
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import CanalCliente
from app.schemas.comum import (
    Controle,
    Cpf,
    DataNascimento,
    EmailOpcional,
    Entrada,
    Telefone,
    texto,
    texto_opcional,
)


class ClienteEntrada(Entrada):
    nome: texto(60) = Field(description='Só o primeiro nome (como a loja chama o cliente)')
    sobrenome: texto(100)
    cpf: Cpf = None
    telefone: Telefone
    email: EmailOpcional = None
    data_nascimento: DataNascimento = None
    observacoes: texto_opcional() = None
    canais: list[CanalCliente] = Field(default_factory=lambda: [CanalCliente.loja], max_length=10)
    ativo: bool = True

    @field_validator('canais')
    @classmethod
    def _sem_repetidos(cls, canais: list[CanalCliente]) -> list[CanalCliente]:
        return list(dict.fromkeys(canais))


class ClienteSaida(Controle):
    id: UUID
    nome: str
    sobrenome: str
    cpf: str | None
    telefone: str
    email: str | None
    data_nascimento: date | None
    observacoes: str | None
    canais: list[CanalCliente]
    ativo: bool
