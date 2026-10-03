"""Páginas HTML do back-end, fora de /api (GER-29, SIT-11).

Mapa de URLs (o nginx de produção e o servidor de dev do front seguem o mesmo mapa):

- ``/`` e ``/painel[/...]``: 404 (o painel é aberto pelo endereço da loja, ``/<slug>/painel``, que o
  nginx entrega ao front e nunca chega aqui);
- ``/<slug>``: página provisória da loja (SIT-11), só com os dados públicos de ``LojaPublica`` e a
  mesma visibilidade do site (SIT-01): inexistente, excluída, suspensa ou cancelada = 404;
- ``/<slug>/``: 308 para ``/<slug>``;
- ``/<slug>/<resto>``: 404 (futuras páginas do site).

Este router é registrado **depois** dos routers /api e das rotas de documentação. O primeiro trecho
nunca é ``api`` (conversor ``segmento``): /api/... que não existe continua com o 404 em JSON da API.
HTML com Jinja2 e autoescape, sem JavaScript, com CSP restritiva.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from starlette.convertors import StringConvertor, register_url_convertor

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.limites import MSG_MUITAS_REQUISICOES, limite_site
from app.schemas.site import LojaPublica
from app.services.acesso import modulos_da_loja
from app.services.site import carregar_loja_publica, dados_publicos
from app.services.slugs import endereco_de_loja


class SegmentoDePagina(StringConvertor):
    """Primeiro trecho da URL, menos ``api``: as páginas HTML nunca respondem por /api/..."""

    regex = r'(?!api(?:/|$))[^/]+'


register_url_convertor('segmento', SegmentoDePagina())

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)
METODOS = ['GET', 'HEAD']  # HEAD: o servidor (uvicorn) devolve só os cabeçalhos

_ambiente = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / 'templates'),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

CABECALHOS = {
    'Content-Security-Policy': (
        "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY',
    'Cache-Control': 'no-cache',
}

MSG_PAGINA_404 = 'Página não encontrada'
MSG_LOJA_404 = 'Loja não encontrada'
DICA_PAINEL = 'Acesse o painel pelo endereço da sua loja, por exemplo /nome-da-loja/painel.'
TIPOS = {'clinica': 'Clínica', 'barbearia': 'Barbearia', 'escola': 'Escola'}


def _html(
    modelo: str, codigo: int, cabecalhos: dict[str, str] | None = None, **contexto: object
) -> HTMLResponse:
    conteudo = _ambiente.get_template(modelo).render(**contexto)
    return HTMLResponse(conteudo, status_code=codigo, headers={**CABECALHOS, **(cabecalhos or {})})


def _nao_encontrada(titulo: str = MSG_PAGINA_404, dica: str | None = None) -> HTMLResponse:
    return _html('erro.html', status.HTTP_404_NOT_FOUND, titulo=titulo, dica=dica)


def _endereco(loja: LojaPublica) -> list[str]:
    """Endereço em até duas linhas, só com as partes preenchidas."""
    rua = ', '.join(p for p in (loja.logradouro, loja.numero) if p)
    if rua and loja.complemento:
        rua = f'{rua} - {loja.complemento}'
    cidade = '/'.join(p for p in (loja.cidade, loja.uf) if p)
    bairro = ' · '.join(p for p in (loja.bairro, cidade) if p)
    return [linha for linha in (rua, bairro) if linha]


def _pagina_da_loja(publica: LojaPublica) -> HTMLResponse:
    telefone = re.sub(r'\D', '', publica.telefone or '')
    return _html(
        'loja.html',
        status.HTTP_200_OK,
        loja=publica,
        tipo=TIPOS.get(publica.tipo, ''),
        telefone_link=f'tel:{telefone}' if telefone else None,
        endereco=_endereco(publica),
        indexar=True,
    )


@router.api_route('/', methods=METODOS)
def inicio() -> HTMLResponse:
    return _nao_encontrada()


@router.api_route('/painel', methods=METODOS)
@router.api_route('/painel/{resto:path}', methods=METODOS)
def painel_sem_loja() -> HTMLResponse:
    return _nao_encontrada(dica=DICA_PAINEL)


@router.api_route('/{slug:segmento}', methods=METODOS)
def loja(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    if not endereco_de_loja(slug):  # sem consulta ao banco (nem contagem do limite)
        return _nao_encontrada(MSG_LOJA_404)
    try:
        limite_site(request)  # mesmo limite por IP da API do site
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        return _html(
            'erro.html',
            status.HTTP_429_TOO_MANY_REQUESTS,
            exc.headers,
            titulo='Muitas requisições',
            dica=MSG_MUITAS_REQUISICOES,
        )
    encontrada = carregar_loja_publica(db, slug, ip_da_requisicao(request))
    if encontrada is None:
        return _nao_encontrada(MSG_LOJA_404)
    publica = dados_publicos(db, encontrada, modulos_da_loja(db, encontrada.id))
    return _pagina_da_loja(publica)


@router.api_route('/{slug:segmento}/', methods=METODOS, response_model=None)
def loja_com_barra(slug: str) -> Response:
    if not endereco_de_loja(slug):
        return _nao_encontrada(MSG_LOJA_404)
    return RedirectResponse(f'/{slug}', status_code=status.HTTP_308_PERMANENT_REDIRECT, headers=CABECALHOS)


@router.api_route('/{slug:segmento}/{resto:path}', methods=METODOS)
def outra_pagina() -> HTMLResponse:
    return _nao_encontrada()  # futuras páginas do site
