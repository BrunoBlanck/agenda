"""Sino do painel (/api/loja/notificacoes, NOT-06).

As notificações do painel são **pessoais**: qualquer funcionário logado lê e marca só as suas
(``tipo = loja`` com o seu ``funcionario_id``), sem recurso de acesso (``ContextoLojaDep``: loja ativa,
funcionário ativo e o contexto da transação). Nenhum módulo desliga o sino.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencias import ContextoLojaDep
from app.schemas.comum import PAGINA_MAX, Erro, Paginacao
from app.schemas.notificacoes import (
    NOTIFICACOES_POR_PAGINA_MAX,
    ListaNotificacoes,
    NotificacaoSaida,
    ResumoNotificacoes,
    VisualizarEntrada,
    VisualizarSaida,
)
from app.services.comum import fuso
from app.services.notificacoes import (
    VISUALIZADA,
    listar_do_funcionario,
    marcar_do_funcionario,
    nao_visualizadas_do_funcionario,
)

router = APIRouter(prefix='/notificacoes', tags=['Loja: notificações'], responses={403: {'model': Erro}})


def paginacao_do_sino(
    pagina: Annotated[int, Query(ge=1, le=PAGINA_MAX, description='Página, começando em 1')] = 1,
    por_pagina: Annotated[
        int, Query(ge=1, le=NOTIFICACOES_POR_PAGINA_MAX, description='Itens por página (máx. 50)')
    ] = 20,
) -> Paginacao:
    return Paginacao(pagina=pagina, por_pagina=por_pagina)


@router.get('', summary='Minhas notificações (mais novas primeiro, paginadas)')
def listar(ctx: ContextoLojaDep, pag: Annotated[Paginacao, Depends(paginacao_do_sino)]) -> ListaNotificacoes:
    db, loja_id, eu = ctx.db, ctx.loja_id, ctx.funcionario.id
    zona = fuso(ctx.loja.fuso_horario)
    itens, total = listar_do_funcionario(db, loja_id, eu, pag)
    return ListaNotificacoes(
        itens=[
            NotificacaoSaida(
                id=item.notificacao.id,
                evento=item.notificacao.evento,
                titulo=item.notificacao.titulo,
                mensagem=item.notificacao.mensagem,
                agendamento_id=item.agendamento_id,
                inicio_agendamento=item.inicio_agendamento.astimezone(zona)
                if item.inicio_agendamento
                else None,
                visualizada=item.notificacao.status_site == VISUALIZADA,
                visualizada_em=(
                    item.notificacao.visualizada_em.astimezone(zona)
                    if item.notificacao.visualizada_em
                    else None
                ),
                status_email=item.notificacao.status_email,
                status_whatsapp=item.notificacao.status_whatsapp,
                criado_em=item.notificacao.criado_em.astimezone(zona),
            )
            for item in itens
        ],
        total=total,
        pagina=pag.pagina,
        por_pagina=pag.por_pagina,
        nao_visualizadas=nao_visualizadas_do_funcionario(db, loja_id, eu),
    )


@router.get('/resumo', summary='Quantas notificações minhas ainda não foram visualizadas')
def resumo(ctx: ContextoLojaDep) -> ResumoNotificacoes:
    return ResumoNotificacoes(
        nao_visualizadas=nao_visualizadas_do_funcionario(ctx.db, ctx.loja_id, ctx.funcionario.id)
    )


@router.post(
    '/visualizar',
    responses={422: {'model': Erro}},
    summary='Marcar como visualizadas as notificações mostradas (ids de outro usuário são ignorados)',
)
def visualizar(dados: VisualizarEntrada, ctx: ContextoLojaDep) -> VisualizarSaida:
    """No acesso de suporte (SUPERADMIN acessando a loja como o Administrador) nada é marcado: o sino do
    Administrador continua como estava (``marcadas: 0``)."""
    db, loja_id, eu = ctx.db, ctx.loja_id, ctx.funcionario.id
    marcadas = 0 if ctx.token.suporte else marcar_do_funcionario(db, loja_id, eu, dados.ids)
    return VisualizarSaida(
        marcadas=marcadas, nao_visualizadas=nao_visualizadas_do_funcionario(db, loja_id, eu)
    )
