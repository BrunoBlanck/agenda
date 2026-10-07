"""Páginas HTML do back-end, fora de /api (GER-29, SIT-12).

Mapa de URLs (o nginx de produção e o servidor de dev do front seguem o mesmo mapa):

- ``/`` e ``/painel[/...]``: 404 (o painel é aberto pelo endereço da loja, ``/<slug>/painel``, que o
  nginx entrega ao front e nunca chega aqui);
- ``/static/site/<arquivo>``: CSS e JS do site do consumidor (lista fechada de arquivos);
- ``/<slug>`` e ``/<slug>/agendar[/...]``: site do consumidor (``app/routers/site/paginas.py``);
- ``/<slug>/conta[/...]``: conta do cliente no site (``app/routers/site/conta.py``; cancelar e remarcar em
  ``app/routers/site/conta_agendamentos.py``);
- ``/<slug>/``: 308 para ``/<slug>``;
- qualquer outro ``/<slug>/<resto>``: 404.

Este router é registrado **depois** dos routers /api e das rotas de documentação. O primeiro trecho
nunca é ``api`` (conversor ``segmento``): /api/... que não existe continua com o 404 em JSON da API.
"""

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.routers.html import (
    CABECALHOS,
    CSP_SIMPLES,
    MSG_LOJA_404,
    TIPOS_ESTATICOS,
    cabecalhos,
    estatico,
    nao_encontrada,
)
from app.routers.site import conta, conta_agendamentos
from app.routers.site import paginas as site
from app.services.slugs import endereco_de_loja

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)
METODOS = ['GET', 'HEAD']  # HEAD: o servidor (uvicorn) devolve só os cabeçalhos

DICA_PAINEL = 'Acesse o painel pelo endereço da sua loja, por exemplo /nome-da-loja/painel.'


@router.api_route('/', methods=METODOS)
def inicio() -> HTMLResponse:
    return nao_encontrada()


@router.api_route('/painel', methods=METODOS)
@router.api_route('/painel/{resto:path}', methods=METODOS)
def painel_sem_loja() -> HTMLResponse:
    return nao_encontrada(dica=DICA_PAINEL)


# --- Arquivos do site do consumidor ----------------------------------------------------------------

CACHE_LONGO = 'public, max-age=31536000, immutable'


@router.api_route('/static/site/{nome}', methods=METODOS, response_model=None)
def arquivo_do_site(nome: str, request: Request) -> Response:
    tipo = TIPOS_ESTATICOS.get(nome)
    if tipo is None:  # nunca monta caminho com o texto da URL
        return nao_encontrada()
    arquivo = estatico(nome)
    versionado = request.query_params.get('v') == arquivo.versao
    return Response(
        arquivo.conteudo,
        media_type=tipo,
        headers={**CABECALHOS, 'Cache-Control': CACHE_LONGO if versionado else 'no-cache'},
    )


# --- Site do consumidor e o resto ------------------------------------------------------------------

router.include_router(site.router)
router.include_router(conta.router)  # /<slug>/conta/... (conta do cliente, SIT-16 a SIT-21)
router.include_router(conta_agendamentos.router)  # /<slug>/conta/agendamentos/<id>/... (SIT-23, SIT-24)


@router.api_route('/{slug:segmento}/', methods=METODOS, response_model=None)
def loja_com_barra(slug: str) -> Response:
    if not endereco_de_loja(slug):
        return nao_encontrada(MSG_LOJA_404)
    return RedirectResponse(
        f'/{slug}', status_code=status.HTTP_308_PERMANENT_REDIRECT, headers=cabecalhos(CSP_SIMPLES)
    )


@router.api_route('/{slug:segmento}/{resto:path}', methods=METODOS)
def outra_pagina() -> HTMLResponse:
    return nao_encontrada()
