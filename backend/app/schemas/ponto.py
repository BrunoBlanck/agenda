"""Controle de tempo (estrutura.md, 2.16)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrigemPonto
from app.schemas.comum import Controle, DataHora, Entrada, texto

AcaoPonto = Literal['entrada', 'saida']


class RegistrarEntrada(Entrada):
    acao: AcaoPonto = Field(
        description='O que o usuário pediu: entrada ou saída. Se não bater com a situação atual = 409'
    )
    funcionario_id: UUID | None = Field(
        default=None,
        description='Vazio = o próprio usuário. Outro funcionário exige escrita em Ponto da equipe',
    )


class CorrecaoEntrada(Entrada):
    entrada: DataHora = Field(description='Sem fuso, vale o horário da loja')
    saida: DataHora | None = None
    justificativa: texto() = Field(description='Motivo da correção (obrigatório)')


class PontoManualEntrada(CorrecaoEntrada):
    funcionario_id: UUID


class RegistroSaida(Controle):
    id: UUID
    funcionario_id: UUID
    funcionario_nome: str | None = None
    data: date | None = Field(default=None, description='Dia da entrada, no fuso da loja')
    entrada: datetime
    saida: datetime | None
    minutos: int | None = Field(default=None, description='Tempo trabalhado (nulo = em serviço)')
    origem: OrigemPonto
    justificativa: str | None
    editado_por: UUID | None
    editado_por_nome: str | None = None


class RegistroFeito(BaseModel):
    acao: AcaoPonto
    registro: RegistroSaida


class TotalDia(BaseModel):
    funcionario_id: UUID
    funcionario_nome: str | None
    data: date
    minutos: int


class PontoPeriodo(BaseModel):
    inicio: date
    fim: date
    registros: list[RegistroSaida]
    totais: list[TotalDia] = Field(
        description='Horas trabalhadas por funcionário e dia (só registros fechados)'
    )


class FuncionarioPonto(BaseModel):
    """Funcionário para escolher no ponto da equipe (registrar, lançar e filtrar)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    cor_agenda: str | None
    ativo: bool
