"""Serviços (/api/loja/servicos). Recurso: servicos (módulo Serviços).

Vínculos (tabelas de ligação): profissionais habilitados, locais permitidos e materiais por
atendimento. Religar um vínculo removido restaura a linha existente (não cria outra).

- Serviço ativo precisa de pelo menos um profissional ativo vinculado (SER-02).
- Serviço com agendamentos ativos de agora em diante não é excluído (409): inative-o.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import exists, func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import (
    Agendamento,
    Funcionario,
    Local,
    Material,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
    ServicoMaterial,
)
from app.schemas.comum import Erro, Referencia
from app.schemas.servicos import (
    LocalDoServico,
    MaterialOpcao,
    OpcoesServico,
    ServicoEntrada,
    ServicoSaida,
)
from app.services.agendamentos import ATIVOS
from app.services.comum import (
    buscar,
    conferir_ids,
    conflito,
    excluir,
    invalido,
    sincronizar_vinculos,
)
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
    conferir_ids(ctx.db, modelo, ctx.loja_id, ids, mensagem)


def _gravar_vinculos(ctx: ContextoLoja, servico: Servico, dados: ServicoEntrada) -> None:
    if dados.ativo and not dados.funcionario_ids:
        raise invalido('Selecione ao menos um profissional que realiza o serviço.')
    _conferir_ids(ctx, Funcionario, dados.funcionario_ids, 'Profissional não encontrado.')
    if dados.ativo and not ctx.db.scalar(
        select(
            exists().where(
                Funcionario.loja_id == ctx.loja_id,
                Funcionario.id.in_(dados.funcionario_ids),
                Funcionario.ativo,
                Funcionario.excluido_em.is_(None),
            )
        )
    ):
        raise invalido('Selecione ao menos um profissional ativo que realiza o serviço.')
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


@router.get('/opcoes', summary='Profissionais, locais e materiais ativos para o formulário de serviço')
def opcoes(ctx: Escrita) -> OpcoesServico:
    """Quem edita serviços escolhe os vínculos sem precisar de acesso a Funcionários, Locais ou Materiais.

    Só itens ativos (para vínculos novos); os já vinculados vêm no próprio serviço. Locais e materiais
    são nulos com o módulo desligado.
    """
    db = ctx.db
    profissionais = [
        Referencia(id=i, nome=n)
        for i, n in db.execute(
            select(Funcionario.id, Funcionario.nome)
            .where(Funcionario.loja_id == ctx.loja_id, Funcionario.ativo)
            .order_by(func.lower(Funcionario.nome), Funcionario.id)
        )
    ]
    locais = None
    if ctx.acesso.modulo_ativo('locais'):
        locais = [
            LocalDoServico(id=loc.id, nome=loc.nome, tipo=loc.tipo)
            for loc in db.scalars(
                select(Local)
                .where(Local.loja_id == ctx.loja_id, Local.ativo)
                .order_by(func.lower(Local.nome), Local.id)
            )
        ]
    materiais = None
    if ctx.acesso.modulo_ativo('materiais'):
        materiais = [
            MaterialOpcao(id=i, nome=n, unidade=u)
            for i, n, u in db.execute(
                select(Material.id, Material.nome, Material.unidade)
                .where(Material.loja_id == ctx.loja_id, Material.ativo)
                .order_by(func.lower(Material.nome), Material.id)
            )
        ]
    return OpcoesServico(profissionais=profissionais, locais=locais, materiais=materiais)


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
    # FOR UPDATE: espera quem está marcando um agendamento com este serviço (a criação trava o
    # serviço com FOR KEY SHARE) e, se a exclusão vier primeiro, a criação passa a não achá-lo (LOG-02)
    servico = buscar(ctx.db, Servico, ctx.loja_id, servico_id, MSG_404, travar=True)
    com_agendamentos = ctx.db.scalar(
        select(
            exists().where(
                Agendamento.loja_id == ctx.loja_id,
                Agendamento.servico_id == servico.id,
                Agendamento.status.in_(ATIVOS),
                Agendamento.fim > func.now(),
                Agendamento.excluido_em.is_(None),
            )
        )
    )
    if com_agendamentos:
        raise conflito(
            'Este serviço tem agendamentos marcados de agora em diante e não pode ser excluído. '
            'Remarque ou cancele esses agendamentos, ou inative o serviço.'
        )
    excluir(ctx.db, servico)
