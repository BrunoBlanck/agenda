"""Clientes (estrutura.md, 2.7)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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


# --- Acesso do cliente ao site (CLI-06, SIT-16 a SIT-20) ---------------------------------------------


class ClienteDoCodigo(BaseModel):
    id: UUID
    nome: str = Field(description='Nome completo (nome + sobrenome)')


class CodigoSiteSaida(BaseModel):
    """Código de confirmação aguardando uso, que a loja repassa ao cliente (provedor "painel")."""

    telefone: str = Field(description='(11) 98888-1111')
    codigo: str = Field(description='6 dígitos')
    expira_em: datetime
    criado_em: datetime
    clientes: list[ClienteDoCodigo] = Field(description='Clientes com o telefone (vazia: sem cadastro)')


class CodigoPendente(BaseModel):
    codigo: str
    expira_em: datetime


class ContaSiteSaida(BaseModel):
    possui_conta: bool
    criada_em: datetime | None
    ultimo_acesso_em: datetime | None
    codigo_pendente: CodigoPendente | None
