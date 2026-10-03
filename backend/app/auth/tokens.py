"""Tokens JWT. O tipo do usuário vai no token: funcionario (com loja_id) ou superadmin."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt

from app.config import get_settings

TipoUsuario = Literal['funcionario', 'superadmin']

# Sessão aberta pelo SUPERADMIN em "Acessar loja" (PLA-18): validade fixa, sem renovação
VALIDADE_SUPORTE = timedelta(hours=1)


@dataclass(frozen=True)
class DadosToken:
    usuario_id: UUID
    tipo: TipoUsuario
    loja_id: UUID | None
    expira_em: datetime
    suporte: bool = False  # token de funcionário gerado pelo SUPERADMIN em "Acessar loja"


class TokenInvalido(Exception):
    pass


def criar_token(
    usuario_id: UUID, tipo: TipoUsuario, loja_id: UUID | None = None, *, suporte: bool = False
) -> tuple[str, datetime]:
    """Token assinado. ``suporte=True`` (só funcionário) marca a claim ``suporte`` e vale VALIDADE_SUPORTE."""
    settings = get_settings()
    agora = datetime.now(UTC).replace(microsecond=0)  # o JWT guarda segundos: expira_em = exp
    validade = VALIDADE_SUPORTE if suporte else timedelta(minutes=settings.jwt_expira_minutos)
    expira_em = agora + validade
    dados: dict[str, object] = {'sub': str(usuario_id), 'tipo': tipo, 'iat': agora, 'exp': expira_em}
    if tipo == 'funcionario':
        if loja_id is None:
            raise ValueError('Token de funcionário precisa da loja.')
        dados['loja_id'] = str(loja_id)
        if suporte:
            dados['suporte'] = True
    elif suporte:
        raise ValueError('Só o token de funcionário pode ser de suporte.')
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
        funcionario = tipo == 'funcionario'
        return DadosToken(
            usuario_id=UUID(dados['sub']),
            tipo=tipo,
            loja_id=UUID(dados['loja_id']) if funcionario else None,
            expira_em=datetime.fromtimestamp(dados['exp'], UTC),
            suporte=funcionario and dados.get('suporte') is True,
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError, OverflowError, OSError) as erro:
        raise TokenInvalido from erro
