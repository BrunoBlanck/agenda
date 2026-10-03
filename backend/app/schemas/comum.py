"""Schemas compartilhados: paginação, erros, tipos de campo e colunas de controle."""

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
)
from pydantic_core import PydanticCustomError

# Limites gerais de entrada (SEG-10, SEG-12)
TEXTO_MAX = 2000  # textos livres (observações, descrição, justificativa, motivo...)
LISTA_MAX = 200  # itens em listas de ids e vínculos
PAGINA_MAX = 10_000
# Faixa aceita em datas e horários informados pelo usuário (protege contra 9999-12-31 e afins)
ANO_MIN, ANO_MAX = 2000, 2100


class Esquema(BaseModel):
    """Base dos schemas de saída: aceita objetos do ORM."""

    model_config = ConfigDict(from_attributes=True)


class Entrada(BaseModel):
    """Base dos schemas de entrada: ignora campos desconhecidos (ex.: id, criado_em vindos do front)."""

    model_config = ConfigDict(extra='ignore')


class Paginacao(BaseModel):
    pagina: int
    por_pagina: int

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.por_pagina


def paginacao(
    pagina: Annotated[int, Query(ge=1, le=PAGINA_MAX, description='Página, começando em 1')] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100, description='Itens por página')] = 20,
) -> Paginacao:
    """Dependência para listas que crescem (agendamentos, clientes, auditoria)."""
    return Paginacao(pagina=pagina, por_pagina=por_pagina)


class Pagina[T](BaseModel):
    itens: list[T]
    total: int
    pagina: int
    por_pagina: int


class ErroCampo(BaseModel):
    campo: str
    mensagem: str


class Erro(BaseModel):
    detail: str
    erros: list[ErroCampo] | None = None


# ---------------------------------------------------------------------------------------------
# Tipos de campo
# ---------------------------------------------------------------------------------------------


def regra(mensagem: str) -> PydanticCustomError:
    """Erro de validação com mensagem em português que chega ao usuário como está.

    Use em validadores: ``raise regra('O fim deve ser depois do início.')``.
    """
    return PydanticCustomError('regra', mensagem)


def vazio_para_none(valor: Any) -> Any:
    """Texto vazio (ou só espaços) vindo de formulário vira None."""
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


def texto(maximo: int = TEXTO_MAX, minimo: int = 1) -> Any:
    """Texto obrigatório, sem espaços nas pontas (no máximo TEXTO_MAX caracteres, se nada for dito)."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=minimo, max_length=maximo)]


def texto_opcional(maximo: int = TEXTO_MAX) -> Any:
    """Texto opcional: vazio vira None (no máximo TEXTO_MAX caracteres, se nada for dito)."""
    return Annotated[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=maximo)] | None,
        BeforeValidator(vazio_para_none),
    ]


EmailOpcional = Annotated[EmailStr | None, BeforeValidator(vazio_para_none)]


# --- Datas -----------------------------------------------------------------------------------------


def _data_na_faixa(valor: date) -> date:
    if not ANO_MIN <= valor.year <= ANO_MAX:
        raise regra(f'Informe uma data entre {ANO_MIN} e {ANO_MAX}.')
    return valor


Data = Annotated[date, AfterValidator(_data_na_faixa)]
"""Data informada pelo usuário (filtros, períodos), entre ANO_MIN e ANO_MAX."""

DataHora = Annotated[datetime, AfterValidator(_data_na_faixa)]
"""Data e hora informadas pelo usuário (sem fuso = horário da loja), entre ANO_MIN e ANO_MAX."""

NASCIMENTO_MIN = date(1900, 1, 1)
MSG_NASCIMENTO = 'Data de nascimento inválida (não pode ser no futuro nem antes de 1900).'
# Fuso mais adiantado do mundo (UTC+14): a data de "hoje" dele nunca fica atrás da de nenhuma loja
_FUSO_MAIS_ADIANTADO = timezone(timedelta(hours=14))


def nascimento_valido(valor: date, hoje_na_loja: date) -> bool:
    """Entre 1900 e hoje (no fuso da loja, GER-15)."""
    return NASCIMENTO_MIN <= valor <= hoje_na_loja


def _nascimento(valor: date | None) -> date | None:
    if valor is not None and not nascimento_valido(valor, datetime.now(_FUSO_MAIS_ADIANTADO).date()):
        raise regra(MSG_NASCIMENTO)
    return valor


DataNascimento = Annotated[date | None, BeforeValidator(vazio_para_none), AfterValidator(_nascimento)]
"""Data de nascimento (vazio = None). O schema não conhece a loja: barra o que é futuro em qualquer
lugar do mundo; a rota confere com o dia da loja (app.services.comum.conferir_nascimento)."""


# --- Documentos e contato --------------------------------------------------------------------------


def so_digitos(valor: str) -> str:
    return re.sub(r'\D', '', valor)


def cpf_valido(digitos: str) -> bool:
    """Confere os dígitos verificadores do CPF (11 dígitos)."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    numeros = [int(d) for d in digitos]
    for posicao in (9, 10):
        soma = sum(n * p for n, p in zip(numeros[:posicao], range(posicao + 1, 1, -1), strict=True))
        digito = (soma * 10) % 11 % 10
        if numeros[posicao] != digito:
            return False
    return True


