"""Configuração da aplicação, lida só de variáveis de ambiente (ou do arquivo .env)."""

from functools import lru_cache
from pathlib import Path
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

    # --- Proteção contra abuso (app/limites.py). Janelas em segundos. ---
    # Login (loja e superadmin): tentativas por IP
    limite_login_por_ip: int = Field(default=20, ge=1)
    limite_login_janela: int = Field(default=60, ge=1)
    # Login: falhas seguidas por conta (e-mail) até bloquear; o bloqueio dobra a cada nova falha
    login_falhas_para_bloquear: int = Field(default=5, ge=1)
    login_falhas_janela: int = Field(default=3600, ge=1)
    login_bloqueio_inicial: int = Field(default=60, ge=1)
    login_bloqueio_maximo: int = Field(default=900, ge=1)
    # Site do consumidor: requisições por IP (todas as rotas) e pedidos de agendamento por IP e loja
    limite_site_por_ip: int = Field(default=120, ge=1)
    limite_site_janela: int = Field(default=60, ge=1)
    limite_site_pedidos_por_ip: int = Field(default=10, ge=1)
    limite_site_pedidos_janela: int = Field(default=3600, ge=1)
    # Site: pedidos "Aguardando aceite" (futuros) ao mesmo tempo por telefone, em cada loja
    site_pendentes_por_telefone: int = Field(default=3, ge=1)

    # --- Arquivos enviados (logo da loja, app/services/arquivos.py) ---
    # Pasta no disco (em produção, um volume persistente). Padrão: backend/arquivos
    arquivos_dir: Path = Path(__file__).resolve().parent.parent / 'arquivos'
    # Tamanho máximo da logo, em bytes (padrão 2 MB)
    logo_tamanho_maximo: int = Field(default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)

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
