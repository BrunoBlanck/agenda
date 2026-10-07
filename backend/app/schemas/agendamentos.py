"""Agendamentos, pagamento, listas de apoio e histórico do cliente (estrutura.md, 2.13, 2.14 e 2.25)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import FormaPagamento, OrigemAgendamento, StatusAgendamento, TipoLocal
from app.schemas.clientes import ClienteSaida
from app.schemas.comum import (
    LISTA_MAX,
    Controle,
    DataHora,
    DecimalSaida,
    Dinheiro,
    Entrada,
    Esquema,
    Pagina,
    QuantidadePositiva,
    regra,
    texto_opcional,
)
from app.schemas.locais import validar_link
from app.schemas.servicos import ServicoSaida


class AgendamentoEntrada(Entrada):
    cliente_id: UUID
    servico_id: UUID | None = Field(
        default=None, description='Obrigatório com o módulo Serviços ativo; ignorado com ele desligado'
    )
    funcionario_id: UUID
    local_id: UUID | None = Field(
        default=None, description='Obrigatório com o módulo Locais ativo; ignorado com ele desligado'
    )
    link_reuniao: texto_opcional(500) = Field(default=None, description='Só para local online')
    inicio: DataHora = Field(description='Sem fuso, vale o horário da loja')
    duracao_minutos: int | None = Field(
        default=None, gt=0, le=24 * 60, description='Vazio = duração do serviço (obrigatória sem serviço)'
    )
    preco: Dinheiro | None = Field(
        default=None, description='Vazio = preço do serviço (congelado no agendamento)'
    )
    status: StatusAgendamento | None = Field(
        default=None, description='Na criação: agendado (padrão) ou confirmado. Na edição, muda o status'
    )
    observacoes: texto_opcional() = None
    motivo_cancelamento: texto_opcional() = None

    _link = field_validator('link_reuniao')(validar_link)


class StatusEntrada(Entrada):
    status: StatusAgendamento
    motivo_cancelamento: texto_opcional() = Field(default=None, description='Obrigatório para cancelar')


class RecusaEntrada(Entrada):
    motivo_cancelamento: texto_opcional() = None


class MaterialUsado(Entrada):
    material_id: UUID
    quantidade: QuantidadePositiva


class MateriaisEntrada(Entrada):
    materiais: list[MaterialUsado] = Field(max_length=LISTA_MAX)

    @field_validator('materiais')
    @classmethod
    def _uma_vez(cls, materiais: list[MaterialUsado]) -> list[MaterialUsado]:
        if len({m.material_id for m in materiais}) != len(materiais):
            raise regra('Cada material só pode aparecer uma vez.')
        return materiais


class PagamentoEntrada(Entrada):
    """Registrar o pagamento conclui o atendimento (AGE-26, AGE-27)."""

    forma: FormaPagamento
    valor: Dinheiro = Field(description='De 0 (cortesia) a 99.999.999,99, no máximo 2 casas')


class PagamentoSaida(BaseModel):
    id: UUID
    forma: FormaPagamento
    valor: DecimalSaida
    pago_em: datetime = Field(description='Hora do servidor, no fuso da loja')
    registrado_por_nome: str | None = Field(description='Funcionário que registrou')


class MaterialUsadoSaida(BaseModel):
    material_id: UUID
    nome: str
    unidade: str
    quantidade: DecimalSaida


class AgendamentoSaida(Controle):
    id: UUID
    cliente_id: UUID
    cliente_nome: str | None = Field(default=None, description='Nome completo')
    servico_id: UUID | None
    servico_nome: str | None = None
    funcionario_id: UUID
    funcionario_nome: str | None = None
    cor_agenda: str | None = None
    local_id: UUID | None
    local_nome: str | None = None
    local_tipo: TipoLocal | None = None
    link_reuniao: str | None
    link: str | None = Field(default=None, description='Link efetivo: o do atendimento ou o fixo do local')
    inicio: datetime
    fim: datetime
    duracao_minutos: int = 0
    preco: DecimalSaida | None
    status: StatusAgendamento
    origem: OrigemAgendamento
    observacoes: str | None
    motivo_cancelamento: str | None
    criado_por: UUID | None
    materiais: list[MaterialUsadoSaida] | None = Field(default=None, description='Só no detalhe')
    pagamento: PagamentoSaida | None = Field(
        default=None,
        description='Pagamento ativo (só em concluído). Nulo nos demais e nos concluídos antigos (AGE-29)',
    )


# --- Listas de apoio ---------------------------------------------------------------------------


class ClienteApoio(Esquema):
    """Cliente na busca do formulário de agendamento: só o necessário para escolher (sem CPF/e-mail)."""

    id: UUID
    nome: str
    sobrenome: str
    telefone: str


class ProfissionalApoio(Esquema):
    id: UUID
    nome: str
    cor_agenda: str | None
    perfil_id: UUID
    cargo_nome: str | None = None


class LocalApoio(Esquema):
    id: UUID
    nome: str
    tipo: TipoLocal
    link_padrao: str | None


class MaterialApoio(Esquema):
    id: UUID
    nome: str
    unidade: str


class ApoioAgendamento(BaseModel):
    """O que o formulário de agendamento precisa (estrutura.md, 2.2: listas de apoio).

    Os clientes não vêm aqui: o formulário busca em GET /apoio/clientes?busca=... (paginado).
    """

    servicos: list[ServicoSaida] | None = Field(description='Nulo com o módulo Serviços desligado')
    profissionais: list[ProfissionalApoio]
    locais: list[LocalApoio] | None = Field(description='Nulo com o módulo Locais desligado')
    materiais: list[MaterialApoio] | None = Field(
        default=None,
        description=(
            'Materiais ativos, para ajustar o que foi usado no atendimento. '
            'Nulo com o módulo Materiais desligado'
        ),
    )


class ProfissionalFiltro(Esquema):
    id: UUID
    nome: str
    cor_agenda: str | None
    ativo: bool


class LocalFiltro(Esquema):
    id: UUID
    nome: str
    tipo: TipoLocal
    ativo: bool


class FiltrosAgenda(BaseModel):
    """Opções dos filtros da agenda e da lista de agendamentos (leitura na agenda basta)."""

    so_propria: bool = Field(description='O usuário só vê a própria agenda (a lista traz só ele)')
    profissionais: list[ProfissionalFiltro] = Field(description='Ativos primeiro; inclui os inativos')
    locais: list[LocalFiltro] | None = Field(description='Nulo com o módulo Locais desligado')


class Disponibilidade(BaseModel):
    aviso: str | None = Field(description='Horário bloqueado ou fora da jornada (nulo = disponível)')
    profissional_ocupado: bool
    locais_ocupados: list[UUID]


# --- Histórico do cliente ----------------------------------------------------------------------


class HistoricoCliente(BaseModel):
    cliente: ClienteSaida
    concluidos: int
    faltas: int
    cancelados: int
    total_gasto: DecimalSaida = Decimal(0)
    ultimo: AgendamentoSaida | None = Field(description='Último atendimento concluído')
    proximo: AgendamentoSaida | None = Field(description='Próximo agendamento ativo')
    parcial: bool = Field(description='Há agendamentos do cliente que o usuário não pode ver')
    agendamentos: Pagina[AgendamentoSaida]


FiltroHistorico = Literal['todos', 'concluidos', 'faltas']
