"""Hash de senhas com Argon2."""

from functools import lru_cache

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


@lru_cache
def _hash_ficticio() -> str:
    return _hasher.hash('senha-ficticia-para-igualar-o-tempo')


def verificar_senha(senha: str, senha_hash: str | None) -> tuple[bool, str | None]:
    """Confere a senha. Retorna (válida, novo_hash quando o hash precisa ser atualizado).

    Sem usuário (senha_hash None), confere contra um hash fictício para o tempo de resposta não
    revelar se o e-mail existe.
    """
    if senha_hash is None:
        _hasher.verify(senha, _hash_ficticio())
        return False, None
    return _hasher.verify_and_update(senha, senha_hash)
