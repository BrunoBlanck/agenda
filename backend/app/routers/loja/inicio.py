"""Início (/api/loja/inicio): resumo do dia. Cada bloco só vem se o usuário puder vê-lo (nulo = oculto).

- agenda de hoje e solicitações do site: leitura em Minha agenda ou Agenda da equipe (só os visíveis);
- clientes cadastrados: leitura em Clientes;
- funcionários em serviço (quantidade e quem, desde quando): leitura em Ponto da equipe;
- materiais a repor: leitura em Materiais.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLojaDep
from app.models import Agendamento, Cliente, Funcionario, Material, RegistroPonto
from app.models.enums import StatusAgendamento
from app.schemas.agendamentos import AgendamentoSaida
from app.schemas.comum import DecimalSaida
from app.services import agendamentos as regras
from app.services.comum import fuso, hoje, intervalo_de_dias

router = APIRouter(tags=['Loja: início'])


class MaterialRepor(BaseModel):
    id: UUID
    nome: str
    unidade: str
    quantidade_atual: DecimalSaida
    estoque_minimo: DecimalSaida


class EmServico(BaseModel):
    registro_id: UUID
    funcionario_id: UUID
    nome: str
    cor_agenda: str | None
    entrada: datetime = Field(description='No fuso da loja')


class Resumo(BaseModel):
    data: date = Field(description='Hoje, no fuso da loja')
    agenda_hoje: list[AgendamentoSaida] | None
    so_propria: bool = Field(description='A agenda mostra só os agendamentos do próprio usuário')
    solicitacoes_site: list[AgendamentoSaida] | None = Field(description='Pedidos do site aguardando aceite')
    clientes_cadastrados: int | None
    funcionarios_em_servico: int | None
    equipe_em_servico: list[EmServico] | None = Field(
        default=None, description='Quem registrou entrada e ainda não saiu, pela ordem de entrada'
    )
    materiais_a_repor: list[MaterialRepor] | None


@router.get('/inicio', summary='Resumo do dia (cada bloco conforme o acesso do usuário)')
def inicio(ctx: ContextoLojaDep) -> Resumo:
    db = ctx.db
    zona = fuso(ctx.loja.fuso_horario)
    dia = hoje(zona)
    de, ate = intervalo_de_dias(dia, dia, zona)

    agenda_hoje = solicitacoes = None
    if ctx.pode('agenda_propria') or ctx.pode('agenda_equipe'):
        visiveis = regras.filtro_visiveis(ctx)
        base = [Agendamento.loja_id == ctx.loja_id, *([visiveis] if visiveis is not None else [])]
        do_dia = db.scalars(
            select(Agendamento)
            .where(*base, Agendamento.inicio >= de, Agendamento.inicio < ate)
            .order_by(Agendamento.inicio, Agendamento.id)
        ).all()
        pendentes = db.scalars(
            select(Agendamento)
            .where(*base, Agendamento.status == StatusAgendamento.pendente)
            .order_by(Agendamento.inicio, Agendamento.id)
        ).all()
        agenda_hoje = regras.descrever(ctx, list(do_dia))
        solicitacoes = regras.descrever(ctx, list(pendentes))

    clientes = None
    if ctx.pode('clientes'):
        clientes = db.scalar(select(func.count()).select_from(Cliente).where(Cliente.loja_id == ctx.loja_id))

    em_servico = equipe = None
    if ctx.pode('ponto_equipe'):
        abertos = db.execute(
            select(RegistroPonto, Funcionario.nome, Funcionario.cor_agenda)
            .join(
                Funcionario,
                (Funcionario.id == RegistroPonto.funcionario_id)
                & (Funcionario.loja_id == RegistroPonto.loja_id),
            )
            .where(
                RegistroPonto.loja_id == ctx.loja_id,
                RegistroPonto.saida.is_(None),
                RegistroPonto.entrada < ate,
            )
            .order_by(RegistroPonto.entrada, RegistroPonto.id)
        ).all()
        equipe = [
            EmServico(
                registro_id=registro.id,
                funcionario_id=registro.funcionario_id,
                nome=nome,
                cor_agenda=cor,
                entrada=registro.entrada.astimezone(zona),
            )
            for registro, nome, cor in abertos
        ]
        em_servico = len(equipe)

    repor = None
    if ctx.pode('materiais'):
        repor = [
            MaterialRepor.model_validate(m, from_attributes=True)
            for m in db.scalars(
                select(Material)
                .where(
                    Material.loja_id == ctx.loja_id,
                    Material.ativo,
                    Material.quantidade_atual < func.coalesce(Material.estoque_minimo, Decimal(0)),
                )
                .order_by(Material.quantidade_atual - Material.estoque_minimo, Material.nome)
            )
        ]

    return Resumo(
        data=dia,
        agenda_hoje=agenda_hoje,
        so_propria=not ctx.pode('agenda_equipe'),
        solicitacoes_site=solicitacoes,
        clientes_cadastrados=clientes,
        funcionarios_em_servico=em_servico,
        equipe_em_servico=equipe,
        materiais_a_repor=repor,
    )
