"""Serviços e vínculos (estrutura.md, 2.8, 2.9, 2.12 e 2.20)."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import TipoLocal
from app.schemas.comum import (
    LISTA_MAX,
    Controle,
    DecimalSaida,
    Dinheiro,
    Entrada,
    QuantidadePositiva,
    Referencia,
    regra,
    texto,
    texto_opcional,
)


class MaterialDoServico(Entrada):
    material_id: UUID
    quantidade: QuantidadePositiva = Decimal(1)


class ServicoEntrada(Entrada):
    nome: texto(120)
    descricao: texto_opcional() = None
    duracao_minutos: int = Field(gt=0, le=24 * 60)
    preco: Dinheiro | None = None
    ativo: bool = True
    funcionario_ids: list[UUID] = Field(
        default_factory=list, max_length=LISTA_MAX, description='Profissionais que realizam'
    )
    local_ids: list[UUID] | None = Field(
        default=None,
        max_length=LISTA_MAX,
        description='Onde pode acontecer ([] = qualquer local ativo). Nulo = não muda. '
        'Ignorado com o módulo Locais desligado.',
    )
    materiais: list[MaterialDoServico] | None = Field(
        default=None,
        max_length=LISTA_MAX,
        description='Materiais por atendimento. Nulo = não muda. Ignorado com o módulo Materiais desligado.',
    )

    @field_validator('funcionario_ids', 'local_ids')
    @classmethod
    def _sem_repetidos(cls, ids: list[UUID] | None) -> list[UUID] | None:
        return None if ids is None else list(dict.fromkeys(ids))

    @field_validator('materiais')
    @classmethod
    def _material_uma_vez(cls, materiais: list[MaterialDoServico] | None) -> list[MaterialDoServico] | None:
        if materiais is not None and len({m.material_id for m in materiais}) != len(materiais):
            raise regra('Cada material só pode aparecer uma vez no serviço.')
        return materiais


class LocalDoServico(Referencia):
    tipo: TipoLocal


class MaterialDoServicoSaida(BaseModel):
    material_id: UUID
    nome: str
    unidade: str
    quantidade: DecimalSaida


class ServicoSaida(Controle):
    id: UUID
    nome: str
    descricao: str | None
    duracao_minutos: int
    preco: DecimalSaida | None
    ativo: bool
    funcionario_ids: list[UUID] = Field(default_factory=list)
    profissionais: list[Referencia] = Field(default_factory=list)
    local_ids: list[UUID] = Field(default_factory=list, description='Vazio = qualquer local ativo')
    locais: list[LocalDoServico] = Field(default_factory=list)
    materiais: list[MaterialDoServicoSaida] = Field(default_factory=list)


class MaterialOpcao(Referencia):
    unidade: str


class OpcoesServico(BaseModel):
    """Listas do formulário de serviço (só itens ativos), sem exigir acesso a Funcionários ou Materiais."""

    profissionais: list[Referencia]
    locais: list[LocalDoServico] | None = Field(description='Nulo = módulo Locais desligado')
    materiais: list[MaterialOpcao] | None = Field(description='Nulo = módulo Materiais desligado')
