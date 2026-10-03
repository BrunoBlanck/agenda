"""Agendamentos (/api/loja/agendamentos), listas de apoio (/api/loja/apoio) e histórico do cliente.

Recursos: agenda_propria (só os próprios) e agenda_equipe (todos). As regras ficam em
app/services/agendamentos.py.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, Cargo, Cliente, Funcionario, Local, Material, Servico
from app.models.enums import NivelAcesso, StatusAgendamento
from app.schemas.agendamentos import (
    AgendamentoEntrada,
    AgendamentoSaida,
    ApoioAgendamento,
    ClienteApoio,
    Disponibilidade,
    FiltroHistorico,
    FiltrosAgenda,
    HistoricoCliente,
    LocalApoio,
    LocalFiltro,
    MateriaisEntrada,
    MaterialApoio,
    ProfissionalApoio,
    ProfissionalFiltro,
    RecusaEntrada,
    StatusEntrada,
)
from app.schemas.clientes import ClienteSaida
from app.schemas.comum import Data, DataHora, Erro, Pagina, Paginacao, paginacao
from app.services import agendamentos as regras
from app.services.clientes import filtro_busca_apoio
from app.services.comum import (
    buscar,
    com_autor,
    conflito,
    excluir,
    fuso,
    intervalo_de_dias,
    invalido,
    no_fuso,
    paginar,
    proibido,
)
from app.services.disponibilidade import mensagem_indisponivel
from app.services.servicos import descrever_servicos

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(tags=['Loja: agendamentos'], responses=ERROS)

AGENDA = ('agenda_propria', 'agenda_equipe')
VerAgenda = Annotated[ContextoLoja, Depends(exigir(AGENDA))]
EscreverAgenda = Annotated[ContextoLoja, Depends(exigir(AGENDA, 'escrita'))]
S = StatusAgendamento


def _detalhe(ctx: ContextoLoja, ag: Agendamento) -> AgendamentoSaida:
    return regras.descrever(ctx, [ag], com_materiais=ctx.acesso.modulo_ativo('materiais'))[0]


# --- Lista e detalhe -----------------------------------------------------------------------------


@router.get('/agendamentos', summary='Agendamentos (paginado, filtrado e só os que o usuário pode ver)')
def listar(
    ctx: VerAgenda,
    pag: Annotated[Paginacao, Depends(paginacao)],
    funcionario_id: UUID | None = None,
    local_id: UUID | None = None,
    cliente_id: UUID | None = None,
    servico_id: UUID | None = None,
    status_: Annotated[list[StatusAgendamento] | None, Query(alias='status')] = None,
    inicio: Annotated[Data | None, Query(description='Primeiro dia (no fuso da loja)')] = None,
    fim: Annotated[Data | None, Query(description='Último dia, inclusive')] = None,
    ordem: Annotated[
        Literal['asc', 'desc'],
        Query(description='Pelo início: asc = mais antigos primeiro (padrão); desc = mais recentes primeiro'),
    ] = 'asc',
) -> Pagina[AgendamentoSaida]:
    zona = fuso(ctx.loja.fuso_horario)
    consulta = select(Agendamento).where(Agendamento.loja_id == ctx.loja_id)
    visiveis = regras.filtro_visiveis(ctx)
    if visiveis is not None:
        consulta = consulta.where(visiveis)
    for coluna, valor in (
        (Agendamento.funcionario_id, funcionario_id),
        (Agendamento.local_id, local_id),
        (Agendamento.cliente_id, cliente_id),
        (Agendamento.servico_id, servico_id),
    ):
        if valor is not None:
            consulta = consulta.where(coluna == valor)
    if status_:
        consulta = consulta.where(Agendamento.status.in_(status_))
    if inicio and fim and fim < inicio:
        raise invalido('O fim do período deve ser depois do início.')
    if inicio:
        consulta = consulta.where(Agendamento.inicio >= intervalo_de_dias(inicio, inicio, zona)[0])
    if fim:
        consulta = consulta.where(Agendamento.inicio < intervalo_de_dias(fim, fim, zona)[1])
    if ordem == 'desc':
        consulta = consulta.order_by(Agendamento.inicio.desc(), Agendamento.id.desc())
    else:
        consulta = consulta.order_by(Agendamento.inicio, Agendamento.id)
    itens, total = paginar(ctx.db, consulta, pag)
    return Pagina(
        itens=regras.descrever(ctx, itens), total=total, pagina=pag.pagina, por_pagina=pag.por_pagina
    )


@router.get('/agendamentos/{agendamento_id}', summary='Um agendamento (com os materiais)')
def obter(agendamento_id: UUID, ctx: VerAgenda) -> AgendamentoSaida:
    return _detalhe(ctx, regras.buscar_visivel(ctx, agendamento_id))


# --- Criação, edição e exclusão ------------------------------------------------------------------


@router.post('/agendamentos', status_code=status.HTTP_201_CREATED, summary='Novo agendamento')
def criar(dados: AgendamentoEntrada, ctx: EscreverAgenda) -> AgendamentoSaida:
    return _detalhe(ctx, regras.salvar(ctx, dados))


@router.put(
    '/agendamentos/{agendamento_id}',
    summary='Editar (remarcar, trocar profissional/serviço/local) e, se informado, mudar o status',
)
def editar(agendamento_id: UUID, dados: AgendamentoEntrada, ctx: EscreverAgenda) -> AgendamentoSaida:
    ag = regras.buscar_visivel(ctx, agendamento_id, travar=True)
    return _detalhe(ctx, regras.salvar(ctx, dados, ag))


@router.delete(
    '/agendamentos/{agendamento_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir agendamento (concluído não é excluído)',
)
def remover(agendamento_id: UUID, ctx: EscreverAgenda) -> None:
    ag = regras.buscar_visivel(ctx, agendamento_id, travar=True)
    regras.exigir_edicao(ctx, ag)
    if ag.status == S.concluido:
        raise conflito('Agendamento concluído não pode ser excluído (os materiais já saíram do estoque).')
    excluir(ctx.db, ag)


# --- Status --------------------------------------------------------------------------------------


@router.post(
    '/agendamentos/{agendamento_id}/status', summary='Mudar o status (confirmar, concluir, cancelar...)'
)
def mudar_status(agendamento_id: UUID, dados: StatusEntrada, ctx: EscreverAgenda) -> AgendamentoSaida:
    ag = regras.buscar_visivel(ctx, agendamento_id, travar=True)
    regras.exigir_edicao(ctx, ag)
    regras.mudar_status(ctx, ag, dados.status, dados.motivo_cancelamento)
    return _detalhe(ctx, ag)


def _pendente(ctx: ContextoLoja, agendamento_id: UUID) -> Agendamento:
    ag = regras.buscar_visivel(ctx, agendamento_id, travar=True)
    regras.exigir_edicao(ctx, ag)
    if ag.status != S.pendente:
        raise conflito('Esta solicitação já foi respondida.')
    return ag


@router.post(
    '/agendamentos/{agendamento_id}/aceitar', summary='Aceitar solicitação do site (vira confirmado)'
)
def aceitar(agendamento_id: UUID, ctx: EscreverAgenda) -> AgendamentoSaida:
    ag = _pendente(ctx, agendamento_id)
    regras.mudar_status(ctx, ag, S.confirmado)
    return _detalhe(ctx, ag)


@router.post('/agendamentos/{agendamento_id}/recusar', summary='Recusar solicitação do site (vira cancelado)')
def recusar(
    agendamento_id: UUID, ctx: EscreverAgenda, dados: RecusaEntrada | None = None
) -> AgendamentoSaida:
    ag = _pendente(ctx, agendamento_id)
    motivo = (dados.motivo_cancelamento if dados else None) or 'Recusado pela loja'
    regras.mudar_status(ctx, ag, S.cancelado, motivo)
    return _detalhe(ctx, ag)


@router.put(
    '/agendamentos/{agendamento_id}/materiais',
    summary='Ajustar os materiais usados no atendimento (antes de concluir)',
)
def ajustar_materiais(agendamento_id: UUID, dados: MateriaisEntrada, ctx: EscreverAgenda) -> AgendamentoSaida:
    ag = regras.buscar_visivel(ctx, agendamento_id, travar=True)
    regras.exigir_edicao(ctx, ag)
    regras.ajustar_materiais(ctx, ag, {m.material_id: {'quantidade': m.quantidade} for m in dados.materiais})
    return _detalhe(ctx, ag)


# --- Listas de apoio do formulário ---------------------------------------------------------------


BUSCA_MINIMA = 2


@router.get('/apoio/clientes', summary='Busca de clientes ativos para o formulário de agendamento (paginada)')
def apoio_clientes(
    ctx: EscreverAgenda,
    pag: Annotated[Paginacao, Depends(paginacao)],
    busca: Annotated[
        str,
        Query(
            max_length=100,
            description=(
                f'Nome ou telefone (com ou sem máscara). Mínimo de {BUSCA_MINIMA} caracteres. '
                'Não busca por CPF nem e-mail'
            ),
        ),
    ],
) -> Pagina[ClienteApoio]:
    """Liberada para quem pode criar agendamentos, mesmo sem leitura em Clientes (ACE-21).

    Busca só por nome e telefone e devolve só id, nome, sobrenome e telefone (sem CPF nem e-mail).
    """
    termo = busca.strip()
    if len(termo) < BUSCA_MINIMA:
        raise invalido(f'Digite pelo menos {BUSCA_MINIMA} caracteres para buscar.')
    consulta = (
        select(Cliente)
        .where(Cliente.loja_id == ctx.loja_id, Cliente.ativo, filtro_busca_apoio(termo))
        .order_by(Cliente.nome, Cliente.sobrenome, Cliente.id)
    )
    itens, total = paginar(ctx.db, consulta, pag)
    return Pagina(
        itens=[ClienteApoio.model_validate(c) for c in itens],
        total=total,
        pagina=pag.pagina,
        por_pagina=pag.por_pagina,
    )


@router.get('/apoio/agendamento', summary='Serviços, profissionais e locais para o formulário')
def apoio(ctx: EscreverAgenda) -> ApoioAgendamento:
    """Liberado para quem pode criar agendamentos, mesmo sem leitura em Serviços (2.2).

    Quem só tem escrita em Minha agenda recebe só ele mesmo como profissional e só os serviços
    que realiza. Os clientes vêm de GET /apoio/clientes (busca paginada).
    """
    db = ctx.db
    para_outros = ctx.pode('agenda_equipe', NivelAcesso.escrita)
    consulta_prof = (
        select(Funcionario, Cargo.nome)
        .outerjoin(Cargo, (Cargo.id == Funcionario.cargo_id) & (Cargo.loja_id == Funcionario.loja_id))
        .where(Funcionario.loja_id == ctx.loja_id, Funcionario.ativo)
        .order_by(Funcionario.nome)
    )
    if not para_outros:
        consulta_prof = consulta_prof.where(Funcionario.id == ctx.funcionario.id)
    profissionais = []
    for funcionario, cargo_nome in db.execute(consulta_prof):
        item = ProfissionalApoio.model_validate(funcionario)
        item.cargo_nome = cargo_nome
        profissionais.append(item)

    servicos = None
    if ctx.acesso.modulo_ativo('servicos'):
        lista = db.scalars(
            select(Servico)
            .where(Servico.loja_id == ctx.loja_id, Servico.ativo)
            .order_by(func.lower(Servico.nome))
        ).all()
        servicos = descrever_servicos(
            db,
            ctx.loja_id,
            lista,
            com_locais=ctx.acesso.modulo_ativo('locais'),
            com_materiais=ctx.acesso.modulo_ativo('materiais'),
            so_profissionais_ativos=True,
        )
        if not para_outros:
            servicos = [s for s in servicos if ctx.funcionario.id in s.funcionario_ids]
    locais = None
    if ctx.acesso.modulo_ativo('locais'):
        locais = [
            LocalApoio.model_validate(loc)
            for loc in db.scalars(
                select(Local)
                .where(Local.loja_id == ctx.loja_id, Local.ativo)
                .order_by(func.lower(Local.nome))
            )
        ]
    materiais = None
    if ctx.acesso.modulo_ativo('materiais'):
        materiais = [
            MaterialApoio.model_validate(m)
            for m in db.scalars(
                select(Material)
                .where(Material.loja_id == ctx.loja_id, Material.ativo)
                .order_by(func.lower(Material.nome), Material.id)
            )
        ]
    return ApoioAgendamento(
        servicos=servicos,
        profissionais=profissionais,
        locais=locais,
        materiais=materiais,
    )


@router.get(
    '/apoio/filtros-agenda',
    summary='Profissionais e locais para os filtros da agenda e da lista de agendamentos',
)
def filtros_agenda(ctx: VerAgenda) -> FiltrosAgenda:
    """Liberado com leitura na agenda (os filtros da tela não exigem escrita).

    Quem só tem Minha agenda recebe só ele mesmo. Inclui profissionais e locais inativos, para
    filtrar agendamentos antigos; os ativos vêm primeiro.
    """
    db = ctx.db
    so_propria = not ctx.pode('agenda_equipe')
    consulta_prof = select(Funcionario).where(Funcionario.loja_id == ctx.loja_id)
    if so_propria:
        consulta_prof = consulta_prof.where(Funcionario.id == ctx.funcionario.id)
    profissionais = [
        ProfissionalFiltro.model_validate(f)
        for f in db.scalars(
            consulta_prof.order_by(Funcionario.ativo.desc(), func.lower(Funcionario.nome), Funcionario.id)
        )
    ]
    locais = None
    if ctx.acesso.modulo_ativo('locais'):
        locais = [
            LocalFiltro.model_validate(loc)
            for loc in db.scalars(
                select(Local)
                .where(Local.loja_id == ctx.loja_id)
                .order_by(Local.ativo.desc(), func.lower(Local.nome), Local.id)
            )
        ]
    return FiltrosAgenda(so_propria=so_propria, profissionais=profissionais, locais=locais)


@router.get(
    '/apoio/disponibilidade', summary='O horário está livre? (aviso de jornada/bloqueio e locais ocupados)'
)
def disponibilidade(
    ctx: EscreverAgenda,
    funcionario_id: UUID,
    inicio: Annotated[DataHora, Query(description='Sem fuso, vale o horário da loja')],
    duracao_minutos: Annotated[int, Query(gt=0, le=24 * 60)],
    agendamento_id: Annotated[UUID | None, Query(description='Ignora este agendamento (edição)')] = None,
) -> Disponibilidade:
    if not regras.pode_editar(ctx, funcionario_id):
        raise proibido('Você só pode consultar a sua própria agenda.')
    funcionario = buscar(ctx.db, Funcionario, ctx.loja_id, funcionario_id, 'Profissional não encontrado.')
    zona = fuso(ctx.loja.fuso_horario)
    ini = no_fuso(inicio, zona)
    fim = ini + timedelta(minutes=duracao_minutos)
    outros = [Agendamento.loja_id == ctx.loja_id, *regras.ocupa_intervalo(ini, fim)]
    if agendamento_id is not None:
        outros.append(Agendamento.id != agendamento_id)
    ocupado = ctx.db.scalar(
        select(func.count())
        .select_from(Agendamento)
        .where(*outros, Agendamento.funcionario_id == funcionario.id)
    )
    locais = ctx.db.scalars(
        select(Agendamento.local_id).where(*outros, Agendamento.local_id.is_not(None)).distinct()
    ).all()
    return Disponibilidade(
        aviso=mensagem_indisponivel(ctx.db, ctx.loja_id, funcionario, ini, fim, zona),
        profissional_ocupado=bool(ocupado),
        locais_ocupados=list(locais),
    )


# --- Histórico do cliente ------------------------------------------------------------------------


@router.get(
    '/clientes/{cliente_id}/historico',
    tags=['Loja: clientes'],
    summary='Histórico do cliente: resumo e agendamentos que o usuário pode ver (mais recentes primeiro)',
)
def historico(
    cliente_id: UUID,
    ctx: Annotated[ContextoLoja, Depends(exigir('clientes'))],
    pag: Annotated[Paginacao, Depends(paginacao)],
    filtro: FiltroHistorico = 'todos',
) -> HistoricoCliente:
    db = ctx.db
    cliente = buscar(db, Cliente, ctx.loja_id, cliente_id, 'Cliente não encontrado.')
    do_cliente = [Agendamento.loja_id == ctx.loja_id, Agendamento.cliente_id == cliente.id]
    visiveis = regras.filtro_visiveis(ctx)
    filtro_visiveis = [*do_cliente, *([visiveis] if visiveis is not None else [])]

    total_geral = db.scalar(select(func.count()).select_from(Agendamento).where(*do_cliente)) or 0
    contagem = dict(
        db.execute(
            select(Agendamento.status, func.count()).where(*filtro_visiveis).group_by(Agendamento.status)
        ).all()
    )
    total_gasto = db.scalar(
        select(func.coalesce(func.sum(Agendamento.preco), 0)).where(
            *filtro_visiveis, Agendamento.status == S.concluido
        )
    )
    ultimo = db.scalar(
        select(Agendamento)
        .where(*filtro_visiveis, Agendamento.status == S.concluido)
        .order_by(Agendamento.inicio.desc())
        .limit(1)
    )
    proximo = db.scalar(
        select(Agendamento)
        .where(
            *filtro_visiveis,
            Agendamento.status.in_((S.pendente, S.agendado, S.confirmado)),
            Agendamento.inicio > func.now(),
        )
        .order_by(Agendamento.inicio)
        .limit(1)
    )
    consulta = select(Agendamento).where(*filtro_visiveis)
    if filtro == 'concluidos':
        consulta = consulta.where(Agendamento.status == S.concluido)
    elif filtro == 'faltas':
        consulta = consulta.where(Agendamento.status.in_((S.nao_compareceu, S.cancelado)))
    itens, total = paginar(db, consulta.order_by(Agendamento.inicio.desc(), Agendamento.id), pag)

    destaques = regras.descrever(ctx, [a for a in (ultimo, proximo) if a is not None])
    por_id = {d.id: d for d in destaques}
    return HistoricoCliente(
        cliente=com_autor(db, ctx.loja_id, [ClienteSaida.model_validate(cliente)])[0],
        concluidos=contagem.get(S.concluido, 0),
        faltas=contagem.get(S.nao_compareceu, 0),
        cancelados=contagem.get(S.cancelado, 0),
        total_gasto=Decimal(total_gasto or 0),
        ultimo=por_id.get(ultimo.id) if ultimo else None,
        proximo=por_id.get(proximo.id) if proximo else None,
        parcial=sum(contagem.values()) < total_geral,
        agendamentos=Pagina(
            itens=regras.descrever(ctx, itens), total=total, pagina=pag.pagina, por_pagina=pag.por_pagina
        ),
    )
