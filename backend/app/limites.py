"""Proteção contra abuso: limite de requisições por IP e bloqueio progressivo de login (SEG-09).

Decisão provisória para ABE-23/SIT-10 (sem captcha por enquanto):

- **Por IP** (janela fixa): login da loja, do superadmin e do cliente no site, todas as rotas do site
  e, à parte, os pedidos de agendamento do site por IP em cada loja. Passou do limite: 429 com
  ``Retry-After``.
- **Entrar na conta do cliente no site** (``limite_login_site``): por IP, com os valores do login do painel
  mas num contador próprio (esgotar um não afeta o outro).
- **Códigos de confirmação do site** (SIT-17): pedidos por IP e um pedido por (telefone, IP) a cada N
  segundos (``limite_codigo_pedido``); códigos gerados de fato por telefone em cada loja
  (``limite_codigo_telefone``, conferido só quando não há código pendente); erros no mesmo código por IP
  (``TentativasDoCodigo``). Assim um terceiro não invalida nem esgota o código de quem já o tem.
- **Por conta + IP** no login: depois de N falhas seguidas com o mesmo e-mail **vindas do mesmo IP**,
  novas tentativas desse IP para essa conta recebem 429 por um tempo que dobra a cada nova falha
  (até um máximo). Outra origem não é afetada: quem só sabe o e-mail não tranca a conta do dono
  (que entra de outro IP), nem renova o bloqueio dele. Vale também para e-mail que não existe,
  então a resposta não revela se a conta existe. Acertar a senha zera as falhas daquele IP.
  Contra o ataque distribuído (muitos IPs na mesma conta) segue valendo o limite global por IP.

Os limites vêm da configuração (``LIMITE_*`` e ``LOGIN_*`` no .env, ver app/config.py).

O estado fica no PostgreSQL (schema ``limites``, migração 0003), então vale para todos os processos
e réplicas da API. Cada contador grava numa conexão própria, em autocommit: conta mesmo quando a
requisição falha e a transação dela é desfeita (senha errada, 404, 422). As chaves são HMAC do IP
ou do e-mail com o segredo do JWT: a tabela não guarda dado pessoal legível (SEG-17).

O IP é o mesmo da auditoria (``ip_da_requisicao``). Atrás de um proxy reverso, rode o uvicorn com
``--proxy-headers --forwarded-allow-ips=<ip do proxy>``; senão todos os clientes viram o IP do proxy.
"""

import hashlib
import hmac
import math
import secrets
from functools import lru_cache

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, Engine, create_engine, text
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.dependencias import ip_da_requisicao
from app.config import get_settings

MSG_MUITAS_REQUISICOES = 'Muitas requisições. Aguarde um pouco e tente novamente.'
SEM_IP = 'desconhecido'  # requisição sem IP válido: todas dividem o mesmo contador (conservador)
CONTAGEM_MAXIMA = 1_000_000_000  # o contador para de crescer aqui (integer no banco)

_CONTAR = text("""
    INSERT INTO limites.contadores AS c (chave, contagem, expira_em)
    VALUES (:chave, 1, now() + :janela * interval '1 second')
    ON CONFLICT (chave) DO UPDATE SET
      contagem = CASE WHEN c.expira_em <= now() THEN 1 ELSE least(c.contagem + 1, :maximo) END,
      expira_em = CASE WHEN c.expira_em <= now() THEN now() + :janela * interval '1 second'
                       ELSE c.expira_em END
    RETURNING contagem, ceil(extract(epoch FROM expira_em - now()))::integer
""")

_FALHA = text("""
    INSERT INTO limites.contadores AS c (chave, contagem, expira_em)
    VALUES (:chave, 1, now() + :janela * interval '1 second')
    ON CONFLICT (chave) DO UPDATE SET
      contagem = CASE WHEN c.expira_em <= now() THEN 1 ELSE least(c.contagem + 1, :maximo) END,
      expira_em = now() + :janela * interval '1 second'
    RETURNING contagem
""")

_BLOQUEAR = text("""
    UPDATE limites.contadores SET bloqueado_ate = now() + :segundos * interval '1 second'
     WHERE chave = :chave
""")

_BLOQUEIO = text("""
    SELECT ceil(extract(epoch FROM bloqueado_ate - now()))::integer
      FROM limites.contadores
     WHERE chave = :chave AND bloqueado_ate > now()
""")

