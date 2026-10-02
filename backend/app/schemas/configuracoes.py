"""Configurações › Dados da loja (estrutura.md, 2.18)."""

import re
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.models.enums import StatusLoja, TipoLoja
from app.schemas.comum import EmailOpcional, Entrada, regra, texto, texto_opcional


def cnpj_valido(digitos: str) -> bool:
    """Confere os dígitos verificadores do CNPJ (14 dígitos)."""
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    numeros = [int(d) for d in digitos]
    for posicao in (12, 13):
        pesos = list(range(posicao - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(n * p for n, p in zip(numeros[:posicao], pesos, strict=True))
        digito = 0 if soma % 11 < 2 else 11 - soma % 11
        if numeros[posicao] != digito:
            return False
    return True


def _normalizar_cnpj(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    digitos = re.sub(r'\D', '', valor)
    if not digitos:
        return None
    if not cnpj_valido(digitos):
        raise regra('CNPJ inválido.')
    return f'{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}'


def _normalizar_cep(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    digitos = re.sub(r'\D', '', valor)
    if not digitos:
        return None
    if len(digitos) != 8:
        raise regra('CEP inválido.')
    return f'{digitos[:5]}-{digitos[5:]}'


class DadosLojaEntrada(Entrada):
    """Campos que a própria loja edita. tipo, slug, plano, status, fuso e módulos são do superadmin."""

    nome_fantasia: texto(150) = Field(description='Nome da loja')
    nome: texto(150) = Field(description='Razão social')
    cnpj: Annotated[str | None, BeforeValidator(_normalizar_cnpj)] = None
    telefone: texto_opcional(20) = None
    email: EmailOpcional = None
    cep: Annotated[str | None, BeforeValidator(_normalizar_cep)] = None
    logradouro: texto_opcional(150) = None
    numero: texto_opcional(10) = None
    complemento: texto_opcional(80) = None
    bairro: texto_opcional(80) = None
    cidade: texto_opcional(80) = None
    uf: texto_opcional(2) = None

    @field_validator('uf')
    @classmethod
    def _uf(cls, uf: str | None) -> str | None:
        if uf is None:
            return None
        if not re.fullmatch(r'[A-Za-z]{2}', uf):
            raise regra('UF inválida.')
        return uf.upper()


class DadosLoja(BaseModel):
    nome_fantasia: str | None
    nome: str
    cnpj: str | None
    telefone: str | None
    email: str | None
    cep: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
    logo_url: str | None
    # Definidos pela plataforma (só leitura aqui)
    tipo: TipoLoja
    slug: str
    plano_nome: str | None
    status: StatusLoja
    fuso_horario: str
    modulos: dict[str, bool] = Field(description='Módulos opcionais: ativo ou não')
    # Última alteração (UltimaAlteracao)
    atualizado_em: datetime
    atualizado_por: str | None = Field(description='funcionario, superadmin ou nulo (rotina)')
    atualizado_por_nome: str | None