def formatar_cpf(digitos: str) -> str:
    return f'{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}'


def _cpf(valor: Any) -> Any:
    """CPF com dígito verificador conferido, gravado sempre como 000.000.000-00 (vazio = None)."""
    if not isinstance(valor, str):
        return valor
    digitos = so_digitos(valor)
    if not digitos and not valor.strip():
        return None
    if not cpf_valido(digitos):
        raise regra('CPF inválido.')
    return formatar_cpf(digitos)


def formatar_telefone(digitos: str) -> str:
    return f'({digitos[:2]}) {digitos[2:-4]}-{digitos[-4:]}'


def _telefone(valor: Any) -> Any:
    """Telefone brasileiro com DDD (10 ou 11 dígitos), gravado com máscara: (11) 98888-1111."""
    if not isinstance(valor, str):
        return valor
    digitos = so_digitos(valor)
    if len(digitos) not in (10, 11) or digitos[0] == '0':
        raise regra('Informe o telefone com DDD (ex.: (11) 99999-9999).')
    return formatar_telefone(digitos)


def _telefone_opcional(valor: Any) -> Any:
    valor = vazio_para_none(valor)
    return None if valor is None else _telefone(valor)


Cpf = Annotated[
    str | None, BeforeValidator(_cpf), Field(description='Com ou sem máscara; sai 000.000.000-00')
]
Telefone = Annotated[
    str, BeforeValidator(_telefone), Field(description='Com DDD, com ou sem máscara; sai (11) 98888-1111')
]
TelefoneOpcional = Annotated[
    str | None,
    BeforeValidator(_telefone_opcional),
    Field(description='Com DDD, com ou sem máscara; sai (11) 98888-1111'),
]

# Valores numeric(10,2) saem como número no JSON (e não como texto, padrão do Pydantic para Decimal)
_COMO_NUMERO = PlainSerializer(float, return_type=float, when_used='json')
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2), _COMO_NUMERO]
# Uma movimentação (ou consumo por atendimento) tem no máximo QUANTIDADE_MAX; o saldo do material
# (numeric(10,2)) é conferido antes de gravar (app/services/estoque.py).
QUANTIDADE_MAX = Decimal('1000000')
Quantidade = Annotated[
    Decimal,
    Field(ge=-QUANTIDADE_MAX, le=QUANTIDADE_MAX, max_digits=10, decimal_places=2),
    _COMO_NUMERO,
]
QuantidadePositiva = Annotated[
    Decimal, Field(gt=0, le=QUANTIDADE_MAX, max_digits=10, decimal_places=2), _COMO_NUMERO
]
DecimalSaida = Annotated[Decimal, _COMO_NUMERO]


class Controle(Esquema):
    """Colunas de controle exibidas na tela (componente UltimaAlteracao do front).

    atualizado_por_nome: funcionário que fez a última alteração. None quando foi o superadmin, o
    site ou uma rotina automática (o front decide o texto a partir de ``origem``, quando houver).
    """

    criado_em: datetime
    atualizado_em: datetime
    atualizado_por: UUID | None = None
    atualizado_por_nome: str | None = None


class Referencia(Esquema):
    """Item de lista de apoio: só id e nome."""

    id: UUID
    nome: str
