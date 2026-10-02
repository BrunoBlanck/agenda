"""Planos comerciais (/api/superadmin/planos): só nome e preço (estrutura.md, 1.3)."""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import exists, func, select

from app.auth.dependencias import ContextoSuperadminDep
from app.models import Loja, Plano
from app.schemas.comum import Erro
from app.schemas.superadmin import PlanoEntrada, PlanoSaida
from app.services.comum import conflito, excluir, nao_encontrado
from app.services.plataforma import MSG_PLANO_404, lojas_ativas_por_plano

router = APIRouter(
    prefix='/planos', tags=['Superadmin: planos'], responses={404: {'model': Erro}, 409: {'model': Erro}}
)


def _saida(db, planos: list[Plano]) -> list[PlanoSaida]:
    ativas = lojas_ativas_por_plano(db)
    saida = []
    for plano in planos:
        item = PlanoSaida.model_validate(plano)
        item.lojas_ativas = ativas.get(plano.id, 0)
        saida.append(item)
    return saida


def _buscar(db, plano_id: UUID) -> Plano:
    plano = db.scalar(select(Plano).where(Plano.id == plano_id))
    if plano is None:
        raise nao_encontrado(MSG_PLANO_404)
    return plano


@router.get('', summary='Planos (com o número de lojas ativas em cada um)')
def listar(ctx: ContextoSuperadminDep) -> list[PlanoSaida]:
    planos = ctx.db.scalars(select(Plano).order_by(Plano.preco_mensal, func.lower(Plano.nome)))
    return _saida(ctx.db, list(planos))


@router.get('/{plano_id}', summary='Dados do plano')
def obter(plano_id: UUID, ctx: ContextoSuperadminDep) -> PlanoSaida:
    return _saida(ctx.db, [_buscar(ctx.db, plano_id)])[0]


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar plano')
def criar(dados: PlanoEntrada, ctx: ContextoSuperadminDep) -> PlanoSaida:
    plano = Plano(**dados.model_dump())
    ctx.db.add(plano)
    ctx.db.flush()
    return _saida(ctx.db, [plano])[0]


@router.put('/{plano_id}', summary='Editar plano (inativo não aparece para lojas novas)')
def editar(plano_id: UUID, dados: PlanoEntrada, ctx: ContextoSuperadminDep) -> PlanoSaida:
    plano = _buscar(ctx.db, plano_id)
    for campo, valor in dados.model_dump().items():
        if getattr(plano, campo) != valor:
            setattr(plano, campo, valor)
    ctx.db.flush()
    return _saida(ctx.db, [plano])[0]


@router.delete(
    '/{plano_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir plano (só sem lojas; com lojas, inative)',
)
def remover(plano_id: UUID, ctx: ContextoSuperadminDep) -> None:
    plano = _buscar(ctx.db, plano_id)
    em_uso = ctx.db.scalar(select(exists().where(Loja.plano_id == plano.id, Loja.excluido_em.is_(None))))
    if em_uso:
        raise conflito('Há lojas neste plano. Mude o plano delas antes de excluir, ou inative o plano.')
    excluir(ctx.db, plano)
