"""Cifra simétrica (Fernet) de segredos que a aplicação precisa ler de volta: a senha SMTP da loja (CFG-06).

A chave fica só no ``.env`` (``CHAVE_CIFRA``). Sem ela, nada é cifrado (a loja não salva senha de e-mail).
Trocar a chave torna ilegíveis as senhas já salvas: a loja precisa salvá-las de novo.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class SenhaIlegivel(Exception):
    """O texto cifrado não abre com a chave atual (chave trocada ou dado corrompido)."""


def _fernet() -> Fernet | None:
    chave = get_settings().chave_cifra
    return Fernet(chave.get_secret_value().encode()) if chave is not None else None


def cifra_disponivel() -> bool:
    return get_settings().chave_cifra is not None


def cifrar(texto: str) -> str:
    fernet = _fernet()
    if fernet is None:
        raise RuntimeError('CHAVE_CIFRA não configurada.')
    return fernet.encrypt(texto.encode()).decode()


def decifrar(cifrado: str) -> str:
    fernet = _fernet()
    if fernet is None:
        raise SenhaIlegivel
    try:
        return fernet.decrypt(cifrado.encode()).decode()
    except InvalidToken:
        raise SenhaIlegivel from None