_ZERAR = text('DELETE FROM limites.contadores WHERE chave = :chave')

_FAXINA = text("""
    DELETE FROM limites.contadores
     WHERE expira_em < now() AND (bloqueado_ate IS NULL OR bloqueado_ate < now())
""")


@lru_cache
def get_engine_limites() -> Engine:
    """Pool próprio e pequeno, em autocommit: não disputa conexões com as transações das requisições."""
    url = get_settings().database_url.get_secret_value()
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        isolation_level='AUTOCOMMIT',
        pool_size=2,
        max_overflow=8,
    )


def _chave(*partes: str) -> str:
    segredo = get_settings().jwt_secret.get_secret_value().encode()
    return hmac.new(segredo, '\x1f'.join(partes).encode(), hashlib.sha256).hexdigest()


def _ip(request: Request) -> str:
    return ip_da_requisicao(request) or SEM_IP


def muitas_requisicoes(segundos: int, mensagem: str = MSG_MUITAS_REQUISICOES) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, mensagem, headers={'Retry-After': str(max(1, segundos))}
    )


def _faxina_de_vez_em_quando(conexao: Connection) -> None:
    """Apaga contadores vencidos em ~1% das chamadas (a tabela não cresce sem limite)."""
    if secrets.randbelow(100) == 0:
        conexao.execute(_FAXINA)


def contar(chave: str, limite: int, janela: int) -> None:
    """Soma uma requisição ao contador da chave; 429 se passou de ``limite`` na janela."""
    with get_engine_limites().connect() as conexao:
        contagem, restante = conexao.execute(
            _CONTAR, {'chave': chave, 'janela': janela, 'maximo': CONTAGEM_MAXIMA}
        ).one()
        _faxina_de_vez_em_quando(conexao)
    if contagem > limite:
        raise muitas_requisicoes(restante)


# --- Dependências (por IP) -------------------------------------------------------------------------


def limite_login(request: Request) -> None:
    """Tentativas de login por IP (loja e superadmin contam juntas)."""
    s = get_settings()
    contar(_chave('login-ip', _ip(request)), s.limite_login_por_ip, s.limite_login_janela)


def limite_login_site(request: Request) -> None:
    """Tentativas de entrar na conta do cliente no site por IP (contador próprio, valores do login)."""
    s = get_settings()
    contar(_chave('site-login-ip', _ip(request)), s.limite_login_por_ip, s.limite_login_janela)


def limite_site(request: Request) -> None:
    """Requisições ao site do consumidor por IP (todas as lojas e rotas)."""
    s = get_settings()
    contar(_chave('site-ip', _ip(request)), s.limite_site_por_ip, s.limite_site_janela)


def limite_site_pedido(request: Request) -> None:
    """Pedidos de agendamento por IP em cada loja (impede travar a agenda inteira com pedidos)."""
    s = get_settings()
    slug = str(request.path_params.get('slug', ''))
    contar(
        _chave('site-pedido', slug, _ip(request)), s.limite_site_pedidos_por_ip, s.limite_site_pedidos_janela
    )


def limite_codigo_pedido(request: Request, slug: str, telefone_digitos: str) -> None:
    """Pedidos de código do site (SIT-17): por IP (todas as lojas) e um por (loja, telefone, IP) a cada
    ``LIMITE_CODIGO_INTERVALO`` segundos. 429 no primeiro que passar."""
    s = get_settings()
    ip = _ip(request)
    contar(_chave('site-codigo-ip', ip), s.limite_codigos_por_ip, s.limite_codigos_por_ip_janela)
    contar(_chave('site-codigo-intervalo', slug, telefone_digitos, ip), 1, s.limite_codigo_intervalo)


def limite_codigo_telefone(slug: str, telefone_digitos: str) -> None:
    """Códigos gerados de fato para o telefone na loja (SIT-17): só quando não há um pendente."""
    s = get_settings()
    contar(
        _chave('site-codigo-telefone', slug, telefone_digitos),
        s.limite_codigos_por_telefone,
        s.limite_codigos_por_telefone_janela,
    )


_CONTAGEM = text('SELECT contagem FROM limites.contadores WHERE chave = :chave AND expira_em > now()')


