"""Configuração da aplicação, lida só de variáveis de ambiente (ou do arquivo .env)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator
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
    # Site, conta do cliente (SIT-17): códigos de confirmação por telefone (em cada loja) e por IP
    limite_codigo_intervalo: int = Field(default=60, ge=1)  # um pedido por telefone e IP a cada N segundos
    limite_codigos_por_telefone: int = Field(default=5, ge=1)  # códigos gerados de fato, por janela
    limite_codigos_por_telefone_janela: int = Field(default=3600, ge=1)
    limite_codigos_por_ip: int = Field(default=10, ge=1)
    limite_codigos_por_ip_janela: int = Field(default=3600, ge=1)
    limite_codigo_tentativas_por_ip: int = Field(default=5, ge=1)  # erros no mesmo código vindos de um IP
    # Site, conta do cliente (SIT-20): validade da sessão (cookie), em dias. Provisório
    site_sessao_dias: int = Field(default=30, ge=1, le=365)

    # --- Arquivos enviados (logo da loja, app/services/arquivos.py) ---
    # Pasta no disco (em produção, um volume persistente). Padrão: backend/arquivos
    arquivos_dir: Path = Path(__file__).resolve().parent.parent / 'arquivos'
    # Tamanho máximo da logo, em bytes (padrão 2 MB)
    logo_tamanho_maximo: int = Field(default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)

    # --- Notificações (app/services/notificacoes.py, app/tarefas.py) ---
    # Chave Fernet que cifra a senha SMTP de cada loja (CFG-06). Sem ela, a loja não salva senha de e-mail.
    chave_cifra: SecretStr | None = None
    # Endereço público do site (ex.: https://agenda.exemplo.com), para o link "Minha conta" no e-mail ao
    # cliente (NOT-08). Sem ele, o e-mail vai sem link.
    url_publica: str | None = None
    # Tarefa de fundo (envio de e-mails e lembretes) no processo da API. None = ligada fora de AMBIENTE=teste
    notificacoes_tarefa: bool | None = None
    notificacoes_intervalo: int = Field(default=30, ge=5, le=3600)  # segundos entre os ciclos

    @field_validator('chave_cifra')
    @classmethod
    def _chave_fernet(cls, chave: SecretStr | None) -> SecretStr | None:
        if chave is None or not chave.get_secret_value().strip():
            return None
        try:
            Fernet(chave.get_secret_value().strip().encode())
        except ValueError:
            raise ValueError(
                'CHAVE_CIFRA inválida: gere com '
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            ) from None
        return SecretStr(chave.get_secret_value().strip())

    @field_validator('url_publica')
    @classmethod
    def _url_publica(cls, url: str | None) -> str | None:
        if url is None or not url.strip():
            return None
        url = url.strip().rstrip('/')
        partes = urlsplit(url)
        if partes.scheme not in ('http', 'https') or not partes.netloc or partes.query or partes.fragment:
            raise ValueError('URL_PUBLICA deve ser http(s)://dominio, sem consulta.')
        return url

    @property
    def tarefa_de_notificacoes(self) -> bool:
        """A tarefa de fundo roda neste processo? (padrão: sim, menos nos testes)."""
        if self.notificacoes_tarefa is None:
            return self.ambiente != 'teste'
        return self.notificacoes_tarefa

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
