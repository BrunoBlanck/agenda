"""Site do consumidor (público): só o necessário para escolher o serviço, o horário e pedir o agendamento."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatusAgendamento, TipoLocal, TipoLoja
from app.schemas.comum import DataHora, DecimalSaida, EmailOpcional, Telefone, texto, texto_opcional


class LojaPublica(BaseModel):
    tipo: TipoLoja = Field(description='Escolhe o site (layout e textos) do tipo da loja')
    slug: str
    nome_fantasia: str
    logo_url: str | None
    telefone: str | None
    email: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
    fuso_horario: str
    usa_servicos: bool = Field(description='false = o site oferece um atendimento genérico de 30 minutos')
    usa_locais: bool
    rotulo_local: str = 'Local'


class ProfissionalPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    cor_agenda: str | None


class ServicoPublico(BaseModel):
    id: UUID | None = Field(description='Nulo no atendimento genérico (loja sem o módulo Serviços)')
    nome: str
    descricao: str | None = None
    duracao_minutos: int
    preco: DecimalSaida | None = None
    profissionais: list[ProfissionalPublico]


class LocalPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    tipo: TipoLocal


class HorarioLivre(BaseModel):
    hora: str = Field(description='HH:MM no fuso da loja')
    inicio: datetime
    funcionario_id: UUID
    funcionario_nome: str
    local: LocalPublico | None = Field(description='Local reservado para o horário (módulo Locais)')


class DiaLivre(BaseModel):
    data: date
    horarios: list[HorarioLivre]


class SolicitacaoEntrada(BaseModel):
    """Pedido de agendamento feito pelo cliente. Campos desconhecidos são recusados."""

    model_config = ConfigDict(extra='forbid')

    servico_id: UUID | None = Field(default=None, description='Obrigatório com o módulo Serviços')
    funcionario_id: UUID
    inicio: DataHora = Field(description='Um dos horários livres. Sem fuso = horário da loja')
    local_id: UUID | None = Field(default=None, description='Vazio = o sistema escolhe um local livre')
    nome: texto(60) = Field(description='Só o primeiro nome')
    sobrenome: texto(100)
    telefone: Telefone = Field(description='WhatsApp com DDD')
    email: EmailOpcional = None
    observacoes: texto_opcional(500) = None


class SolicitacaoSaida(BaseModel):
    id: UUID
    status: StatusAgendamento
    inicio: datetime
    fim: datetime
    servico_nome: str
    funcionario_nome: str
    local: LocalPublico | None
    preco: DecimalSaida | None
    cliente_nome: str = Field(description='O nome informado no pedido')
    mensagem: str