class TentativasDoCodigo:
    """Erros num mesmo código vindos de um IP (SIT-17): passou do limite, aquele IP não tenta mais esse
    código, mas o código continua valendo para os outros (o total por código fica na própria linha)."""

    def __init__(self, request: Request, codigo_id: object, validade_segundos: int) -> None:
        self.chave = _chave('site-codigo-tentativa', str(codigo_id), _ip(request))
        self.janela = validade_segundos

    def esgotadas(self) -> bool:
        with get_engine_limites().connect() as conexao:
            contagem = conexao.execute(_CONTAGEM, {'chave': self.chave}).scalar()
        return (contagem or 0) >= get_settings().limite_codigo_tentativas_por_ip

    def errou(self) -> bool:
        """Soma um erro; True se este IP chegou ao limite para o código."""
        with get_engine_limites().connect() as conexao:
            contagem, _ = conexao.execute(
                _CONTAR, {'chave': self.chave, 'janela': self.janela, 'maximo': CONTAGEM_MAXIMA}
            ).one()
        return contagem >= get_settings().limite_codigo_tentativas_por_ip


# --- Bloqueio progressivo por conta (login) --------------------------------------------------------


class BloqueioLogin:
    """Falhas seguidas de login de uma conta (área + loja + e-mail, exista ou não) a partir de um IP."""

    def __init__(self, request: Request, *conta: str) -> None:
        self.chave = _chave('login-conta-ip', _ip(request), *(c.strip().lower() for c in conta))

    def conferir(self) -> None:
        """429 se a conta estiver bloqueada (antes de conferir a senha)."""
        with get_engine_limites().connect() as conexao:
            restante = conexao.execute(_BLOQUEIO, {'chave': self.chave}).scalar()
        if restante is not None:
            minutos = math.ceil(restante / 60)
            raise muitas_requisicoes(
                restante,
                f'Muitas tentativas de login. Aguarde {minutos} minuto(s) e tente novamente.',
            )

    def falhou(self) -> None:
        s = get_settings()
        with get_engine_limites().connect() as conexao:
            falhas = conexao.execute(
                _FALHA, {'chave': self.chave, 'janela': s.login_falhas_janela, 'maximo': CONTAGEM_MAXIMA}
            ).scalar_one()
            excesso = falhas - s.login_falhas_para_bloquear
            if excesso >= 0:
                segundos = min(s.login_bloqueio_inicial * 2 ** min(excesso, 20), s.login_bloqueio_maximo)
                conexao.execute(_BLOQUEAR, {'chave': self.chave, 'segundos': segundos})

    def acertou(self) -> None:
        with get_engine_limites().connect() as conexao:
            conexao.execute(_ZERAR, {'chave': self.chave})


# ---------------------------------------------------------------------------------------------
# Tamanho do corpo da requisição (SEG-12)
# ---------------------------------------------------------------------------------------------

MSG_CORPO_GRANDE = 'O envio passou do tamanho máximo permitido.'
# Folga para os cabeçalhos do multipart em volta do arquivo
MARGEM_DO_CORPO = 64 * 1024


def maximo_do_corpo() -> int:
    """Maior corpo aceito em qualquer rota: o maior arquivo permitido (a logo) mais a folga."""
    return get_settings().logo_tamanho_maximo + MARGEM_DO_CORPO


class LimiteDoCorpo:
    """Middleware ASGI: recusa (413) corpos acima de ``maximo_do_corpo()`` sem lê-los inteiros.

    Confere o Content-Length antes de ler e, sem ele (envio em partes), conta os bytes recebidos.
    Assim um envio enorme não chega a ser gravado em disco pelo leitor de multipart, nem antes da
    autenticação. O limite exato de cada arquivo é conferido na rota (ex.: logo, 2 MB).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        maximo = maximo_do_corpo()
        declarado = Headers(scope=scope).get('content-length')
        if declarado is not None and declarado.isascii() and declarado.isdigit() and int(declarado) > maximo:
            resposta = JSONResponse({'detail': MSG_CORPO_GRANDE}, status.HTTP_413_CONTENT_TOO_LARGE)
            await resposta(scope, receive, send)
            return
        recebido = 0

        async def receber() -> Message:
            nonlocal recebido
            mensagem = await receive()
            if mensagem['type'] == 'http.request':
                recebido += len(mensagem.get('body', b''))
                if recebido > maximo:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, MSG_CORPO_GRANDE)
            return mensagem

        await self.app(scope, receber, send)
