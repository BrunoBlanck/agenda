"""Clientes (/api/loja/clientes). Recurso: clientes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import exists, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, Cliente
from app.models.enums import CanalCliente
from app.schemas.clientes import ClienteEntrada, ClienteSaida
from app.schemas.comum import Erro, Pagina, Paginacao, paginacao
from app.services.clientes import filtro_busca
from app.services.comum import buscar, com_autor, conferir_nascimento, conflito, excluir, fuso, paginar

ERROS = {403: {'model': Erro}, 404: {'model': Erro}}
router = APIRouter(prefix='/clientes', tags=['Loja: clientes'], responses=ERROS)

MSG_404 = 'Cliente não encontrado.'


def _saida(ctx: ContextoLoja, clientes: list[Cliente]) -> list[ClienteSaida]:
    return com_autor(ctx.db, ctx.loja_id, [ClienteSaida.model_validate(c) for c in clientes])


@router.get('', summary='Lista de clientes (paginada)')
def listar(
    ctx: Annotated[ContextoLoja, Depends(exigir('clientes'))],
    pag: Annotated[Paginacao, Depends(paginacao)],
    busca: Annotated[
        str | None,
        Query(max_length=100, description='Nome, CPF, telefone ou e-mail (com ou sem máscara)'),
    ] = None,
    ativo: bool | None = None,
    canal: CanalCliente | None = None,
) -> Pagina[ClienteSaida]:
    consulta = select(Cliente).where(Cliente.loja_id == ctx.loja_id)
    if busca and busca.strip():
        consulta = consulta.where(filtro_busca(busca.strip()))
    if ativo is not None:
        consulta = consulta.where(Cliente.ativo == ativo)
    if canal is not None:
        consulta = consulta.where(Cliente.canais.contains([canal]))
    consulta = consulta.order_by(Cliente.nome, Cliente.sobrenome, Cliente.id)
    itens, total = paginar(ctx.db, consulta, pag)
    return Pagina(itens=_saida(ctx, itens), total=total, pagina=pag.pagina, por_pagina=pag.por_pagina)


@router.get('/{cliente_id}', summary='Ficha do cliente')
def obter(cliente_id: UUID, ctx: Annotated[ContextoLoja, Depends(exigir('clientes'))]) -> ClienteSaida:
    return _saida(ctx, [buscar(ctx.db, Cliente, ctx.loja_id, cliente_id, MSG_404)])[0]


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar cliente')
def criar(
    dados: ClienteEntrada, ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))]
) -> ClienteSaida:
    conferir_nascimento(dados.data_nascimento, fuso(ctx.loja.fuso_horario))
    cliente = Cliente(loja_id=ctx.loja_id, **dados.model_dump())
    ctx.db.add(cliente)
    ctx.db.flush()
    return _saida(ctx, [cliente])[0]


@router.put('/{cliente_id}', summary='Editar cliente')
def editar(
    cliente_id: UUID,
    dados: ClienteEntrada,
    ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))],
) -> ClienteSaida:
    cliente = buscar(ctx.db, Cliente, ctx.loja_id, cliente_id, MSG_404)
    conferir_nascimento(dados.data_nascimento, fuso(ctx.loja.fuso_horario))
    for campo, valor in dados.model_dump().items():
        setattr(cliente, campo, valor)
    ctx.db.flush()
    return _saida(ctx, [cliente])[0]


@router.delete(
    '/{cliente_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {'model': Erro}},
    summary='Excluir cliente (só sem agendamentos; com agendamentos, inative)',
)
def remover(cliente_id: UUID, ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))]) -> None:
    cliente = buscar(ctx.db, Cliente, ctx.loja_id, cliente_id, MSG_404)
    tem_agendamentos = ctx.db.scalar(
        select(
            exists().where(
                Agendamento.loja_id == ctx.loja_id,
                Agendamento.cliente_id == cliente.id,
                Agendamento.excluido_em.is_(None),
            )
        )
    )
    if tem_agendamentos:
        raise conflito('Este cliente tem agendamentos e não pode ser excluído. Inative o cadastro.')
    excluir(ctx.db, cliente)
