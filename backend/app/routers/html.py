"""Ferramentas das páginas HTML do back-end (GER-29): Jinja2, cabeçalhos de segurança e respostas prontas.

Usadas pelas páginas gerais (``app/routers/paginas.py``: /, /painel, 404) e pelo site do consumidor
(``app/routers/site/paginas.py``). Jinja2 com autoescape: todo texto vindo do banco sai escapado.

Duas políticas de conteúdo (CSP), cada página com o mínimo de que precisa:
- ``CSP_SIMPLES`` (páginas de erro): sem script, sem formulário, estilo embutido;
- ``CSP_SITE`` (fluxo de agendamento): estilo e script só da própria origem (``/static/site/...``),
  formulários só para a própria origem, imagens (logo) da própria origem.
"""

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from starlette.convertors import StringConvertor, register_url_convertor

from app.limites import MSG_MUITAS_REQUISICOES

PASTA_DO_APP = Path(__file__).resolve().parent.parent


class SegmentoDePagina(StringConvertor):
    """Primeiro trecho da URL (``{x:segmento}``), menos ``api``: páginas HTML nunca respondem por /api/..."""

    regex = r'(?!api(?:/|$))[^/]+'


register_url_convertor('segmento', SegmentoDePagina())

ambiente = Environment(
    loader=FileSystemLoader(PASTA_DO_APP / 'templates'),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

CSP_SIMPLES = (
    "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
CSP_SITE = (
    "default-src 'none'; img-src 'self'; style-src 'self'; script-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

CABECALHOS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY',
    'Cache-Control': 'no-store',
}

MSG_PAGINA_404 = 'Página não encontrada'
MSG_LOJA_404 = 'Loja não encontrada'


def cabecalhos(csp: str, extras: dict[str, str] | None = None) -> dict[str, str]:
    return {'Content-Security-Policy': csp, **CABECALHOS, **(extras or {})}


def pagina(
    modelo: str,
    codigo: int = status.HTTP_200_OK,
    *,
    csp: str = CSP_SIMPLES,
    extras: dict[str, str] | None = None,
    **contexto: object,
) -> HTMLResponse:
    conteudo = ambiente.get_template(modelo).render(**contexto)
    return HTMLResponse(conteudo, status_code=codigo, headers=cabecalhos(csp, extras))


def nao_encontrada(titulo: str = MSG_PAGINA_404, dica: str | None = None) -> HTMLResponse:
    return pagina('erro.html', status.HTTP_404_NOT_FOUND, titulo=titulo, dica=dica)


def muitas_requisicoes(exc: HTTPException) -> HTMLResponse:
    return pagina(
        'erro.html',
        status.HTTP_429_TOO_MANY_REQUESTS,
        extras=exc.headers,
        titulo='Muitas requisições',
        dica=MSG_MUITAS_REQUISICOES,
    )


def redirecionar(url: str, codigo: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url, status_code=codigo, headers=cabecalhos(CSP_SIMPLES))


class RespostaPronta(Exception):
    """Interrompe a página com uma resposta pronta (404, 429, redirecionamento para o passo certo).

    A transação da requisição é desfeita (nada foi gravado até aí) e a resposta sai como está.
    """

    def __init__(self, resposta: Response) -> None:
        super().__init__(resposta.status_code)
        self.resposta = resposta


async def responder(_: Request, exc: RespostaPronta) -> Response:
    """Tratador registrado no app (app/main.py) para ``RespostaPronta``."""
    return exc.resposta


# --- Arquivos do site do consumidor (CSS e JS) ----------------------------------------------------

PASTA_ESTATICA = PASTA_DO_APP / 'static' / 'site'
TIPOS_ESTATICOS = {'site.css': 'text/css; charset=utf-8', 'site.js': 'text/javascript; charset=utf-8'}


@dataclass(frozen=True)
class Estatico:
    conteudo: bytes
    versao: str


@lru_cache(maxsize=8)
def _ler_estatico(nome: str, _modificado_em: int) -> Estatico:
    conteudo = (PASTA_ESTATICA / nome).read_bytes()
    return Estatico(conteudo=conteudo, versao=hashlib.sha256(conteudo).hexdigest()[:12])


def estatico(nome: str) -> Estatico:
    """Arquivo da lista fechada (``TIPOS_ESTATICOS``), relido quando muda (data de modificação)."""
    return _ler_estatico(nome, (PASTA_ESTATICA / nome).stat().st_mtime_ns)


def url_estatica(nome: str) -> str:
    """Endereço com a versão (resumo do conteúdo): o navegador guarda por um ano e troca quando muda."""
    return f'/static/site/{nome}?v={estatico(nome).versao}'
