"""Configurações › Dados da loja (estrutura.md, 2.18)."""

import re
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.models.enums import StatusLoja, TipoLoja
from app.schemas.comum import Controle, EmailOpcional, Entrada, regra, texto, texto_opcional
from app.services.cores_site import MSG_CONTRASTE_COR, MSG_FORMATO_COR, legivel_com_branco, normalizar_cor


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


class DadosLoja(Controle):
    """Dados da loja com a última alteração (Controle).

    atualizado_por / atualizado_por_nome: o funcionário da loja que fez a última alteração; nulos
    quando foi o superadmin ou o sistema (GER-13), como nas demais rotas da loja.
    """

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
    logo_url: str | None = Field(
        description='URL da logo (/api/arquivos/logos/...), na mesma origem da API. Nulo = sem logo'
    )
    # Definidos pela plataforma (só leitura aqui)
    tipo: TipoLoja
    slug: str
    plano_nome: str | None
    status: StatusLoja
    fuso_horario: str
    modulos: dict[str, bool] = Field(description='Módulos opcionais: ativo ou não')


# --- Cores do site (SIT-13, SIT-14) ----------------------------------------------------------------


def _cor_do_site(valor: Any) -> Any:
    """null (ou vazio) = cor padrão do tipo; senão #RRGGBB (vira minúsculas) legível com texto branco."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    cor = normalizar_cor(valor) if isinstance(valor, str) else None
    if cor is None:
        raise regra(MSG_FORMATO_COR)
    if not legivel_com_branco(cor):
        raise regra(MSG_CONTRASTE_COR)
    return cor


CorDoSite = Annotated[
    str | None,
    BeforeValidator(_cor_do_site),
    Field(description='#RRGGBB (sai em minúsculas), contraste de 4,5:1 com o branco; null = padrão do tipo'),
]


class CoresSiteEntrada(Entrada):
    """As duas cores são obrigatórias no corpo (null = voltar ao padrão)."""

    cor_topo: CorDoSite
    cor_destaque: CorDoSite


class CoresPadrao(BaseModel):
    cor_topo: str
    cor_destaque: str


class CoresSite(Controle):
    """Cores do site do consumidor. atualizado_por / atualizado_por_nome: o funcionário que alterou por
    último; nulos quando foi o superadmin ou o sistema (GER-13)."""

    cor_topo: str | None = Field(description='null = cor padrão do tipo (padrao.cor_topo)')
    cor_destaque: str | None = Field(description='null = cor padrão do tipo (padrao.cor_destaque)')
    padrao: CoresPadrao = Field(description='Paleta do tipo da loja (voltar ao padrão e pré-visualização)')
    tipo: TipoLoja
