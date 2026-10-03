"""Perfis, níveis de acesso, jornada e bloqueios (estrutura.md, 1.8, 2.1, 2.2, 2.5 e 2.6)."""

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import NivelAcesso
from app.schemas.comum import LISTA_MAX, Controle, DataHora, Entrada, Esquema, regra, texto, texto_opcional


class RecursoSaida(BaseModel):
    codigo: str
    nome: str
    descricao: str | None = Field(description='"Leitura: ... Escrita: ..." (mantido por compatibilidade)')
    leitura: str = Field(description='O que o nível leitura permite')
    escrita: str = Field(description='O que o nível escrita permite')
    modulo: str
    modulo_ativo: bool
    ordem: int | None


class FuncionarioDoPerfil(Esquema):
    id: UUID
    nome: str
    ativo: bool


class PerfilSaida(Controle):
    id: UUID
    nome: str
    descricao: str | None
    padrao: bool
    acesso_total: bool
    acessos: dict[str, NivelAcesso] | None = Field(
        default=None,
        description='Nível do perfil em cada recurso (sem o efeito dos módulos). '
        'Só vem para quem tem leitura em Perfis de acesso.',
    )
    funcionarios: list[FuncionarioDoPerfil] = Field(default_factory=list)
    sem_jornada: bool = False


class PerfilNovo(Entrada):
    nome: texto(60)
    descricao: texto_opcional() = None
    copiar_de: UUID | None = Field(default=None, description='Copia os níveis e a jornada deste perfil')


class PerfilEdicao(Entrada):
    nome: texto(60)
    descricao: texto_opcional() = None


class AcessosEntrada(Entrada):
    acessos: dict[str, NivelAcesso] = Field(
        max_length=LISTA_MAX, description='Código do recurso -> nível. Os não citados não mudam.'
    )


# --- Jornada (perfil_horarios) -------------------------------------------------------------------


class HorarioEntrada(Entrada):
    dia_semana: int = Field(ge=0, le=6, description='0 = domingo ... 6 = sábado')
    hora_inicio: time
    hora_fim: time

    @model_validator(mode='after')
    def _faixa(self) -> 'HorarioEntrada':
        if self.hora_fim <= self.hora_inicio:
            raise regra('O fim deve ser depois do início.')
        return self


class HorarioSaida(Controle):
    id: UUID
    perfil_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fim: time


# --- Bloqueios -----------------------------------------------------------------------------------


class BloqueioEntrada(Entrada):
    perfil_id: UUID | None = Field(default=None, description='Bloqueio de todo o perfil')
    funcionario_id: UUID | None = Field(default=None, description='Bloqueio só deste funcionário')
    inicio: DataHora = Field(description='Sem fuso, vale o horário da loja')
    fim: DataHora
    motivo: texto_opcional(150) = None

    @model_validator(mode='after')
    def _regras(self) -> 'BloqueioEntrada':
        if self.perfil_id and self.funcionario_id:
            raise regra('Escolha um perfil ou um funcionário, não os dois.')
        return self


class BloqueioSaida(Controle):
    id: UUID
    perfil_id: UUID | None
    funcionario_id: UUID | None
    inicio: datetime
    fim: datetime
    motivo: str | None
    alvo: Literal['loja', 'perfil', 'funcionario'] = 'loja'
    quem: str | None = Field(
        default=None, description='Para quem é o bloqueio, em texto. Nulo = loja inteira'
    )
