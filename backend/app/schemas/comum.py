"""Schemas compartilhados: paginação, erros, tipos de campo e colunas de controle."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
)


class Esquema(BaseModel):
    """Base dos schemas de saída: aceita objetos do ORM."""

    model_config = ConfigDict(from_attributes=True)


class Entrada(BaseModel):
    """Base dos schemas de entrada: ignora campos desconhecidos (ex.: id, criado_em vindos do front)."""

    model_config = ConfigDict(extra='ignore')


class Paginacao(BaseModel):
    pagina: int
    por_pagina: int

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.por_pagina


def paginacao(
    pagina: Annotated[int, Query(ge=1, description='Página, começando em 1')] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100, description='Itens por página')] = 20,
) -> Paginacao:
    """Dependência para listas que crescem (agendamentos, clientes, auditoria)."""
    return Paginacao(pagina=pagina, por_pagina=por_pagina)


class Pagina[T](BaseModel):
    itens: list[T]
    total: int
    pagina: int
    por_pagina: int


class ErroCampo(BaseModel):
    campo: str
    mensagem: str


class Erro(BaseModel):
    detail: str
    erros: list[ErroCampo] | None = None


# ---------------------------------------------------------------------------------------------
# Tipos de campo
# ---------------------------------------------------------------------------------------------


def vazio_para_none(valor: Any) -> Any:
    """Texto vazio (ou só espaços) vindo de formulário vira None."""
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


def texto(maximo: int | None = None, minimo: int = 1) -> Any:
    """Texto obrigatório, sem espaços nas pontas."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=minimo, max_length=maximo)]


def texto_opcional(maximo: int | None = None) -> Any:
    """Texto opcional: vazio vira None."""
    return Annotated[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=maximo)] | None,
        BeforeValidator(vazio_para_none),
    ]


EmailOpcional = Annotated[EmailStr | None, BeforeValidator(vazio_para_none)]

# Valores numeric(10,2) saem como número no JSON (e não como texto, padrão do Pydantic para Decimal)
_COMO_NUMERO = PlainSerializer(float, return_type=float, when_used='json')
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2), _COMO_NUMERO]
Quantidade = Annotated[Decimal, Field(max_digits=10, decimal_places=2), _COMO_NUMERO]
QuantidadePositiva = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2), _COMO_NUMERO]
DecimalSaida = Annotated[Decimal, _COMO_NUMERO]


class Controle(Esquema):
    """Colunas de controle exibidas na tela (componente UltimaAlteracao do front).

    atualizado_por_nome: funcionário que fez a última alteração. None quando foi o superadmin, o
    site ou uma rotina automática (o front decide o texto a partir de ``origem``, quando houver).
    """

    criado_em: datetime
    atualizado_em: datetime
    atualizado_por: UUID | None = None
    atualizado_por_nome: str | None = None


class Referencia(Esquema):
    """Item de lista de apoio: só id e nome."""

    id: UUID
    nome: str
