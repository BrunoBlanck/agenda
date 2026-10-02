"""Materiais, categorias e movimentações de estoque (estrutura.md, 2.10, 2.11 e 2.15)."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, model_validator

from app.models.enums import TipoMovimentacao
from app.schemas.comum import Controle, DecimalSaida, Entrada, Quantidade, regra, texto, texto_opcional


def _unidade_padrao(valor: Any) -> Any:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 'un'
    return valor


Unidade = Annotated[texto(10), BeforeValidator(_unidade_padrao), Field(description='un, cx, pct, ml...')]
NaoNegativa = Annotated[Quantidade, Field(ge=0)]


class CategoriaEntrada(Entrada):
    nome: texto(80)


class CategoriaSaida(Controle):
    id: UUID
    nome: str


class MaterialEdicao(Entrada):
    nome: texto(150)
    categoria_id: UUID | None = None
    unidade: Unidade = 'un'
    estoque_minimo: NaoNegativa = Decimal(0)
    ativo: bool = True


class MaterialNovo(MaterialEdicao):
    quantidade_inicial: NaoNegativa = Field(
        default=Decimal(0), description='Lançada como uma movimentação de entrada (o estoque só muda assim)'
    )


class MaterialSaida(Controle):
    id: UUID
    nome: str
    categoria_id: UUID | None
    categoria_nome: str | None = None
    unidade: str
    quantidade_atual: DecimalSaida
    estoque_minimo: DecimalSaida
    ativo: bool
    repor: bool = Field(default=False, description='Quantidade abaixo do estoque mínimo')


class MovimentacaoEntrada(Entrada):
    """Lançamento manual. A saída por atendimento é automática, ao concluir o agendamento."""

    tipo: Literal['entrada', 'ajuste', 'perda']
    quantidade: Quantidade = Field(
        description='entrada: positiva; perda: informe a quantidade perdida (vira negativa); '
        'ajuste: positiva soma, negativa subtrai'
    )
    motivo: texto_opcional(200) = Field(default=None, description='Obrigatório em ajuste e perda')

    @model_validator(mode='after')
    def _regras(self) -> 'MovimentacaoEntrada':
        if self.quantidade == 0:
            raise regra('A quantidade não pode ser zero.')
        if self.tipo == 'entrada' and self.quantidade < 0:
            raise regra('A entrada deve ter quantidade positiva.')
        if self.tipo == 'perda':
            self.quantidade = -abs(self.quantidade)
        if self.tipo in ('ajuste', 'perda') and not self.motivo:
            raise regra('Informe o motivo do ajuste ou da perda.')
        return self


class MovimentacaoSaida(Controle):
    id: UUID
    material_id: UUID
    tipo: TipoMovimentacao
    quantidade: DecimalSaida
    agendamento_id: UUID | None
    funcionario_id: UUID | None
    funcionario_nome: str | None = None
    motivo: str | None
    criado_em: datetime
