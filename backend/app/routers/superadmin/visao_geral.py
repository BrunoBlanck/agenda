"""Visão geral da plataforma (/api/superadmin/visao-geral)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.auth.dependencias import ContextoSuperadminDep
from app.models import Auditoria, Funcionalidade, Funcionario, Loja, Plano
from app.models.enums import StatusLoja, TipoLoja
from app.schemas.superadmin import AcaoRecente, ModuloEmUso, VisaoGeral
from app.services.auditoria import nome_tabela
from app.services.plataforma import modulos_opcionais_por_loja, nomes_superadmins

router = APIRouter(tags=['Superadmin: visão geral'])


@router.get('/visao-geral', summary='Números da plataforma e últimas ações dos admins')
def visao_geral(
    ctx: ContextoSuperadminDep,
    acoes: Annotated[int, Query(ge=1, le=50, description='Quantas ações recentes trazer')] = 6,
) -> VisaoGeral:
    db = ctx.db
    lojas = db.execute(select(Loja.id, Loja.tipo, Loja.status, Loja.plano_id)).all()
    ativas = [loja for loja in lojas if loja.status == StatusLoja.ativa]
    contagem = {s: sum(1 for loja in lojas if loja.status == s) for s in StatusLoja}

    por_tipo = {t: dict.fromkeys(StatusLoja, 0) for t in TipoLoja}
    for loja in lojas:
        por_tipo[loja.tipo][loja.status] += 1

    precos = dict(
        db.execute(select(Plano.id, Plano.preco_mensal).execution_options(incluir_excluidos=True)).all()
    )
    receita = sum((precos.get(loja.plano_id, Decimal(0)) for loja in ativas), Decimal(0))

    ids_ativas = [loja.id for loja in ativas]
    funcionarios = 0
    if ids_ativas:
        funcionarios = (
            db.scalar(
                select(func.count())
                .select_from(Funcionario)
                .where(
                    Funcionario.loja_id.in_(ids_ativas),
                    Funcionario.ativo,
                    Funcionario.excluido_em.is_(None),
                )
            )
            or 0
        )

    modulos = modulos_opcionais_por_loja(db, ids_ativas)
    opcionais = db.execute(
        select(Funcionalidade.codigo, Funcionalidade.nome)
        .where(Funcionalidade.opcional)
        .order_by(Funcionalidade.nome)
    ).all()
    em_uso = [
        ModuloEmUso(codigo=codigo, nome=nome, lojas=sum(1 for m in modulos.values() if m.get(codigo)))
        for codigo, nome in opcionais
    ]

    ultimas = list(
        db.scalars(
            select(Auditoria)
            .where(Auditoria.superadmin_id.is_not(None))
            .order_by(Auditoria.id.desc())
            .limit(acoes)
        )
    )
    admins = nomes_superadmins(db, (a.superadmin_id for a in ultimas))
    ids_lojas = {a.loja_id for a in ultimas if a.loja_id}
    nomes_lojas = {
        i: fantasia or nome
        for i, fantasia, nome in db.execute(
            select(Loja.id, Loja.nome_fantasia, Loja.nome)
            .where(Loja.id.in_(ids_lojas))
            .execution_options(incluir_excluidos=True)
        ).all()
    }

    return VisaoGeral(
        lojas_ativas=contagem[StatusLoja.ativa],
        lojas_suspensas=contagem[StatusLoja.suspensa],
        lojas_canceladas=contagem[StatusLoja.cancelada],
        funcionarios_ativos=funcionarios,
        receita_mensal=receita,
        lojas_por_tipo=por_tipo,
        modulos_em_uso=em_uso,
        ultimas_acoes=[
            AcaoRecente(
                id=a.id,
                criado_em=a.criado_em,
                tabela=a.tabela,
                tabela_nome=nome_tabela(a.tabela),
                operacao=a.operacao,
                superadmin_id=a.superadmin_id,
                superadmin_nome=admins.get(a.superadmin_id) if a.superadmin_id else None,
                loja_id=a.loja_id,
                loja_nome=nomes_lojas.get(a.loja_id) if a.loja_id else None,
            )
            for a in ultimas
        ],
    )
