"""Schemas compartilhados: paginação e erros."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict


class Esquema(BaseModel):
    """Base dos schemas de saída: aceita objetos do ORM."""

    model_config = ConfigDict(from_attributes=True)


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
