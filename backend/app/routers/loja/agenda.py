"""Agenda (/api/loja/agenda): visão de semana/mês e painel do dia num só endpoint.

Devolve, para o período: os agendamentos visíveis, os profissionais (com a cor), a jornada dos
perfis deles e os bloqueios que os atingem. Quem só tem Minha agenda vê apenas a si mesmo (o
filtro de profissional é ignorado), mesmo sem leitura em Horários e bloqueios.
"""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, BloqueioAgenda, Funcionario, PerfilHorario
from app.schemas.agendamentos import AgendamentoSaida
from app.schemas.comum import Erro
from app.schemas.perfis import BloqueioSaida, HorarioSaida
from app.services import agendamentos as regras
from app.services.comum import buscar, com_autor, fuso, intervalo_de_dias, invalido
from app.services.disponibilidade import bloqueios_que_atingem, descrever_bloqueios

router = APIRouter(tags=['Loja: agenda'], responses={403: {'model': Erro}, 404: {'model': Erro}})

MAX_DIAS = 62  # a grade do mês tem 42 dias


class ProfissionalAgenda(BaseModel):
    id: UUID
    nome: str
    cor_agenda: str | None
    perfil_id: UUID
    ativo: bool


class AgendaPeriodo(BaseModel):
    inicio: date
    fim: date
    so_propria: bool
    profissionais: list[ProfissionalAgenda]
    agendamentos: list[AgendamentoSaida]
    jornadas: list[HorarioSaida]
    bloqueios: list[BloqueioSaida]


@router.get('/agenda', summary='Agendamentos, jornada e bloqueios de um período (semana, mês ou dia)')
def agenda(
    ctx: Annotated[ContextoLoja, Depends(exigir(('agenda_propria', 'agenda_equipe')))],
    inicio: Annotated[date, Query(description='Primeiro dia (no fuso da loja)')],
    fim: Annotated[date | None, Query(description='Último dia, inclusive (padrão: o próprio início)')] = None,
    funcionario_id: Annotated[UUID | None, Query(description='Só este profissional')] = None,
) -> AgendaPeriodo:
    db = ctx.db
    fim = fim or inicio
    if fim < inicio:
        raise invalido('O fim do período deve ser depois do início.')
    if fim - inicio > timedelta(days=MAX_DIAS):
        raise invalido(f'O período pode ter no máximo {MAX_DIAS} dias.')
    zona = fuso(ctx.loja.fuso_horario)
    de, ate = intervalo_de_dias(inicio, fim, zona)

    so_propria = not ctx.pode('agenda_equipe')
    if so_propria:
        funcionario_id = ctx.funcionario.id
    filtrado = (
        buscar(db, Funcionario, ctx.loja_id, funcionario_id, 'Profissional não encontrado.')
        if funcionario_id
        else None
    )

    consulta = select(Agendamento).where(
        Agendamento.loja_id == ctx.loja_id, Agendamento.inicio < ate, Agendamento.fim > de
    )
    if filtrado is not None:
        consulta = consulta.where(Agendamento.funcionario_id == filtrado.id)
    agendamentos = list(db.scalars(consulta.order_by(Agendamento.inicio, Agendamento.id)))

    if filtrado is not None:
        profissionais = [filtrado]
    else:
        com_agendamento = {a.funcionario_id for a in agendamentos}
        profissionais = list(
            db.scalars(
                select(Funcionario)
                .where(
                    Funcionario.loja_id == ctx.loja_id,
                    or_(Funcionario.ativo, Funcionario.id.in_(com_agendamento)),
                )
                .order_by(Funcionario.nome)
            )
        )
    perfis = {f.perfil_id for f in profissionais}
    jornadas = db.scalars(
        select(PerfilHorario)
        .where(PerfilHorario.loja_id == ctx.loja_id, PerfilHorario.perfil_id.in_(perfis))
        .order_by(PerfilHorario.perfil_id, PerfilHorario.dia_semana, PerfilHorario.hora_inicio)
    ).all()

    consulta_bloqueios = select(BloqueioAgenda).where(
        BloqueioAgenda.loja_id == ctx.loja_id, BloqueioAgenda.inicio < ate, BloqueioAgenda.fim > de
    )
    if filtrado is not None:
        consulta_bloqueios = consulta_bloqueios.where(bloqueios_que_atingem(filtrado))
    bloqueios = db.scalars(consulta_bloqueios.order_by(BloqueioAgenda.inicio, BloqueioAgenda.id)).all()

    return AgendaPeriodo(
        inicio=inicio,
        fim=fim,
        so_propria=so_propria,
        profissionais=[ProfissionalAgenda.model_validate(f, from_attributes=True) for f in profissionais],
        agendamentos=regras.descrever(ctx, agendamentos),
        jornadas=com_autor(db, ctx.loja_id, [HorarioSaida.model_validate(j) for j in jornadas]),
        bloqueios=descrever_bloqueios(db, ctx.loja_id, bloqueios, zona),
    )
