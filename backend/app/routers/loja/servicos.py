"""Serviços (/api/loja/servicos). Recurso: servicos (módulo Serviços).

Vínculos (tabelas de ligação): profissionais habilitados, locais permitidos e materiais por
atendimento. Religar um vínculo removido restaura a linha existente (não cria outra).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import (
    Funcionario,
    Local,
    Material,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
    ServicoMaterial,
)
from app.schemas.comum import Erro
from app.schemas.servicos import ServicoEntrada, ServicoSaida
from app.services.comum import buscar, excluir, invalido, sincronizar_vinculos
from app.services.servicos import descrever_servicos

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(prefix='/servicos', tags=['Loja: serviços'], responses=ERROS)

MSG_404 = 'Serviço não encontrado.'

Leitura = Annotated[ContextoLoja, Depends(exigir('servicos'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('servicos', 'escrita'))]


def _saida(ctx: ContextoLoja, servicos: list[Servico]) -> list[ServicoSaida]:
    return descrever_servicos(
        ctx.db,
        ctx.loja_id,
        servicos,
        com_locais=ctx.acesso.modulo_ativo('locais'),
        com_materiais=ctx.acesso.modulo_ativo('materiais'),
    )


def _conferir_ids(ctx: ContextoLoja, modelo: type, ids: list[UUID], mensagem: str) -> None:
    """Todos os ids existem na loja do token? (de outra loja = não encontrado)."""
    if not ids:
        return
    encontrados = set(
        ctx.db.scalars(select(modelo.id).where(modelo.loja_id == ctx.loja_id, modelo.id.in_(ids)))
    )
    if len(encontrados) != len(set(ids)):
        raise invalido(mensagem)


def _gravar_vinculos(ctx: ContextoLoja, servico: Servico, dados: ServicoEntrada) -> None:
    if dados.ativo and not dados.funcionario_ids:
        raise invalido('Selecione ao menos um profissional que realiza o serviço.')
    _conferir_ids(ctx, Funcionario, dados.funcionario_ids, 'Profissional não encontrado.')
    fixo = {'servico_id': servico.id}
    sincronizar_vinculos(
        ctx.db,
        ServicoFuncionario,
        ctx.loja_id,
        fixo,
        'funcionario_id',
        {i: {} for i in dados.funcionario_ids},
    )
    if dados.local_ids is not None and ctx.acesso.modulo_ativo('locais'):
        _conferir_ids(ctx, Local, dados.local_ids, 'Local não encontrado.')
        sincronizar_vinculos(
            ctx.db, ServicoLocal, ctx.loja_id, fixo, 'local_id', {i: {} for i in dados.local_ids}
        )
    if dados.materiais is not None and ctx.acesso.modulo_ativo('materiais'):
        _conferir_ids(ctx, Material, [m.material_id for m in dados.materiais], 'Material não encontrado.')
        sincronizar_vinculos(
            ctx.db,
            ServicoMaterial,
            ctx.loja_id,
            fixo,
            'material_id',
            {m.material_id: {'quantidade': m.quantidade} for m in dados.materiais},
        )


@router.get('', summary='Serviços com profissionais, locais e materiais')
def listar(ctx: Leitura, ativo: bool | None = None) -> list[ServicoSaida]:
    consulta = select(Servico).where(Servico.loja_id == ctx.loja_id)
    if ativo is not None:
        consulta = consulta.where(Servico.ativo == ativo)
    return _saida(ctx, list(ctx.db.scalars(consulta.order_by(func.lower(Servico.nome), Servico.id))))


@router.get('/{servico_id}', summary='Um serviço')
def obter(servico_id: UUID, ctx: Leitura) -> ServicoSaida:
    return _saida(ctx, [buscar(ctx.db, Servico, ctx.loja_id, servico_id, MSG_404)])[0]


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar serviço')
def criar(dados: ServicoEntrada, ctx: Escrita) -> ServicoSaida:
    campos = dados.model_dump(exclude={'funcionario_ids', 'local_ids', 'materiais'})
    servico = Servico(loja_id=ctx.loja_id, **campos)
    ctx.db.add(servico)
    ctx.db.flush()
    _gravar_vinculos(ctx, servico, dados)
    return _saida(ctx, [servico])[0]


@router.put('/{servico_id}', summary='Editar serviço e vínculos')
def editar(servico_id: UUID, dados: ServicoEntrada, ctx: Escrita) -> ServicoSaida:
    servico = buscar(ctx.db, Servico, ctx.loja_id, servico_id, MSG_404)
    for campo, valor in dados.model_dump(exclude={'funcionario_ids', 'local_ids', 'materiais'}).items():
        setattr(servico, campo, valor)
    ctx.db.flush()
    _gravar_vinculos(ctx, servico, dados)
    return _saida(ctx, [servico])[0]


@router.delete(
    '/{servico_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir serviço (agendamentos antigos continuam mostrando o serviço)',
)
def remover(servico_id: UUID, ctx: Escrita) -> None:
    excluir(ctx.db, buscar(ctx.db, Servico, ctx.loja_id, servico_id, MSG_404))
