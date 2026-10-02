"""Dependências de autenticação e permissão.

- ``ContextoLojaDep``: funcionário logado (token do tipo funcionario), loja ativa, acesso calculado
  e contexto da transação gravado (app.funcionario_id, app.loja_id, app.origem = painel).
- ``exigir(recurso, nivel)``: além do acima, exige o nível no recurso (perfil + módulo ligado).
- ``ContextoSuperadminDep``: superadmin logado (token do tipo superadmin), contexto gravado
  (app.superadmin_id, app.origem = superadmin).

Toda consulta da loja deve filtrar por ``ctx.loja_id`` (que vem do token), nunca por um loja_id
vindo do corpo ou da URL.
"""

import ipaddress
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.catalogo import RECURSOS
from app.auth.tokens import DadosToken, TipoUsuario, TokenInvalido, ler_token
from app.db import definir_contexto, sessao
from app.models import Funcionario, Loja, Perfil, SuperadminUsuario
from app.models.enums import NivelAcesso, StatusLoja
from app.services.acesso import Acesso, calcular_acesso

# Sessão com commit antes de a resposta sair (ver app.db.sessao)
DbDep = Annotated[Session, Depends(sessao, scope='function')]

_bearer = HTTPBearer(auto_error=False, description='Token obtido no login')

MSG_SESSAO_INVALIDA = 'Sua sessão expirou ou é inválida. Entre novamente.'
MSG_STATUS_LOJA = {
    StatusLoja.suspensa: 'Esta loja está suspensa. Fale com o suporte da plataforma.',
    StatusLoja.cancelada: 'Esta loja foi cancelada. Fale com o suporte da plataforma.',
}


def nao_autenticado(mensagem: str = MSG_SESSAO_INVALIDA) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, mensagem, headers={'WWW-Authenticate': 'Bearer'})


def ip_da_requisicao(request: Request) -> str | None:
    """IP do cliente para a auditoria (None se não for um IP válido)."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def _ler_credenciais(credenciais: HTTPAuthorizationCredentials | None, tipo: TipoUsuario) -> DadosToken:
    if credenciais is None:
        raise nao_autenticado('Faça login para continuar.')
    try:
        dados = ler_token(credenciais.credentials)
    except TokenInvalido:
        raise nao_autenticado() from None
    if dados.tipo != tipo:
        # Token de superadmin nas rotas da loja (ou o contrário)
        raise nao_autenticado('Este acesso não vale para esta área. Entre com o usuário correto.')
    return dados


def verificar_status_loja(loja: Loja) -> None:
    if loja.status != StatusLoja.ativa:
        raise HTTPException(status.HTTP_403_FORBIDDEN, MSG_STATUS_LOJA[loja.status])


# ---------------------------------------------------------------------------------------------
# Painel da loja
# ---------------------------------------------------------------------------------------------


@dataclass
class ContextoLoja:
    db: Session
    loja: Loja
    funcionario: Funcionario
    perfil: Perfil
    acesso: Acesso

    @property
    def loja_id(self) -> UUID:
        return self.loja.id

    def pode(self, recurso: str, minimo: NivelAcesso = NivelAcesso.leitura) -> bool:
        return self.acesso.pode(recurso, minimo)


def obter_contexto_loja(
    request: Request,
    db: DbDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ContextoLoja:
    dados = _ler_credenciais(credenciais, 'funcionario')
    if dados.loja_id is None:
        raise nao_autenticado()
    definir_contexto(
        db,
        origem='painel',
        funcionario_id=dados.usuario_id,
        loja_id=dados.loja_id,
        ip=ip_da_requisicao(request),
    )
    loja = db.scalar(select(Loja).where(Loja.id == dados.loja_id))
    funcionario = db.scalar(
        select(Funcionario).where(Funcionario.id == dados.usuario_id, Funcionario.loja_id == dados.loja_id)
    )
    if loja is None or funcionario is None or not funcionario.ativo:
        raise nao_autenticado()
    verificar_status_loja(loja)
    perfil = db.scalar(select(Perfil).where(Perfil.id == funcionario.perfil_id, Perfil.loja_id == loja.id))
    if perfil is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, 'Seu usuário está sem perfil de acesso. Fale com o administrador.'
        )
    return ContextoLoja(
        db=db, loja=loja, funcionario=funcionario, perfil=perfil, acesso=calcular_acesso(db, loja.id, perfil)
    )


ContextoLojaDep = Annotated[ContextoLoja, Depends(obter_contexto_loja)]


def exigir(
    recursos: str | Sequence[str], nivel: NivelAcesso | str = NivelAcesso.leitura
) -> Callable[..., ContextoLoja]:
    """Dependência que exige ``nivel`` em pelo menos um dos ``recursos``.

    Ex.: ``ctx: ContextoLoja = Depends(exigir('clientes', 'escrita'))`` ou
    ``Depends(exigir(('agenda_propria', 'agenda_equipe')))``. Responde 403 com mensagem em português.
    """
    codigos = (recursos,) if isinstance(recursos, str) else tuple(recursos)
    desconhecidos = [c for c in codigos if c not in RECURSOS]
    if not codigos or desconhecidos:
        raise ValueError(f'Recurso desconhecido em exigir(): {desconhecidos}')
    minimo = NivelAcesso(nivel)

    def dependencia(ctx: ContextoLojaDep) -> ContextoLoja:
        if any(ctx.pode(c, minimo) for c in codigos):
            return ctx
        if not any(ctx.acesso.modulo_ativo(RECURSOS[c]) for c in codigos):
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Este módulo não está ativo na sua loja.')
        if minimo == NivelAcesso.escrita and any(ctx.pode(c) for c in codigos):
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Você só tem permissão de leitura aqui.')
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Você não tem permissão para acessar esta área.')

    return dependencia


# ---------------------------------------------------------------------------------------------
# Plataforma (SUPERADMIN)
# ---------------------------------------------------------------------------------------------


@dataclass
class ContextoSuperadmin:
    db: Session
    superadmin: SuperadminUsuario


def obter_contexto_superadmin(
    request: Request,
    db: DbDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ContextoSuperadmin:
    dados = _ler_credenciais(credenciais, 'superadmin')
    definir_contexto(db, origem='superadmin', superadmin_id=dados.usuario_id, ip=ip_da_requisicao(request))
    superadmin = db.scalar(select(SuperadminUsuario).where(SuperadminUsuario.id == dados.usuario_id))
    if superadmin is None or not superadmin.ativo:
        raise nao_autenticado()
    return ContextoSuperadmin(db=db, superadmin=superadmin)


ContextoSuperadminDep = Annotated[ContextoSuperadmin, Depends(obter_contexto_superadmin)]
