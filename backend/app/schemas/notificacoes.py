"""Notificações do painel (NOT-06) e Configurações › Avisos e e-mail (CFG-05, CFG-06)."""

import ipaddress
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, StringConstraints, field_validator

from app.schemas.comum import Controle, EmailOpcional, Entrada, Pagina, regra, texto_opcional, vazio_para_none

ANTECEDENCIA_MAXIMA = 10_080  # 7 dias, em minutos
PORTAS_SMTP = (25, 465, 587, 2525)
VISUALIZAR_MAXIMO = 100
NOTIFICACOES_POR_PAGINA_MAX = 50

MSG_SERVIDOR = 'Informe só o nome do servidor (ex.: smtp.exemplo.com), sem http:// nem porta.'
MSG_PORTA = 'Use a porta 25, 465, 587 ou 2525.'

# --- Sino do painel ------------------------------------------------------------------------------------


class NotificacaoSaida(BaseModel):
    id: UUID
    evento: str
    titulo: str
    mensagem: str
    agendamento_id: UUID | None = Field(description='Nulo se o agendamento foi excluído')
    inicio_agendamento: datetime | None = Field(
        description='Fuso da loja; nulo se o agendamento foi excluído'
    )
    visualizada: bool
    visualizada_em: datetime | None
    status_email: int = Field(description='1 pendente, 2 enviado, 3 erro, 4 dado faltando no cadastro')
    status_whatsapp: int = Field(description='1 pendente, 2 enviado, 3 erro, 4 dado faltando (hoje sempre 4)')
    criado_em: datetime


class ListaNotificacoes(Pagina[NotificacaoSaida]):
    nao_visualizadas: int


class ResumoNotificacoes(BaseModel):
    nao_visualizadas: int


class VisualizarEntrada(Entrada):
    ids: list[UUID] = Field(min_length=1, max_length=VISUALIZAR_MAXIMO)


class VisualizarSaida(BaseModel):
    marcadas: int
    nao_visualizadas: int


# --- Configurações › Avisos e e-mail -----------------------------------------------------------------

_HOST = re.compile(r'(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))*', re.ASCII)


def _servidor(valor: Any) -> Any:
    """Nome de host ou IP, sem esquema, porta nem caminho (vira minúsculas)."""
    valor = vazio_para_none(valor)
    if not isinstance(valor, str):
        return valor
    servidor = valor.strip().lower().rstrip('.')
    try:
        ipaddress.ip_address(servidor.strip('[]'))
    except ValueError:
        if not _HOST.fullmatch(servidor):
            raise regra(MSG_SERVIDOR) from None
        return servidor
    return servidor.strip('[]')


Servidor = Annotated[
    str | None,
    BeforeValidator(_servidor),
    Field(description='Nome do servidor SMTP ou IP, sem esquema (ex.: smtp.exemplo.com)'),
]


class EmailConfigEntrada(Entrada):
    ativo: bool
    servidor: Servidor = None
    porta: int | None = None
    seguranca: Literal['ssl', 'starttls'] | None = None
    usuario: texto_opcional(255) = None
    senha: Annotated[str, StringConstraints(min_length=1, max_length=255)] | None = Field(
        default=None, description='Ausente = mantém a senha salva; null = apaga'
    )
    remetente_email: EmailOpcional = None
    remetente_nome: texto_opcional(120) = None

    @field_validator('porta')
    @classmethod
    def _porta(cls, porta: int | None) -> int | None:
        if porta is not None and porta not in PORTAS_SMTP:
            raise regra(MSG_PORTA)
        return porta

    @property
    def mudar_senha(self) -> bool:
        """A senha veio no corpo (string = troca, null = apaga); ausente = mantém."""
        return 'senha' in self.model_fields_set


class ConfigNotificacoesEntrada(Entrada):
    antecedencia_cliente_minutos: int = Field(ge=0, le=ANTECEDENCIA_MAXIMA)
    email: EmailConfigEntrada


class EmailConfig(BaseModel):
    ativo: bool
    servidor: str | None
    porta: int | None
    seguranca: Literal['ssl', 'starttls'] | None
    usuario: str | None
    senha_definida: bool = Field(description='Há senha salva (a senha nunca sai pela API)')
    remetente_email: str | None
    remetente_nome: str | None


class ConfigNotificacoes(Controle):
    antecedencia_cliente_minutos: int
    email: EmailConfig
    whatsapp_disponivel: bool


class TesteEmailEntrada(Entrada):
    destino: EmailStr


class TesteEmailSaida(BaseModel):
    enviado: bool
    erro: str | None = None
