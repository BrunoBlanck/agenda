"""Jornada e bloqueios: quando um profissional pode ser agendado (estrutura.md, 2.5, 2.6 e 2.13).

Espelha frontend/src/data/horarios.js:
- a jornada do funcionário é a do perfil dele;
- um bloqueio atinge o funcionário se for da loja inteira, do perfil dele ou dele próprio.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.orm import Session

from app.models import BloqueioAgenda, Funcionario, Perfil, PerfilHorario
from app.schemas.perfis import BloqueioSaida
from app.services.comum import com_autor, dia_semana

MSG_FORA_DA_JORNADA = 'Horário fora da jornada de trabalho do profissional.'


def bloqueios_que_atingem(funcionario: Funcionario) -> ColumnElement[bool]:
    return or_(
        and_(BloqueioAgenda.perfil_id.is_(None), BloqueioAgenda.funcionario_id.is_(None)),
        BloqueioAgenda.perfil_id == funcionario.perfil_id,
        BloqueioAgenda.funcionario_id == funcionario.id,
    )


def bloqueio_no_periodo(
    db: Session, loja_id: UUID, funcionario: Funcionario, inicio: datetime, fim: datetime
) -> BloqueioAgenda | None:
    return db.scalar(
        select(BloqueioAgenda)
        .where(
            BloqueioAgenda.loja_id == loja_id,
            bloqueios_que_atingem(funcionario),
            BloqueioAgenda.inicio < fim,
            BloqueioAgenda.fim > inicio,
        )
        .order_by(BloqueioAgenda.inicio)
        .limit(1)
    )


def dentro_da_jornada(
    db: Session, loja_id: UUID, funcionario: Funcionario, inicio: datetime, fim: datetime, zona: ZoneInfo
) -> bool:
    """O intervalo cabe inteiro numa faixa da jornada do perfil, no dia (no fuso da loja)?"""
    ini_local, fim_local = inicio.astimezone(zona), fim.astimezone(zona)
    if fim_local.date() != ini_local.date():
        return False
    faixa = db.scalar(
        select(PerfilHorario.id)
        .where(
            PerfilHorario.loja_id == loja_id,
            PerfilHorario.perfil_id == funcionario.perfil_id,
            PerfilHorario.dia_semana == dia_semana(ini_local),
            PerfilHorario.hora_inicio <= ini_local.time(),
            PerfilHorario.hora_fim >= fim_local.time(),
        )
        .limit(1)
    )
    return faixa is not None


def mensagem_indisponivel(
    db: Session, loja_id: UUID, funcionario: Funcionario, inicio: datetime, fim: datetime, zona: ZoneInfo
) -> str | None:
    """Mensagem para o usuário se o horário estiver bloqueado ou fora da jornada (None = disponível)."""
    bloqueio = bloqueio_no_periodo(db, loja_id, funcionario, inicio, fim)
    if bloqueio is not None:
        return f'Horário bloqueado: {bloqueio.motivo or "sem motivo informado"}.'
    if not dentro_da_jornada(db, loja_id, funcionario, inicio, fim, zona):
        return MSG_FORA_DA_JORNADA
    return None


def descrever_bloqueios(
    db: Session, loja_id: UUID, bloqueios: Sequence[BloqueioAgenda], zona: ZoneInfo
) -> list[BloqueioSaida]:
    """Bloqueios com o alvo em texto (como alvoBloqueio do front) e as datas no fuso da loja."""
    ids_func = {b.funcionario_id for b in bloqueios if b.funcionario_id}
    ids_perfil = {b.perfil_id for b in bloqueios if b.perfil_id}
    funcionarios = dict(
        db.execute(
            select(Funcionario.id, Funcionario.nome)
            .where(Funcionario.loja_id == loja_id, Funcionario.id.in_(ids_func))
            .execution_options(incluir_excluidos=True)
        ).all()
    )
    perfis = dict(
        db.execute(
            select(Perfil.id, Perfil.nome)
            .where(Perfil.loja_id == loja_id, Perfil.id.in_(ids_perfil))
            .execution_options(incluir_excluidos=True)
        ).all()
    )
    saida = []
    for b in bloqueios:
        item = BloqueioSaida.model_validate(b)
        item.inicio, item.fim = b.inicio.astimezone(zona), b.fim.astimezone(zona)
        if b.funcionario_id:
            item.alvo, item.quem = 'funcionario', funcionarios.get(b.funcionario_id, '—')
        elif b.perfil_id:
            item.alvo, item.quem = 'perfil', f'Perfil {perfis.get(b.perfil_id, "—")}'
        saida.append(item)
    return com_autor(db, loja_id, saida)
