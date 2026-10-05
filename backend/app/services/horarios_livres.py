"""Horários livres para o site do consumidor (estrutura.md, 2.13): API pública e páginas HTML do site.

Mesmas regras do agendamento pelo painel (app.services.agendamentos e app.services.disponibilidade):
- dentro da jornada do perfil do profissional, inteiro numa faixa do dia (fuso da loja);
- fora dos bloqueios da loja, do perfil e do próprio profissional;
- sem conflito com outro agendamento que ocupa o horário (pedidos pendentes do site também ocupam);
- com o módulo Locais: só se houver um local permitido para o serviço e livre; o pedido já sai com ele.
Além disso, o site só oferece horários a partir de ``ANTECEDENCIA_MINUTOS`` e em passos de ``PASSO_MINUTOS``.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Agendamento,
    BloqueioAgenda,
    Funcionario,
    Local,
    PerfilHorario,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
)
from app.services.agendamentos import LIBERAM_HORARIO
from app.services.comum import inicio_do_dia

PASSO_MINUTOS = 30  # entre um horário oferecido e outro
ANTECEDENCIA_MINUTOS = 60  # a partir de agora
DURACAO_SEM_SERVICO = 30  # atendimento genérico (loja sem o módulo Serviços)
DIAS_MAXIMOS = 31  # dias por consulta


@dataclass(frozen=True)
class Livre:
    inicio: datetime
    fim: datetime
    funcionario: Funcionario
    local_id: UUID | None


def profissionais_por_servico(
    db: Session, loja_id: UUID, servico_ids: list[UUID]
) -> dict[UUID, list[Funcionario]]:
    """Profissionais ativos habilitados em cada serviço, numa consulta só (em ordem alfabética)."""
    equipes: dict[UUID, list[Funcionario]] = defaultdict(list)
    if not servico_ids:
        return equipes
    linhas = db.execute(
        select(ServicoFuncionario.servico_id, Funcionario)
        .join(
            ServicoFuncionario,
            (ServicoFuncionario.funcionario_id == Funcionario.id)
            & (ServicoFuncionario.loja_id == Funcionario.loja_id),
        )
        .where(
            Funcionario.loja_id == loja_id,
            Funcionario.ativo,
            ServicoFuncionario.servico_id.in_(servico_ids),
            ServicoFuncionario.excluido_em.is_(None),
        )
        .order_by(Funcionario.nome, Funcionario.id)
    ).all()
    for servico_id, funcionario in linhas:
        equipes[servico_id].append(funcionario)
    return equipes


def profissionais(db: Session, loja_id: UUID, servico: Servico | None) -> list[Funcionario]:
    """Quem pode ser agendado: ativos habilitados no serviço; sem o módulo Serviços, ativos com jornada."""
    if servico is not None:
        return profissionais_por_servico(db, loja_id, [servico.id]).get(servico.id, [])
    consulta = select(Funcionario).where(
        Funcionario.loja_id == loja_id,
        Funcionario.ativo,
        exists().where(
            PerfilHorario.loja_id == Funcionario.loja_id,
            PerfilHorario.perfil_id == Funcionario.perfil_id,
            PerfilHorario.excluido_em.is_(None),
        ),
    )
    return list(db.scalars(consulta.order_by(Funcionario.nome, Funcionario.id)))


def locais_permitidos(db: Session, loja_id: UUID, servico: Servico | None) -> list[Local]:
    """Locais ativos onde o serviço pode acontecer (serviço sem vínculo = qualquer local ativo)."""
    consulta = select(Local).where(Local.loja_id == loja_id, Local.ativo)
    if servico is not None:
        vinculados = list(
            db.scalars(
                select(ServicoLocal.local_id).where(
                    ServicoLocal.loja_id == loja_id, ServicoLocal.servico_id == servico.id
                )
            )
        )
        if vinculados:
            consulta = consulta.where(Local.id.in_(vinculados))
    return list(db.scalars(consulta.order_by(Local.nome, Local.id)))


class Agenda:
    """Jornada, bloqueios e ocupação carregados uma vez para o período consultado."""

    def __init__(
        self,
        db: Session,
        loja_id: UUID,
        zona: ZoneInfo,
        funcionarios: list[Funcionario],
        local_ids: list[UUID] | None,
        primeiro: date,
        ultimo: date,
    ) -> None:
        self.zona = zona
        self.funcionarios = funcionarios
        self.local_ids = local_ids
        de, ate = inicio_do_dia(primeiro, zona), inicio_do_dia(ultimo + timedelta(days=1), zona)
        ids = [f.id for f in funcionarios]

        self.jornada: dict[tuple[UUID, int], list[tuple[time, time]]] = defaultdict(list)
        for faixa in db.scalars(
            select(PerfilHorario)
            .where(
                PerfilHorario.loja_id == loja_id,
                PerfilHorario.perfil_id.in_({f.perfil_id for f in funcionarios}),
            )
            .order_by(PerfilHorario.hora_inicio)
        ):
            self.jornada[(faixa.perfil_id, faixa.dia_semana)].append((faixa.hora_inicio, faixa.hora_fim))

        self.bloqueios = list(
            db.scalars(
                select(BloqueioAgenda).where(
                    BloqueioAgenda.loja_id == loja_id, BloqueioAgenda.inicio < ate, BloqueioAgenda.fim > de
                )
            )
        )
        ocupacao = [Agendamento.funcionario_id.in_(ids)]
        if local_ids:
            ocupacao.append(Agendamento.local_id.in_(local_ids))
        linhas = db.execute(
            select(
                Agendamento.funcionario_id, Agendamento.local_id, Agendamento.inicio, Agendamento.fim
            ).where(
                Agendamento.loja_id == loja_id,
                Agendamento.inicio < ate,
                Agendamento.fim > de,
                Agendamento.status.not_in(LIBERAM_HORARIO),
                or_(*ocupacao),
            )
        ).all()
        self.por_funcionario: dict[UUID, list[tuple[datetime, datetime]]] = defaultdict(list)
        self.por_local: dict[UUID, list[tuple[datetime, datetime]]] = defaultdict(list)
        for funcionario_id, local_id, inicio, fim in linhas:
            self.por_funcionario[funcionario_id].append((inicio, fim))
            if local_id is not None:
                self.por_local[local_id].append((inicio, fim))

    @staticmethod
    def _sobrepoe(intervalos: list[tuple[datetime, datetime]], inicio: datetime, fim: datetime) -> bool:
        return any(i < fim and f > inicio for i, f in intervalos)

    def _bloqueado(self, funcionario: Funcionario, inicio: datetime, fim: datetime) -> bool:
        return any(
            (
                (b.perfil_id is None and b.funcionario_id is None)
                or b.perfil_id == funcionario.perfil_id
                or b.funcionario_id == funcionario.id
            )
            and b.inicio < fim
            and b.fim > inicio
            for b in self.bloqueios
        )

    def locais_livres(self, inicio: datetime, fim: datetime) -> list[UUID]:
        return [i for i in self.local_ids or [] if not self._sobrepoe(self.por_local[i], inicio, fim)]

    def livres_no_dia(self, dia: date, duracao: int, agora: datetime) -> list[Livre]:
        """Horários livres do dia, em ordem; cada horário fica com o primeiro profissional livre."""
        limite = agora + timedelta(minutes=ANTECEDENCIA_MINUTOS)
        dia_semana = (dia.weekday() + 1) % 7  # 0 = domingo
        passo, tamanho = timedelta(minutes=PASSO_MINUTOS), timedelta(minutes=duracao)
        livres: dict[str, Livre] = {}
        for funcionario in self.funcionarios:
            for hora_inicio, hora_fim in self.jornada.get((funcionario.perfil_id, dia_semana), []):
                inicio = datetime.combine(dia, hora_inicio, tzinfo=self.zona)
                termino = datetime.combine(dia, hora_fim, tzinfo=self.zona)
                while inicio + tamanho <= termino:
                    fim = inicio + tamanho
                    hora = inicio.strftime('%H:%M')
                    if (
                        hora not in livres
                        and inicio >= limite
                        and not self._sobrepoe(self.por_funcionario[funcionario.id], inicio, fim)
                        and not self._bloqueado(funcionario, inicio, fim)
                    ):
                        local_id = None
                        if self.local_ids is not None:
                            disponiveis = self.locais_livres(inicio, fim)
                            local_id = disponiveis[0] if disponiveis else None
                        if self.local_ids is None or local_id is not None:
                            livres[hora] = Livre(inicio, fim, funcionario, local_id)
                    inicio += passo
        return [livres[h] for h in sorted(livres)]
