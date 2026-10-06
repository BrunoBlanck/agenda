"""Clientes (/api/loja/clientes). Recurso: clientes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import exists, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, Cliente
from app.models.enums import CanalCliente
from app.schemas.clientes import (
    ClienteDoCodigo,
    ClienteEntrada,
    ClienteSaida,
    CodigoPendente,
    CodigoSiteSaida,
    ContaSiteSaida,
)
from app.schemas.comum import Erro, Pagina, Paginacao, formatar_telefone, paginacao, so_digitos
from app.services.clientes import filtro_busca
from app.services.comum import (
    buscar,
    com_autor,
    conferir_nascimento,
    conflito,
    excluir,
    fuso,
    nao_encontrado,
    paginar,
)
from app.services.conta_cliente import codigo_pendente, codigos_pendentes, conta_do_telefone, remover_acesso

ERROS = {403: {'model': Erro}, 404: {'model': Erro}}
router = APIRouter(prefix='/clientes', tags=['Loja: clientes'], responses=ERROS)

MSG_404 = 'Cliente não encontrado.'
MSG_SEM_CONTA = 'Este cliente não tem acesso ao site.'


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


# Antes de /{cliente_id}: senão "codigos-site" seria lido como id (422)
@router.get('/codigos-site', summary='Códigos de confirmação do site aguardando uso (CLI-06)')
def codigos_site(
    ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))],
) -> list[CodigoSiteSaida]:
    """Códigos pendentes da loja, mais novo primeiro (até 100). A loja repassa o código ao cliente
    enquanto o envio por SMS/WhatsApp não existe (SIT-17, provedor "painel")."""
    return [
        CodigoSiteSaida(
            telefone=formatar_telefone(codigo.telefone_digitos),
            codigo=codigo.codigo,
            expira_em=codigo.expira_em,
            criado_em=codigo.criado_em,
            clientes=[ClienteDoCodigo(id=c.id, nome=f'{c.nome} {c.sobrenome}') for c in clientes],
        )
        for codigo, clientes in codigos_pendentes(ctx.db, ctx.loja_id)
    ]


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


# --- Acesso ao site (CLI-06, SIT-16 a SIT-20): sempre pelo telefone atual do cliente ------------------


@router.get('/{cliente_id}/conta-site', summary='Conta do cliente no site e código pendente')
def conta_site(
    cliente_id: UUID, ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))]
) -> ContaSiteSaida:
    cliente = buscar(ctx.db, Cliente, ctx.loja_id, cliente_id, MSG_404)
    digitos = so_digitos(cliente.telefone)
    conta = conta_do_telefone(ctx.db, ctx.loja_id, digitos)
    codigo = codigo_pendente(ctx.db, ctx.loja_id, digitos)
    return ContaSiteSaida(
        possui_conta=conta is not None,
        criada_em=conta.criado_em if conta else None,
        ultimo_acesso_em=conta.ultimo_acesso_em if conta else None,
        codigo_pendente=CodigoPendente(codigo=codigo.codigo, expira_em=codigo.expira_em) if codigo else None,
    )


@router.delete(
    '/{cliente_id}/conta-site',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Remover o acesso do cliente ao site (sai de todos os aparelhos)',
)
def remover_conta_site(
    cliente_id: UUID, ctx: Annotated[ContextoLoja, Depends(exigir('clientes', 'escrita'))]
) -> None:
    cliente = buscar(ctx.db, Cliente, ctx.loja_id, cliente_id, MSG_404)
    if not remover_acesso(ctx.db, ctx.loja_id, so_digitos(cliente.telefone)):
        raise nao_encontrado(MSG_SEM_CONTA)
