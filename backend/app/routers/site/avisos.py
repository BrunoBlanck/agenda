"""Avisos do cliente no site (SIT-25, NOT-06): ``GET /<slug>/conta/avisos?pagina=``.

Exige a sessão (sem ela, 303 para entrar voltando aqui). Lista as notificações dos clientes do telefone da
conta (20 por página, mais novas primeiro), destaca as que ainda não tinham sido vistas **nesta abertura**
e, depois de montar a lista, marca as da página como visualizadas. Página estranha ou fora do intervalo:
a primeira (nunca 500). Sem JavaScript, ``noindex``, sem link de local e sem motivo de cancelamento (os
textos já são gravados assim). DIR-003: nada leva ao painel.
"""

import re
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.auth.dependencias import DbDep
from app.routers.site.conta import exigir_sessao
from app.routers.site.paginas import METODOS, abrir, montar_url
from app.services.avisos_conta import abrir_avisos
from app.services.conta_cliente import PAGINA_MAXIMA
from app.services.notificacoes import hora

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)


def _ler_pagina(texto: str | None) -> int:
    """Só dígitos ASCII; o resto (ou fora do limite) é a primeira página."""
    if not texto or re.fullmatch(r'[0-9]{1,6}', texto) is None:
        return 1
    return int(texto) if 1 <= int(texto) <= PAGINA_MAXIMA else 1


@router.api_route('/{slug:segmento}/conta/avisos', methods=METODOS)
def avisos(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    sessao = exigir_sessao(site)
    dados = abrir_avisos(
        db,
        site.ctx.loja.id,
        sessao.conta.telefone_digitos,
        _ler_pagina(request.query_params.get('pagina')),
        marcar=request.method != 'HEAD',  # HEAD (pré-busca, verificador de links) não conta como abrir
    )
    base = f'/{site.slug}/conta/avisos'
    zona = site.ctx.zona

    def quando(momento: datetime) -> str:
        local = momento.astimezone(zona)
        return f'{local:%d/%m/%Y} às {hora(local)}'

    return site.renderizar(
        'site/avisos.html',
        None,
        avisos=[
            {
                'titulo': aviso.titulo,
                'mensagem': aviso.mensagem,
                'quando': quando(aviso.criado_em),
                'momento': aviso.criado_em.astimezone(zona).isoformat(timespec='minutes'),
                'novo': aviso.novo,
            }
            for aviso in dados.avisos
        ],
        novos=sum(1 for aviso in dados.avisos if aviso.novo),
        pagina=dados.pagina,
        paginas=dados.paginas,
        anteriores=montar_url(base, pagina=dados.pagina + 1) if dados.pagina < dados.paginas else None,
        mais_novos=montar_url(base, pagina=dados.pagina - 1 if dados.pagina > 2 else None)
        if dados.pagina > 1
        else None,
        conta=f'/{site.slug}/conta',
    )
