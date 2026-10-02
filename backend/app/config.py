"""Configuração da aplicação, lida só de variáveis de ambiente (ou do arquivo .env)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    ambiente: Literal['desenvolvimento', 'teste', 'producao'] = 'desenvolvimento'

    # Usuário da aplicação: sem privilégio de dono do schema (RLS e REVOKE valem para ele)
    database_url: SecretStr
    # Dono do schema: migrações e criação do papel da aplicação
    database_owner_url: SecretStr
    test_database_name: str = 'agenda_test'

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algoritmo: str = 'HS256'
    jwt_expira_minutos: int = 480

    cors_origens: list[str] = ['http://localhost:5173']

    @property
    def papel_app(self) -> str:
        """Nome do papel (usuário) do Postgres usado pela aplicação."""
        usuario = make_url(self.database_url.get_secret_value()).username
        if not usuario:
            raise ValueError('DATABASE_URL precisa informar o usuário da aplicação.')
        return usuario


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
