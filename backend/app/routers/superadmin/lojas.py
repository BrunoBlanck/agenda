"""Lojas da plataforma (/api/superadmin/lojas): cadastro, situação, módulos e funcionários pelo suporte.

O superadmin escolhe a loja pela URL (não há loja no token). Tudo grava com o contexto de superadmin:
nas tabelas da loja, ``atualizado_por`` fica NULL e a auditoria guarda o ``superadmin_id``
(estrutura.md, "Colunas de controle").
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.catalogo import MODULOS
from app.auth.dependencias import ContextoSuperadmin, ContextoSuperadminDep, ip_da_requisicao
from app.auth.senhas import gerar_hash, gerar_senha_provisoria
from app.db import fuso_conhecido_pelo_banco
from app.models import (
    Funcionalidade,
    Funcionario,
    Loja,
    LojaConfiguracao,
    LojaFuncionalidade,
    Perfil,
    Plano,
)
from app.models.enums import StatusLoja, TipoLoja
from app.schemas.comum import Erro, Pagina, Paginacao, paginacao
from app.schemas.superadmin import (
    MSG_FUSO,
    AcessoLoja,
    FuncionarioSuporte,
    FuncionarioSuporteCriacao,
    FuncionarioSuporteCriado,
    FuncionarioSuporteEdicao,
    LojaCriacao,
    LojaCriada,
    LojaDetalhe,
    LojaEdicao,
    LojaEntrada,
    LojaOpcao,
    LojaResumo,
    ModuloEntrada,
    ModuloLoja,
    PerfilOpcao,
    RedefinirSenha,
    SenhaRedefinida,
    StatusEntrada,
)
from app.services.arquivos import remover_logo, trocar_logo
from app.services.comum import (
    buscar,
    conflito,
    erro_de_campo,
    excluir,
    fuso,
    invalido,
    nao_encontrado,
    no_fuso,
    paginar,
)
from app.services.funcionarios import MSG_ULTIMO_ADMIN, deixa_loja_sem_admin
from app.services.lojas import provisionar_loja
from app.services.plataforma import (
    MSG_PLANO_404,
    buscar_loja,
    funcionarios_ativos_por_loja,
    modulos_opcionais_por_loja,
    nomes_planos,
    nomes_superadmins,
    ultima_alteracao_loja,
)
from app.services.suporte import abrir_acesso_suporte

ERROS = {404: {'model': Erro}, 409: {'model': Erro}, 422: {'model': Erro}}
router = APIRouter(prefix='/lojas', tags=['Superadmin: lojas'], responses=ERROS)

MSG_FUNC_404 = 'Funcionário não encontrado.'


# --- Saída ---------------------------------------------------------------------------------------


def _no_fuso[D: datetime | None](momento: D, zona: ZoneInfo) -> D:
    """Momentos gravados em UTC saem no fuso da loja (GER-15), como no painel da loja."""
    return momento.astimezone(zona) if momento is not None and momento.tzinfo is not None else momento


def _resumos[S: LojaResumo](db, lojas: list[Loja], modelo: type[S]) -> list[S]:
    planos = nomes_planos(db, (loja.plano_id for loja in lojas))
    modulos = modulos_opcionais_por_loja(db, (loja.id for loja in lojas))
    funcionarios = funcionarios_ativos_por_loja(db, (loja.id for loja in lojas))
    saida = []
    for loja in lojas:
        item = modelo.model_validate(loja)
        item.criado_em = _no_fuso(item.criado_em, fuso(loja.fuso_horario))
        item.plano_nome = planos.get(loja.plano_id) if loja.plano_id else None
        item.modulos = modulos.get(loja.id, {})
        item.funcionarios_ativos = funcionarios.get(loja.id, 0)
        saida.append(item)
    return saida


def _detalhe(db, loja: Loja) -> LojaDetalhe:
    item = _resumos(db, [loja], LojaDetalhe)[0]
    configuracao = db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == loja.id))
    if configuracao is not None:
        item.rotulo_local = configuracao.rotulo_local
        item.rotulo_local_plural = configuracao.rotulo_local_plural
    item.atualizado_em = _no_fuso(item.atualizado_em, fuso(loja.fuso_horario))
    ultima = ultima_alteracao_loja(db, loja.id)
    item.atualizado_por, item.atualizado_por_nome = ultima.autor, ultima.nome
    return item


def _validar_plano(db, plano_id: UUID, atual: UUID | None = None) -> None:
    plano = db.scalar(select(Plano).where(Plano.id == plano_id))
    if plano is None:
        raise invalido(MSG_PLANO_404)
    if not plano.ativo and plano_id != atual:
        raise invalido('Este plano está inativo e não pode ser escolhido.')


def _validar_fuso(db: Session, fuso_horario: str) -> None:
    """O fuso vira o TimeZone das transações da loja (app.db): precisa existir também no Postgres."""
    if not fuso_conhecido_pelo_banco(db, fuso_horario):
        raise erro_de_campo('fuso_horario', MSG_FUSO)


def _aplicar(loja: Loja, dados: LojaEntrada) -> None:
    for campo in LojaEntrada.model_fields:
        valor = getattr(dados, campo)
        if getattr(loja, campo) != valor:
            setattr(loja, campo, valor)


# --- Lojas ---------------------------------------------------------------------------------------


@router.get('', summary='Lojas (paginada, com filtros)')
def listar(
    ctx: ContextoSuperadminDep,
    pag: Annotated[Paginacao, Depends(paginacao)],
    busca: Annotated[
        str | None, Query(max_length=100, description='Nome, razão social, slug ou cidade')
    ] = None,
    tipo: TipoLoja | None = None,
    situacao: Annotated[StatusLoja | None, Query(alias='status')] = None,
) -> Pagina[LojaResumo]:
    consulta = select(Loja)
    if busca and busca.strip():
        termo = busca.strip()
        consulta = consulta.where(
            or_(
                Loja.nome_fantasia.icontains(termo, autoescape=True),
                Loja.nome.icontains(termo, autoescape=True),
                Loja.slug.icontains(termo, autoescape=True),
                Loja.cidade.icontains(termo, autoescape=True),
            )
        )
    if tipo is not None:
        consulta = consulta.where(Loja.tipo == tipo)
    if situacao is not None:
        consulta = consulta.where(Loja.status == situacao)
    consulta = consulta.order_by(func.lower(func.coalesce(Loja.nome_fantasia, Loja.nome)), Loja.id)
    itens, total = paginar(ctx.db, consulta, pag)
    return Pagina(
        itens=_resumos(ctx.db, itens, LojaResumo), total=total, pagina=pag.pagina, por_pagina=pag.por_pagina
    )


@router.get('/opcoes', summary='Todas as lojas (id e nome), para listas de escolha')
def opcoes(ctx: ContextoSuperadminDep) -> list[LojaOpcao]:
    lojas = ctx.db.scalars(select(Loja).order_by(func.lower(func.coalesce(Loja.nome_fantasia, Loja.nome))))
    return [LojaOpcao.model_validate(loja) for loja in lojas]


@router.post(
    '', status_code=status.HTTP_201_CREATED, summary='Criar loja com módulos e o primeiro Administrador'
)
def criar(dados: LojaCriacao, ctx: ContextoSuperadminDep) -> LojaCriada:
    db = ctx.db
    _validar_plano(db, dados.plano_id)
    _validar_fuso(db, dados.fuso_horario)
    loja = Loja(**{campo: getattr(dados, campo) for campo in LojaEntrada.model_fields})
    db.add(loja)
    db.flush()
    perfis = provisionar_loja(
        db,
        loja.id,
        {codigo: codigo in dados.modulos for codigo, opcional in MODULOS.items() if opcional},
        rotulo_local=dados.rotulo_local,
        rotulo_local_plural=dados.rotulo_local_plural,
    )
    senha = dados.admin.senha or gerar_senha_provisoria()
    admin = Funcionario(
        loja_id=loja.id,
        perfil_id=perfis['Administrador'].id,
        nome=dados.admin.nome,
        email=dados.admin.email,
        senha_hash=gerar_hash(senha),
    )
    db.add(admin)
    db.flush()
    detalhe = _detalhe(db, loja)
    return LojaCriada(
        **detalhe.model_dump(),
        admin=_funcionarios(ctx, loja.id, [admin])[0],
        senha_provisoria=None if dados.admin.senha else senha,
    )


@router.get('/{loja_id}', summary='Detalhe da loja')
def obter(loja_id: UUID, ctx: ContextoSuperadminDep) -> LojaDetalhe:
    return _detalhe(ctx.db, buscar_loja(ctx.db, loja_id))


@router.put('/{loja_id}', summary='Editar a loja (dados, tipo, slug, plano, fuso e situação)')
def editar(loja_id: UUID, dados: LojaEdicao, ctx: ContextoSuperadminDep) -> LojaDetalhe:
    loja = buscar_loja(ctx.db, loja_id)
    _validar_plano(ctx.db, dados.plano_id, loja.plano_id)
    _validar_fuso(ctx.db, dados.fuso_horario)
    _aplicar(loja, dados)
    if dados.status is not None and loja.status != dados.status:
        loja.status = dados.status
    ctx.db.flush()
    return _detalhe(ctx.db, loja)


@router.post('/{loja_id}/status', summary='Suspender, reativar ou cancelar a loja')
def mudar_status(loja_id: UUID, dados: StatusEntrada, ctx: ContextoSuperadminDep) -> LojaDetalhe:
    loja = buscar_loja(ctx.db, loja_id)
    if loja.status != dados.status:
        loja.status = dados.status
        ctx.db.flush()
    return _detalhe(ctx.db, loja)


@router.put(
    '/{loja_id}/logo',
    responses={413: {'model': Erro}},
    summary='Enviar a logo da loja (multipart, campo "arquivo": PNG, JPEG ou WebP, até 2 MB)',
)
def enviar_logo(
    loja_id: UUID,
    arquivo: Annotated[UploadFile, File(description='PNG, JPEG ou WebP')],
    ctx: ContextoSuperadminDep,
) -> LojaDetalhe:
    return _detalhe(ctx.db, trocar_logo(ctx.db, loja_id, arquivo.file))


@router.delete(
    '/{loja_id}/logo',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Remover a logo da loja (apaga o arquivo)',
)
def excluir_logo(loja_id: UUID, ctx: ContextoSuperadminDep) -> None:
    remover_logo(ctx.db, loja_id)


@router.delete(
    '/{loja_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir a loja (exclusão lógica; só lojas canceladas)',
)
def remover(loja_id: UUID, ctx: ContextoSuperadminDep) -> None:
    loja = buscar_loja(ctx.db, loja_id)
    if loja.status != StatusLoja.cancelada:
        raise conflito('Só uma loja cancelada pode ser excluída. Cancele a loja antes.')
    excluir(ctx.db, loja)


@router.post(
    '/{loja_id}/acesso',
    status_code=status.HTTP_201_CREATED,
    summary='Acessar loja: sessão de 1 hora no painel como o Administrador da loja (sem corpo)',
)
def acessar(loja_id: UUID, request: Request, ctx: ContextoSuperadminDep) -> AcessoLoja:
    loja = buscar_loja(ctx.db, loja_id)  # excluída = 404; suspensa e cancelada podem (PLA-19)
    acesso = abrir_acesso_suporte(ctx.db, loja, ctx.superadmin.id, ip_da_requisicao(request))
    return AcessoLoja(
        token=acesso.token,
        expira_em=acesso.expira_em.astimezone(fuso(loja.fuso_horario)),
        slug=loja.slug,
        funcionario_nome=acesso.funcionario.nome,
    )


# --- Módulos -------------------------------------------------------------------------------------


def _modulos(ctx: ContextoSuperadmin, loja: Loja) -> list[ModuloLoja]:
    agora = datetime.now(UTC)
    zona = fuso(loja.fuso_horario)
    linhas = ctx.db.execute(
        select(Funcionalidade, LojaFuncionalidade)
        .outerjoin(
            LojaFuncionalidade,
            (LojaFuncionalidade.funcionalidade_id == Funcionalidade.id)
            & (LojaFuncionalidade.loja_id == loja.id)
            & LojaFuncionalidade.excluido_em.is_(None),
        )
        .order_by(Funcionalidade.opcional, Funcionalidade.nome)
    ).all()
    autores = nomes_superadmins(ctx.db, (lf.atualizado_por for _, lf in linhas if lf is not None))
    saida = []
    for f, lf in linhas:
        if not f.opcional:
            habilitado, ativo = True, f.ativo
        else:
            habilitado = bool(lf and lf.habilitado)
            ativo = f.ativo and habilitado and (lf.expira_em is None or lf.expira_em > agora)
        saida.append(
            ModuloLoja(
                codigo=f.codigo,
                nome=f.nome,
                descricao=f.descricao,
                opcional=f.opcional,
                habilitado=habilitado,
                ativo=ativo,
                observacao=lf.observacao if lf else None,
                expira_em=lf.expira_em.astimezone(zona) if lf and lf.expira_em else None,
                atualizado_em=_no_fuso(lf.atualizado_em, zona) if lf else None,
                atualizado_por_nome=autores.get(lf.atualizado_por) if lf and lf.atualizado_por else None,
            )
        )
    return saida


@router.get('/{loja_id}/modulos', summary='Módulos da loja (base e opcionais)')
def listar_modulos(loja_id: UUID, ctx: ContextoSuperadminDep) -> list[ModuloLoja]:
    return _modulos(ctx, buscar_loja(ctx.db, loja_id))


@router.patch('/{loja_id}/modulos/{codigo}', summary='Ligar/desligar um módulo opcional, observação e prazo')
def definir_modulo(
    loja_id: UUID, codigo: str, dados: ModuloEntrada, ctx: ContextoSuperadminDep
) -> ModuloLoja:
    db = ctx.db
    loja = buscar_loja(db, loja_id)
    funcionalidade = db.scalar(select(Funcionalidade).where(Funcionalidade.codigo == codigo))
    if funcionalidade is None:
        raise nao_encontrado('Módulo não encontrado.')
    if not funcionalidade.opcional:
        raise invalido('Este módulo é base e fica sempre ativo.')
    registro = db.scalar(
        select(LojaFuncionalidade)
        .where(
            LojaFuncionalidade.loja_id == loja.id,
            LojaFuncionalidade.funcionalidade_id == funcionalidade.id,
        )
        .execution_options(incluir_excluidos=True)
    )
    if registro is None:
        registro = LojaFuncionalidade(loja_id=loja.id, funcionalidade_id=funcionalidade.id, habilitado=False)
        db.add(registro)
    elif registro.excluido_em is not None:
        registro.excluido_em = None  # religar: restaura a linha existente
    enviados = dados.model_fields_set
    if 'habilitado' in enviados:
        if dados.habilitado is None:
            raise invalido('Informe se o módulo fica ligado ou desligado.')
        registro.habilitado = dados.habilitado
    if 'observacao' in enviados:
        registro.observacao = dados.observacao
    if 'expira_em' in enviados:
        registro.expira_em = no_fuso(dados.expira_em, fuso(loja.fuso_horario)) if dados.expira_em else None
    db.flush()
    return next(m for m in _modulos(ctx, loja) if m.codigo == codigo)


# --- Funcionários pelo suporte -------------------------------------------------------------------


def _funcionarios(
    ctx: ContextoSuperadmin, loja_id: UUID, funcionarios: list[Funcionario]
) -> list[FuncionarioSuporte]:
    perfis = {
        p.id: p
        for p in ctx.db.scalars(
            select(Perfil)
            .where(Perfil.loja_id == loja_id, Perfil.id.in_({f.perfil_id for f in funcionarios}))
            .execution_options(incluir_excluidos=True)
        )
    }
    zona = fuso(
        ctx.db.scalar(
            select(Loja.fuso_horario).where(Loja.id == loja_id).execution_options(incluir_excluidos=True)
        )
        or 'America/Sao_Paulo'
    )
    saida = []
    for f in funcionarios:
        item = FuncionarioSuporte.model_validate(f)
        item.criado_em = _no_fuso(item.criado_em, zona)
        item.atualizado_em = _no_fuso(item.atualizado_em, zona)
        item.ultimo_login_em = _no_fuso(item.ultimo_login_em, zona)
        perfil = perfis.get(f.perfil_id)
        item.perfil_nome = perfil.nome if perfil else None
        item.perfil_acesso_total = bool(perfil and perfil.acesso_total)
        if f.criado_por_superadmin:
            item.criado_por = 'superadmin'
        elif f.criado_por_funcionario:
            item.criado_por = 'loja'
        saida.append(item)
    return saida


def _perfil(ctx: ContextoSuperadmin, loja_id: UUID, perfil_id: UUID) -> Perfil:
    perfil = ctx.db.scalar(select(Perfil).where(Perfil.id == perfil_id, Perfil.loja_id == loja_id))
    if perfil is None:
        raise invalido('Perfil não encontrado.')
    return perfil


@router.get('/{loja_id}/perfis', summary='Perfis da loja (para escolher o perfil do funcionário)')
def listar_perfis(loja_id: UUID, ctx: ContextoSuperadminDep) -> list[PerfilOpcao]:
    loja = buscar_loja(ctx.db, loja_id)
    perfis = ctx.db.scalars(
        select(Perfil)
        .where(Perfil.loja_id == loja.id)
        .order_by(Perfil.acesso_total.desc(), Perfil.padrao.desc(), Perfil.nome)
    )
    return [PerfilOpcao.model_validate(p) for p in perfis]


@router.get('/{loja_id}/funcionarios', summary='Funcionários da loja (ativos e inativos)')
def listar_funcionarios(loja_id: UUID, ctx: ContextoSuperadminDep) -> list[FuncionarioSuporte]:
    loja = buscar_loja(ctx.db, loja_id)
    funcionarios = list(
        ctx.db.scalars(
            select(Funcionario)
            .where(Funcionario.loja_id == loja.id)
            .order_by(Funcionario.nome, Funcionario.id)
        )
    )
    return _funcionarios(ctx, loja.id, funcionarios)


@router.post(
    '/{loja_id}/funcionarios',
    status_code=status.HTTP_201_CREATED,
    summary='Criar funcionário (qualquer perfil, inclusive Administrador)',
)
def criar_funcionario(
    loja_id: UUID, dados: FuncionarioSuporteCriacao, ctx: ContextoSuperadminDep
) -> FuncionarioSuporteCriado:
    loja = buscar_loja(ctx.db, loja_id)
    _perfil(ctx, loja.id, dados.perfil_id)
    senha = dados.senha or gerar_senha_provisoria()
    funcionario = Funcionario(
        loja_id=loja.id, senha_hash=gerar_hash(senha), **dados.model_dump(exclude={'senha'})
    )
    ctx.db.add(funcionario)
    ctx.db.flush()
    return FuncionarioSuporteCriado(
        **_funcionarios(ctx, loja.id, [funcionario])[0].model_dump(),
        senha_provisoria=None if dados.senha else senha,
    )


@router.put('/{loja_id}/funcionarios/{funcionario_id}', summary='Editar funcionário (inclui inativar)')
def editar_funcionario(
    loja_id: UUID, funcionario_id: UUID, dados: FuncionarioSuporteEdicao, ctx: ContextoSuperadminDep
) -> FuncionarioSuporte:
    loja = buscar_loja(ctx.db, loja_id)
    funcionario = buscar(ctx.db, Funcionario, loja.id, funcionario_id, MSG_FUNC_404)
    novo_perfil = _perfil(ctx, loja.id, dados.perfil_id)
    perfil_atual = ctx.db.scalar(
        select(Perfil).where(Perfil.id == funcionario.perfil_id, Perfil.loja_id == loja.id)
    )
    era_admin = bool(perfil_atual and perfil_atual.acesso_total)
    if deixa_loja_sem_admin(
        ctx.db, loja.id, funcionario, era_admin, novo_perfil.acesso_total and dados.ativo
    ):
        raise conflito(MSG_ULTIMO_ADMIN)
    for campo, valor in dados.model_dump().items():
        if getattr(funcionario, campo) != valor:
            setattr(funcionario, campo, valor)
    ctx.db.flush()
    return _funcionarios(ctx, loja.id, [funcionario])[0]


@router.post(
    '/{loja_id}/funcionarios/{funcionario_id}/redefinir-senha',
    summary='Redefinir a senha do funcionário (informada ou provisória gerada)',
)
def redefinir_senha(
    loja_id: UUID, funcionario_id: UUID, dados: RedefinirSenha, ctx: ContextoSuperadminDep
) -> SenhaRedefinida:
    loja = buscar_loja(ctx.db, loja_id)
    funcionario = buscar(ctx.db, Funcionario, loja.id, funcionario_id, MSG_FUNC_404)
    senha = dados.senha or gerar_senha_provisoria()
    # A troca do hash entra na auditoria como "alterar" (campo senha_hash, sem o valor), com o superadmin
    funcionario.senha_hash = gerar_hash(senha)
    ctx.db.flush()
    return SenhaRedefinida(
        mensagem='Senha redefinida. Repasse a nova senha ao funcionário.',
        senha_provisoria=None if dados.senha else senha,
    )
