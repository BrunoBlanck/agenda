"""Identificadores assinados para URLs do site: ``<id hex><validade hex>.<assinatura>``.

Curtos, sem dado pessoal legível, presos à loja e a um **domínio** (para que serve: a confirmação de um
pedido não vale como passo da conta, e vice-versa). A assinatura é um HMAC-SHA256 (16 bytes) com o
segredo do JWT; adulterar o id, a validade, a loja ou o domínio invalida o código.
"""

import base64
import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.config import get_settings

_FORMATO = re.compile(r'^([0-9a-f]{32})([0-9a-f]{8})\.([A-Za-z0-9_-]{22})$')


def assinatura(dominio: str, loja_id: UUID, corpo: str) -> str:
    segredo = get_settings().jwt_secret.get_secret_value().encode()
    mensagem = f'{dominio}\x1f{loja_id}\x1f{corpo}'.encode()
    resumo = hmac.new(segredo, mensagem, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(resumo).decode().rstrip('=')


def assinar_id(
    dominio: str, loja_id: UUID, id_: UUID, validade: timedelta, *, agora: datetime | None = None
) -> str:
    expira = int(((agora or datetime.now(UTC)) + validade).timestamp())
    corpo = f'{id_.hex}{expira:08x}'
    return f'{corpo}.{assinatura(dominio, loja_id, corpo)}'


def ler_id(
    texto: str, loja_id: UUID, dominios: tuple[str, ...], *, agora: datetime | None = None
) -> tuple[UUID, str] | None:
    """(id, domínio que confere) se o texto for válido, desta loja e dentro da validade; senão None."""
    partes = _FORMATO.fullmatch(texto or '')
    if partes is None:
        return None
    id_hex, expira_hex, recebida = partes.groups()
    if int(expira_hex, 16) < (agora or datetime.now(UTC)).timestamp():
        return None
    corpo = f'{id_hex}{expira_hex}'
    for dominio in dominios:
        if hmac.compare_digest(recebida, assinatura(dominio, loja_id, corpo)):
            return UUID(id_hex), dominio
    return None
