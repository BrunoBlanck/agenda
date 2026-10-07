"""Sessão do cliente no site por cookie (SIT-20) e o endereço de retorno (``voltar``) das páginas da conta.

Cookie ``HttpOnly``, ``SameSite=Lax``, ``Path=/<slug>`` (não vai para outra loja nem para a API) e
``Secure`` fora de ``AMBIENTE=desenvolvimento``. O valor é o token ``cliente`` de ``app/auth/tokens.py``;
cada página confere loja, conta e versão (``app/services/conta_cliente.py::sessao_valida``).
"""

import re
from dataclasses import dataclass

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.auth.tokens import TokenInvalido, criar_token_cliente, ler_token_cliente
from app.config import get_settings
from app.models import ClienteConta, Loja
from app.services.conta_cliente import SessaoCliente, sessao_valida

COOKIE_SESSAO = 'sessao_cliente'
TAMANHO_MAXIMO_VOLTAR = 500

_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
# Páginas do site para onde se pode voltar depois de entrar (lista fechada; nunca as da própria conta de
# entrada/criação, nem outro slug, esquema ou "//")
_PAGINAS = (
    rf'(?:/agendar(?:/dados|/pronto)?'
    rf'|/conta(?:/avisos|/agendamentos/{_UUID}/(?:cancelar|remarcar(?:/confirmar)?))?)?'
)
_CONSULTA = r'(?:\?[A-Za-z0-9_.~%=&+-]*)?'


@dataclass(frozen=True)
class SessaoLida:
    sessao: SessaoCliente | None
    havia_cookie: bool  # veio um cookie que não vale mais (vencido, trocado, removido, de outra loja)

    @property
    def expirada(self) -> bool:
        return self.sessao is None and self.havia_cookie


def ler_sessao(request: Request, db: Session, loja: Loja) -> SessaoLida:
    token = request.cookies.get(COOKIE_SESSAO)
    if not token:
        return SessaoLida(None, False)
    try:
        dados = ler_token_cliente(token)
    except TokenInvalido:
        return SessaoLida(None, True)
    return SessaoLida(sessao_valida(db, loja.id, dados), True)


def gravar_sessao(resposta: Response, slug: str, conta: ClienteConta) -> Response:
    token, _ = criar_token_cliente(conta.id, conta.loja_id, conta.sessao_versao)
    resposta.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=get_settings().site_sessao_dias * 24 * 3600,
        path=f'/{slug}',
        secure=get_settings().ambiente != 'desenvolvimento',
        httponly=True,
        samesite='lax',
    )
    return resposta


def apagar_sessao(resposta: Response, slug: str) -> Response:
    resposta.delete_cookie(
        COOKIE_SESSAO,
        path=f'/{slug}',
        secure=get_settings().ambiente != 'desenvolvimento',
        httponly=True,
        samesite='lax',
    )
    return resposta


def conta_padrao(slug: str) -> str:
    return f'/{slug}/conta'


def validar_voltar(slug: str, texto: str | None) -> str:
    """``texto`` se for o caminho de uma página do site desta loja (regex fechada); senão ``/<slug>/conta``.

    Protege contra redirecionamento aberto: só caminho relativo começando com ``/<slug>``, sem ``//``,
    esquema, barra invertida ou outro slug.
    """
    valido = (
        texto is not None
        and len(texto) <= TAMANHO_MAXIMO_VOLTAR
        and re.fullmatch(rf'/{re.escape(slug)}{_PAGINAS}{_CONSULTA}', texto) is not None
    )
    return texto if valido and texto else conta_padrao(slug)
