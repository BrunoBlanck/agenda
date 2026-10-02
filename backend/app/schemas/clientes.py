"""Clientes (estrutura.md, 2.7)."""

from datetime import date
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import CanalCliente
from app.schemas.comum import Controle, EmailOpcional, Entrada, texto, texto_opcional


class ClienteEntrada(Entrada):
    nome: texto(60) = Field(description='Só o primeiro nome (como a loja chama o cliente)')
    sobrenome: texto(100)
    cpf: texto_opcional(14) = None
    telefone: texto(20)
    email: EmailOpcional = None
    data_nascimento: date | None = None
    observacoes: texto_opcional() = None
    canais: list[CanalCliente] = Field(default_factory=lambda: [CanalCliente.loja])
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
