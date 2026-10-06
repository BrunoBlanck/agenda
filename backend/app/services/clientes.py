"""Busca de clientes, usada pela lista de Clientes e pelo formulário de agendamento."""

import re

from sqlalchemy import ColumnElement, func, or_

from app.models import Cliente
from app.schemas.comum import so_digitos

# Termo que parece telefone ou CPF: só dígitos e sinais de máscara
_PARECE_NUMERO = re.compile(r'[\d\s().\-/+]+', re.ASCII)


def _digitos_da_coluna(coluna: ColumnElement[str]) -> ColumnElement[str]:
    return func.regexp_replace(coluna, r'\D', '', 'g')


def _contem(termo: str, *colunas: ColumnElement[str]) -> list[ColumnElement[bool]]:
    """Coluna contendo o termo; com termo numérico, também só os dígitos (com ou sem máscara)."""
    condicoes = [coluna.icontains(termo, autoescape=True) for coluna in colunas]
    digitos = so_digitos(termo)
    if digitos and _PARECE_NUMERO.fullmatch(termo):
        condicoes += [_digitos_da_coluna(coluna).contains(digitos) for coluna in colunas]
    return condicoes


def _nome_completo() -> ColumnElement[str]:
    return func.concat(Cliente.nome, ' ', Cliente.sobrenome)


def filtro_busca(termo: str) -> ColumnElement[bool]:
    """Nome completo, CPF, telefone ou e-mail contendo o termo (lista de Clientes).

    Telefone e CPF são encontrados com ou sem máscara: "11988881111", "(11) 98888-1111" e
    "98888-1111" acham o mesmo cadastro.
    """
    return or_(
        _nome_completo().icontains(termo, autoescape=True),
        Cliente.email.icontains(termo, autoescape=True),
        *_contem(termo, Cliente.cpf, Cliente.telefone),
    )


def filtro_busca_apoio(termo: str) -> ColumnElement[bool]:
    """Só nome completo e telefone (com ou sem máscara): busca do formulário de agendamento.

    Quem usa essa busca pode não ter acesso a Clientes; por isso ela não casa CPF nem e-mail, que
    permitiriam descobrir se um documento ou endereço é cliente da loja (SEG-06).
    """
    return or_(_nome_completo().icontains(termo, autoescape=True), *_contem(termo, Cliente.telefone))
