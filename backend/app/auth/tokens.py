"""Tokens JWT. O tipo do usuário vai no token: funcionario (com loja_id) ou superadmin."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt

from app.config import get_settings

TipoUsuario = Literal['funcionario', 'superadmin']


@dataclass(frozen=True)
class DadosToken:
    usuario_id: UUID
    tipo: TipoUsuario
    loja_id: UUID | None


class TokenInvalido(Exception):
    pass


def criar_token(usuario_id: UUID, tipo: TipoUsuario, loja_id: UUID | None = None) -> tuple[str, datetime]:
    settings = get_settings()
    agora = datetime.now(UTC)
    expira_em = agora + timedelta(minutes=settings.jwt_expira_minutos)
    dados: dict[str, object] = {'sub': str(usuario_id), 'tipo': tipo, 'iat': agora, 'exp': expira_em}
    if tipo == 'funcionario':
        if loja_id is None:
            raise ValueError('Token de funcionário precisa da loja.')
        dados['loja_id'] = str(loja_id)
    token = jwt.encode(dados, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algoritmo)
    return token, expira_em


def ler_token(token: str) -> DadosToken:
    settings = get_settings()
    try:
        dados = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algoritmo],
            options={'require': ['sub', 'tipo', 'exp', 'iat']},
        )
        tipo = dados['tipo']
        if tipo not in ('funcionario', 'superadmin'):
            raise TokenInvalido
        loja_id = UUID(dados['loja_id']) if tipo == 'funcionario' else None
        return DadosToken(usuario_id=UUID(dados['sub']), tipo=tipo, loja_id=loja_id)
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as erro:
        raise TokenInvalido from erro
