"""Locais (/api/loja/locais) e como a loja os chama no menu (/api/loja/locais/rotulos). Recurso: locais.

Local não é excluído: é inativado (some dos novos agendamentos, o histórico continua).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, Local, LojaConfiguracao, Servico, ServicoLocal
from app.models.enums import StatusAgendamento
from app.schemas.comum import Erro, Referencia
from app.schemas.locais import LocalEntrada, LocalSaida, RotulosEntrada, RotulosSaida
from app.services.comum import buscar, com_autor, fuso, hoje, inicio_do_dia

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(prefix='/locais', tags=['Loja: locais'], responses=ERROS)

MSG_404 = 'Local não encontrado.'
INATIVOS = (StatusAgendamento.cancelado, StatusAgendamento.nao_compareceu)

Leitura = Annotated[ContextoLoja, Depends(exigir('locais'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('locais', 'escrita'))]


def _saida(ctx: ContextoLoja, locais: list[Local]) -> list[LocalSaida]:
    db = ctx.db
    ids = [loc.id for loc in locais]
    servicos: dict[UUID, list[Referencia]] = {i: [] for i in ids}
    if ctx.acesso.modulo_ativo('servicos'):
        for local_id, servico_id, nome in db.execute(
            select(ServicoLocal.local_id, Servico.id, Servico.nome)
            .join(
                Servico, (Servico.id == ServicoLocal.servico_id) & (Servico.loja_id == ServicoLocal.loja_id)
            )
            .where(ServicoLocal.loja_id == ctx.loja_id, ServicoLocal.local_id.in_(ids))
            .order_by(Servico.nome)
        ):
            servicos[local_id].append(Referencia(id=servico_id, nome=nome))
    zona = fuso(ctx.loja.fuso_horario)
    desde = inicio_do_dia(hoje(zona), zona)
    proximos = dict(
        db.execute(
            select(Agendamento.local_id, func.count())
            .where(
                Agendamento.loja_id == ctx.loja_id,
                Agendamento.local_id.in_(ids),
                Agendamento.inicio >= desde,
                Agendamento.status.not_in(INATIVOS),
            )
            .group_by(Agendamento.local_id)
        ).all()
    )
    saida = []
    for loc in locais:
        item = LocalSaida.model_validate(loc)
        item.servicos = servicos[loc.id]
        item.proximos_agendamentos = proximos.get(loc.id, 0)
        saida.append(item)
    return com_autor(db, ctx.loja_id, saida)


# --- Rótulos (antes de /{local_id}) -------------------------------------------------------------


def _configuracao(ctx: ContextoLoja) -> LojaConfiguracao:
    configuracao = ctx.db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == ctx.loja_id))
    if configuracao is None:  # toda loja nasce com uma; recria se faltar
        configuracao = LojaConfiguracao(loja_id=ctx.loja_id)
        ctx.db.add(configuracao)
        ctx.db.flush()
    return configuracao


@router.get('/rotulos', summary='Como a loja chama os locais (Sala, Cadeira...)')
def obter_rotulos(ctx: Leitura) -> RotulosSaida:
    return com_autor(ctx.db, ctx.loja_id, [RotulosSaida.model_validate(_configuracao(ctx))])[0]


@router.put('/rotulos', summary='Definir como a loja chama os locais (muda o menu e os textos do painel)')
def definir_rotulos(dados: RotulosEntrada, ctx: Escrita) -> RotulosSaida:
    configuracao = _configuracao(ctx)
    configuracao.rotulo_local = dados.rotulo_local
    configuracao.rotulo_local_plural = dados.rotulo_local_plural
    ctx.db.flush()
    return com_autor(ctx.db, ctx.loja_id, [RotulosSaida.model_validate(configuracao)])[0]


# --- Locais ------------------------------------------------------------------------------------


@router.get('', summary='Locais da loja')
def listar(ctx: Leitura, ativo: bool | None = None) -> list[LocalSaida]:
    consulta = select(Local).where(Local.loja_id == ctx.loja_id)
    if ativo is not None:
        consulta = consulta.where(Local.ativo == ativo)
    return _saida(ctx, list(ctx.db.scalars(consulta.order_by(func.lower(Local.nome), Local.id))))


@router.get('/{local_id}', summary='Um local')
def obter(local_id: UUID, ctx: Leitura) -> LocalSaida:
    return _saida(ctx, [buscar(ctx.db, Local, ctx.loja_id, local_id, MSG_404)])[0]


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar local')
def criar(dados: LocalEntrada, ctx: Escrita) -> LocalSaida:
    local = Local(loja_id=ctx.loja_id, **dados.model_dump())
    ctx.db.add(local)
    ctx.db.flush()
    return _saida(ctx, [local])[0]


@router.put('/{local_id}', summary='Editar local (inclui inativar)')
def editar(local_id: UUID, dados: LocalEntrada, ctx: Escrita) -> LocalSaida:
    local = buscar(ctx.db, Local, ctx.loja_id, local_id, MSG_404)
    for campo, valor in dados.model_dump().items():
        setattr(local, campo, valor)
    ctx.db.flush()
    return _saida(ctx, [local])[0]
