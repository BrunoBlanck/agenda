"""Configurações › Perfis e horários (/api/loja/perfis, /horarios, /bloqueios, /recursos).

Recursos (estrutura.md, 1.8):
- perfis_acesso: criar, renomear e excluir perfis e definir os níveis;
- config_agendamentos: jornada semanal (perfil_horarios) e bloqueios (bloqueios_agenda).

A lista de perfis (id, nome e funcionários) também é liberada para quem tem leitura em
Funcionários, para escolher o perfil no cadastro (lista de apoio, 2.2).
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, func, or_, select

from app.auth.dependencias import ContextoLoja, ContextoLojaDep, exigir
from app.models import (
    BloqueioAgenda,
    Funcionalidade,
    Funcionario,
    Perfil,
    PerfilAcesso,
    PerfilHorario,
    Recurso,
)
from app.models.enums import NivelAcesso
from app.schemas.comum import Erro
from app.schemas.perfis import (
    AcessosEntrada,
    BloqueioEntrada,
    BloqueioSaida,
    FuncionarioDoPerfil,
    HorarioEntrada,
    HorarioSaida,
    PerfilEdicao,
    PerfilNovo,
    PerfilSaida,
    RecursoSaida,
)
from app.services.comum import (
    buscar,
    com_autor,
    conflito,
    excluir,
    fuso,
    intervalo_de_dias,
    invalido,
    no_fuso,
)
from app.services.disponibilidade import descrever_bloqueios

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(tags=['Loja: perfis e horários'], responses=ERROS)

MSG_404 = 'Perfil não encontrado.'

VerPerfis = Annotated[ContextoLoja, Depends(exigir(('perfis_acesso', 'config_agendamentos', 'funcionarios')))]
EscritaPerfis = Annotated[ContextoLoja, Depends(exigir('perfis_acesso', 'escrita'))]
LeituraHorarios = Annotated[ContextoLoja, Depends(exigir('config_agendamentos'))]
EscritaHorarios = Annotated[ContextoLoja, Depends(exigir('config_agendamentos', 'escrita'))]


# --- Catálogo de recursos ----------------------------------------------------------------------


@router.get('/recursos', summary='Catálogo de recursos (áreas com nível de acesso)')
def recursos(ctx: ContextoLojaDep) -> list[RecursoSaida]:
    linhas = ctx.db.execute(
        select(Recurso, Funcionalidade.codigo)
        .join(Funcionalidade, Funcionalidade.id == Recurso.funcionalidade_id)
        .order_by(Recurso.ordem, Recurso.codigo)
    ).all()
    return [
        RecursoSaida(
            codigo=r.codigo,
            nome=r.nome,
            descricao=r.descricao,
            modulo=modulo,
            modulo_ativo=ctx.acesso.modulo_ativo(modulo),
            ordem=r.ordem,
        )
        for r, modulo in linhas
    ]


# --- Perfis ------------------------------------------------------------------------------------


def _perfis(ctx: ContextoLoja, perfis: list[Perfil]) -> list[PerfilSaida]:
    db = ctx.db
    ids = [p.id for p in perfis]
    funcionarios = db.scalars(
        select(Funcionario)
        .where(Funcionario.loja_id == ctx.loja_id, Funcionario.perfil_id.in_(ids))
        .order_by(Funcionario.nome)
    ).all()
    com_jornada = set(
        db.scalars(
            select(PerfilHorario.perfil_id)
            .where(PerfilHorario.loja_id == ctx.loja_id, PerfilHorario.perfil_id.in_(ids))
            .distinct()
        )
    )
    niveis: dict[UUID, dict[str, NivelAcesso]] = {i: {} for i in ids}
    ver_niveis = ctx.pode('perfis_acesso')
    if ver_niveis:
        for perfil_id, codigo, nivel in db.execute(
            select(PerfilAcesso.perfil_id, Recurso.codigo, PerfilAcesso.nivel)
            .join(Recurso, Recurso.id == PerfilAcesso.recurso_id)
            .where(PerfilAcesso.loja_id == ctx.loja_id, PerfilAcesso.perfil_id.in_(ids))
        ):
            niveis[perfil_id][codigo] = nivel
    saida = []
    for p in perfis:
        item = PerfilSaida.model_validate(p)
        item.funcionarios = [
            FuncionarioDoPerfil.model_validate(f) for f in funcionarios if f.perfil_id == p.id
        ]
        item.sem_jornada = p.id not in com_jornada
        if ver_niveis:
            item.acessos = niveis[p.id]
        saida.append(item)
    return com_autor(db, ctx.loja_id, saida)


def _definir_niveis(ctx: ContextoLoja, perfil: Perfil, niveis: dict[str, NivelAcesso]) -> None:
    """Grava o nível de cada recurso (restaura a linha se ela tiver sido excluída)."""
    recursos = dict(ctx.db.execute(select(Recurso.codigo, Recurso.id)).all())
    desconhecidos = sorted(set(niveis) - set(recursos))
    if desconhecidos:
        raise invalido(f'Recurso desconhecido: {", ".join(desconhecidos)}.')
    existentes = {
        a.recurso_id: a
        for a in ctx.db.scalars(
            select(PerfilAcesso)
            .where(PerfilAcesso.loja_id == ctx.loja_id, PerfilAcesso.perfil_id == perfil.id)
            .execution_options(incluir_excluidos=True)
        )
    }
    for codigo, nivel in niveis.items():
        linha = existentes.get(recursos[codigo])
        if linha is None:
            ctx.db.add(
                PerfilAcesso(
                    loja_id=ctx.loja_id, perfil_id=perfil.id, recurso_id=recursos[codigo], nivel=nivel
                )
            )
            continue
        if linha.excluido_em is not None:
            linha.excluido_em = None
        if linha.nivel != nivel:
            linha.nivel = nivel
    ctx.db.flush()


@router.get('/perfis', summary='Perfis da loja, com funcionários e (para quem pode ver) os níveis')
def listar_perfis(ctx: VerPerfis) -> list[PerfilSaida]:
    perfis = ctx.db.scalars(
        select(Perfil)
        .where(Perfil.loja_id == ctx.loja_id)
        .order_by(Perfil.acesso_total.desc(), Perfil.padrao.desc(), func.lower(Perfil.nome))
    ).all()
    return _perfis(ctx, list(perfis))


@router.get('/perfis/{perfil_id}', summary='Um perfil')
def obter_perfil(perfil_id: UUID, ctx: VerPerfis) -> PerfilSaida:
    return _perfis(ctx, [buscar(ctx.db, Perfil, ctx.loja_id, perfil_id, MSG_404)])[0]


@router.post(
    '/perfis', status_code=status.HTTP_201_CREATED, summary='Criar perfil (opcionalmente copiando outro)'
)
def criar_perfil(dados: PerfilNovo, ctx: EscritaPerfis) -> PerfilSaida:
    base = buscar(ctx.db, Perfil, ctx.loja_id, dados.copiar_de, MSG_404) if dados.copiar_de else None
    perfil = Perfil(loja_id=ctx.loja_id, nome=dados.nome, descricao=dados.descricao)
    ctx.db.add(perfil)
    ctx.db.flush()

    niveis = dict.fromkeys(ctx.db.scalars(select(Recurso.codigo)), NivelAcesso.nenhum)
    if base is not None and not base.acesso_total:
        for codigo, nivel in ctx.db.execute(
            select(Recurso.codigo, PerfilAcesso.nivel)
            .join(Recurso, Recurso.id == PerfilAcesso.recurso_id)
            .where(PerfilAcesso.loja_id == ctx.loja_id, PerfilAcesso.perfil_id == base.id)
        ):
            niveis[codigo] = nivel
    _definir_niveis(ctx, perfil, niveis)

    if base is not None:
        for faixa in ctx.db.scalars(
            select(PerfilHorario).where(
                PerfilHorario.loja_id == ctx.loja_id, PerfilHorario.perfil_id == base.id
            )
        ):
            ctx.db.add(
                PerfilHorario(
                    loja_id=ctx.loja_id,
                    perfil_id=perfil.id,
                    dia_semana=faixa.dia_semana,
                    hora_inicio=faixa.hora_inicio,
                    hora_fim=faixa.hora_fim,
                )
            )
        ctx.db.flush()
    return _perfis(ctx, [perfil])[0]


@router.put('/perfis/{perfil_id}', summary='Renomear perfil (perfis padrão não são renomeados)')
def editar_perfil(perfil_id: UUID, dados: PerfilEdicao, ctx: EscritaPerfis) -> PerfilSaida:
    perfil = buscar(ctx.db, Perfil, ctx.loja_id, perfil_id, MSG_404)
    if perfil.padrao and dados.nome != perfil.nome:
        raise conflito('Perfis padrão não podem ser renomeados.')
    perfil.nome, perfil.descricao = dados.nome, dados.descricao
    ctx.db.flush()
    return _perfis(ctx, [perfil])[0]


@router.put('/perfis/{perfil_id}/acessos', summary='Definir os níveis de acesso do perfil')
def definir_acessos(perfil_id: UUID, dados: AcessosEntrada, ctx: EscritaPerfis) -> PerfilSaida:
    perfil = buscar(ctx.db, Perfil, ctx.loja_id, perfil_id, MSG_404)
    if perfil.acesso_total:
        raise conflito('O perfil Administrador tem escrita em tudo e não pode ser alterado.')
    _definir_niveis(ctx, perfil, dados.acessos)
    return _perfis(ctx, [perfil])[0]


@router.delete(
    '/perfis/{perfil_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir perfil (não padrão e sem funcionários). Leva junto a jornada e os bloqueios dele',
)
def excluir_perfil(perfil_id: UUID, ctx: EscritaPerfis) -> None:
    perfil = buscar(ctx.db, Perfil, ctx.loja_id, perfil_id, MSG_404)
    if perfil.padrao:
        raise conflito('Perfis padrão não podem ser excluídos.')
    com_funcionarios = ctx.db.scalar(
        select(func.count())
        .select_from(Funcionario)
        .where(
            Funcionario.loja_id == ctx.loja_id,
            Funcionario.perfil_id == perfil.id,
            Funcionario.excluido_em.is_(None),
        )
    )
    if com_funcionarios:
        raise conflito('Há funcionários com este perfil. Troque o perfil deles antes de excluir.')
    for modelo in (PerfilAcesso, PerfilHorario, BloqueioAgenda):
        for linha in ctx.db.scalars(
            select(modelo).where(modelo.loja_id == ctx.loja_id, modelo.perfil_id == perfil.id)
        ):
            linha.excluido_em = func.now()
    excluir(ctx.db, perfil)


# --- Jornada semanal ---------------------------------------------------------------------------


def _horarios(ctx: ContextoLoja, faixas: list[PerfilHorario]) -> list[HorarioSaida]:
    return com_autor(ctx.db, ctx.loja_id, [HorarioSaida.model_validate(f) for f in faixas])


@router.get('/horarios', summary='Jornada semanal (todas as faixas, ou só as de um perfil)')
def listar_horarios(ctx: LeituraHorarios, perfil_id: UUID | None = None) -> list[HorarioSaida]:
    consulta = select(PerfilHorario).where(PerfilHorario.loja_id == ctx.loja_id)
    if perfil_id is not None:
        consulta = consulta.where(PerfilHorario.perfil_id == perfil_id)
    consulta = consulta.order_by(PerfilHorario.perfil_id, PerfilHorario.dia_semana, PerfilHorario.hora_inicio)
    return _horarios(ctx, list(ctx.db.scalars(consulta)))


@router.post(
    '/perfis/{perfil_id}/horarios',
    status_code=status.HTTP_201_CREATED,
    summary='Adicionar uma faixa à jornada do perfil',
)
def adicionar_horario(perfil_id: UUID, dados: HorarioEntrada, ctx: EscritaHorarios) -> HorarioSaida:
    perfil = buscar(ctx.db, Perfil, ctx.loja_id, perfil_id, MSG_404)
    sobreposta = ctx.db.scalar(
        select(PerfilHorario.id).where(
            PerfilHorario.loja_id == ctx.loja_id,
            PerfilHorario.perfil_id == perfil.id,
            PerfilHorario.dia_semana == dados.dia_semana,
            PerfilHorario.hora_inicio < dados.hora_fim,
            PerfilHorario.hora_fim > dados.hora_inicio,
        )
    )
    if sobreposta:
        raise conflito('Essa faixa se sobrepõe a outra do mesmo dia.')
    faixa = PerfilHorario(loja_id=ctx.loja_id, perfil_id=perfil.id, **dados.model_dump())
    ctx.db.add(faixa)
    ctx.db.flush()
    return _horarios(ctx, [faixa])[0]


@router.delete('/horarios/{horario_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Remover faixa')
def remover_horario(horario_id: UUID, ctx: EscritaHorarios) -> None:
    excluir(
        ctx.db, buscar(ctx.db, PerfilHorario, ctx.loja_id, horario_id, 'Faixa de horário não encontrada.')
    )


# --- Bloqueios ---------------------------------------------------------------------------------


@router.get('/bloqueios', summary='Bloqueios, folgas e feriados')
def listar_bloqueios(
    ctx: LeituraHorarios,
    perfil_id: Annotated[
        UUID | None, Query(description='Os da loja inteira, do perfil e de cada funcionário dele')
    ] = None,
    funcionario_id: Annotated[
        UUID | None, Query(description='Os que atingem o funcionário: loja, perfil dele e ele próprio')
    ] = None,
    inicio: Annotated[date | None, Query(description='Só os que terminam a partir deste dia')] = None,
    fim: Annotated[date | None, Query(description='Só os que começam até este dia')] = None,
) -> list[BloqueioSaida]:
    zona = fuso(ctx.loja.fuso_horario)
    da_loja = and_(BloqueioAgenda.perfil_id.is_(None), BloqueioAgenda.funcionario_id.is_(None))
    consulta = select(BloqueioAgenda).where(BloqueioAgenda.loja_id == ctx.loja_id)
    if perfil_id is not None:
        do_perfil = select(Funcionario.id).where(
            Funcionario.loja_id == ctx.loja_id, Funcionario.perfil_id == perfil_id
        )
        consulta = consulta.where(
            or_(
                da_loja,
                BloqueioAgenda.perfil_id == perfil_id,
                BloqueioAgenda.funcionario_id.in_(do_perfil.scalar_subquery()),
            )
        )
    if funcionario_id is not None:
        funcionario = buscar(ctx.db, Funcionario, ctx.loja_id, funcionario_id, 'Funcionário não encontrado.')
        consulta = consulta.where(
            or_(
                da_loja,
                BloqueioAgenda.perfil_id == funcionario.perfil_id,
                BloqueioAgenda.funcionario_id == funcionario.id,
            )
        )
    if inicio is not None:
        consulta = consulta.where(BloqueioAgenda.fim > intervalo_de_dias(inicio, inicio, zona)[0])
    if fim is not None:
        consulta = consulta.where(BloqueioAgenda.inicio < intervalo_de_dias(fim, fim, zona)[1])
    bloqueios = ctx.db.scalars(consulta.order_by(BloqueioAgenda.inicio, BloqueioAgenda.id)).all()
    return descrever_bloqueios(ctx.db, ctx.loja_id, bloqueios, zona)


@router.post('/bloqueios', status_code=status.HTTP_201_CREATED, summary='Novo bloqueio')
def criar_bloqueio(dados: BloqueioEntrada, ctx: EscritaHorarios) -> BloqueioSaida:
    zona = fuso(ctx.loja.fuso_horario)
    inicio, fim = no_fuso(dados.inicio, zona), no_fuso(dados.fim, zona)
    if fim <= inicio:
        raise invalido('O fim do bloqueio deve ser depois do início.')
    if dados.perfil_id is not None:
        buscar(ctx.db, Perfil, ctx.loja_id, dados.perfil_id, MSG_404)
    if dados.funcionario_id is not None:
        buscar(ctx.db, Funcionario, ctx.loja_id, dados.funcionario_id, 'Funcionário não encontrado.')
    bloqueio = BloqueioAgenda(
        loja_id=ctx.loja_id,
        perfil_id=dados.perfil_id,
        funcionario_id=dados.funcionario_id,
        inicio=inicio,
        fim=fim,
        motivo=dados.motivo,
    )
    ctx.db.add(bloqueio)
    ctx.db.flush()
    return descrever_bloqueios(ctx.db, ctx.loja_id, [bloqueio], zona)[0]


@router.delete('/bloqueios/{bloqueio_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Remover bloqueio')
def remover_bloqueio(bloqueio_id: UUID, ctx: EscritaHorarios) -> None:
    excluir(ctx.db, buscar(ctx.db, BloqueioAgenda, ctx.loja_id, bloqueio_id, 'Bloqueio não encontrado.'))
