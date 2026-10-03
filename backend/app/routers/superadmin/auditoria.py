"""Auditoria (/api/superadmin/auditoria): o que mudou e quem fez, sempre uma loja por vez (estrutura.md, 1.9).

A mesma consulta atende a aba Histórico do detalhe da loja.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth.dependencias import ContextoSuperadminDep
from app.models import Auditoria
from app.schemas.comum import Data, Erro, Pagina, Paginacao, paginacao
from app.schemas.superadmin import AuditoriaItem, Periodo, Quem, TabelasAuditoria
from app.services.auditoria import (
    TABELAS_LOJA,
    TABELAS_PLATAFORMA,
    consulta_base,
    descrever,
    descrever_quem,
    filtro_quem,
    fuso_da_area,
    interpretar_loja,
    intervalo_do_periodo,
)
from app.services.comum import paginar

router = APIRouter(prefix='/auditoria', tags=['Superadmin: auditoria'], responses={422: {'model': Erro}})

LojaParam = Annotated[
    str, Query(max_length=40, description='Id da loja, ou "plataforma" para planos e usuários admin')
]
TabelaParam = Annotated[str | None, Query(max_length=60, description='Ex.: agendamentos (vazio = todas)')]
PeriodoParam = Annotated[
    Periodo, Query(description='hoje, 7d, 30d, 90d, ano ou intervalo (com inicio e fim)')
]


@router.get('/tabelas', summary='Tabelas que podem ser consultadas, por área')
def tabelas(_: ContextoSuperadminDep) -> TabelasAuditoria:
    return TabelasAuditoria(loja=TABELAS_LOJA, plataforma=TABELAS_PLATAFORMA)


@router.get('', summary='Alterações de uma loja (ou da plataforma), paginadas, mais recentes primeiro')
def listar(
    ctx: ContextoSuperadminDep,
    pag: Annotated[Paginacao, Depends(paginacao)],
    loja: LojaParam,
    tabela: TabelaParam = None,
    periodo: PeriodoParam = '30d',
    inicio: Data | None = None,
    fim: Data | None = None,
    quem: Annotated[str | None, Query(max_length=60, description='f:<id>, s:<id>, site ou sistema')] = None,
) -> Pagina[AuditoriaItem]:
    db = ctx.db
    loja_id = interpretar_loja(loja)
    zona = fuso_da_area(db, loja_id)
    de, ate = intervalo_do_periodo(periodo, inicio, fim, zona)
    consulta = consulta_base(loja_id, tabela, de, ate)
    if quem:
        consulta = consulta.where(filtro_quem(quem))
    registros, total = paginar(db, consulta.order_by(Auditoria.criado_em.desc(), Auditoria.id.desc()), pag)
    return Pagina(
        itens=descrever(db, loja_id, registros, zona),
        total=total,
        pagina=pag.pagina,
        por_pagina=pag.por_pagina,
    )


@router.get('/pessoas', summary='Quem fez alterações no período (para o filtro "Todas as pessoas")')
def pessoas(
    ctx: ContextoSuperadminDep,
    loja: LojaParam,
    tabela: TabelaParam = None,
    periodo: PeriodoParam = '30d',
    inicio: Data | None = None,
    fim: Data | None = None,
) -> list[Quem]:
    db = ctx.db
    loja_id = interpretar_loja(loja)
    zona = fuso_da_area(db, loja_id)
    de, ate = intervalo_do_periodo(periodo, inicio, fim, zona)
    base = consulta_base(loja_id, tabela, de, ate).subquery()
    linhas = db.execute(select(base.c.funcionario_id, base.c.superadmin_id, base.c.origem).distinct()).all()
    quem = descrever_quem(db, loja_id, [tuple(linha) for linha in linhas])
    return sorted(quem.values(), key=lambda q: (q.tipo != 'superadmin', q.nome.lower()))
