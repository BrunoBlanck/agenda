"""Plataforma (SUPERADMIN): lojas, módulos, funcionários pelo suporte, planos, usuários admin e auditoria."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, PlainSerializer, field_validator

from app.auth.catalogo import MODULOS
from app.models.enums import OperacaoAuditoria, OrigemAuditoria, StatusLoja, TipoLoja
from app.schemas.comum import (
    LISTA_MAX,
    DataHora,
    DecimalSaida,
    Dinheiro,
    Entrada,
    Esquema,
    TelefoneOpcional,
    regra,
    texto,
    texto_opcional,
)
from app.schemas.configuracoes import DadosLojaEntrada
from app.schemas.funcionarios import Senha

SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

# Fuso das telas da plataforma (planos, usuários admin, ações recentes) e da auditoria da "plataforma".
# O que é de uma loja sai no fuso dela (GER-15); o front mostra o horário como veio.
FUSO_PLATAFORMA = 'America/Sao_Paulo'
ZONA_PLATAFORMA = ZoneInfo(FUSO_PLATAFORMA)


def _na_plataforma(momento: datetime) -> datetime:
    return momento.astimezone(ZONA_PLATAFORMA) if momento.tzinfo is not None else momento


MomentoPlataforma = Annotated[
    datetime, PlainSerializer(_na_plataforma, return_type=datetime, when_used='json')
]


def _slug(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    slug = valor.strip().lower()
    if not 2 <= len(slug) <= 60 or not SLUG.fullmatch(slug):
        raise regra('Use de 2 a 60 caracteres: letras minúsculas, números e hífens (ex.: clinica-sorriso).')
    return slug


MSG_FUSO = 'Fuso horário inválido (ex.: America/Sao_Paulo).'


def _fuso(valor: Any) -> Any:
    """Fuso conhecido pelo Python. A rota confere também com o Postgres (pg_timezone_names)."""
    if not isinstance(valor, str):
        return valor
    try:
        if valor not in available_timezones():
            raise ZoneInfoNotFoundError(valor)
        ZoneInfo(valor)
    except (ZoneInfoNotFoundError, ValueError):
        raise regra(MSG_FUSO) from None
    return valor


Slug = Annotated[str, BeforeValidator(_slug)]
Fuso = Annotated[str, BeforeValidator(_fuso)]


class SenhaProvisoria(BaseModel):
    senha_provisoria: str | None = Field(
        default=None,
        description=(
            'Só quando a senha foi gerada pelo sistema (nenhuma senha enviada). Mostre uma vez ao '
            'superadmin para repassar ao usuário: ainda não há envio de e-mail.'
        ),
    )


# --- Lojas ---------------------------------------------------------------------------------------


class LojaEntrada(DadosLojaEntrada):
    """Dados da loja editados pelo superadmin (os da própria loja e os da plataforma)."""

    tipo: TipoLoja = Field(description='Define o site do consumidor')
    slug: Slug = Field(description='Endereço de acesso (único entre as lojas não excluídas)')
    plano_id: UUID
    fuso_horario: Fuso = 'America/Sao_Paulo'


class AdminInicial(Entrada):
    nome: texto(150)
    email: EmailStr = Field(description='E-mail de login do primeiro Administrador')
    senha: Senha | None = Field(default=None, description='Vazia = o sistema gera uma senha provisória')


class LojaCriacao(LojaEntrada):
    modulos: list[str] = Field(
        default_factory=list,
        max_length=LISTA_MAX,
        description='Códigos dos módulos opcionais que a loja vai usar (servicos, materiais, ...)',
    )
    admin: AdminInicial
    rotulo_local: texto(40) = 'Local'
    rotulo_local_plural: texto(40) = 'Locais'

    @field_validator('modulos')
    @classmethod
    def _modulos(cls, modulos: list[str]) -> list[str]:
        opcionais = {codigo for codigo, opcional in MODULOS.items() if opcional}
        if set(modulos) - opcionais:
            raise regra(f'Módulo inválido. Opções: {", ".join(sorted(opcionais))}.')
        return list(dict.fromkeys(modulos))


class LojaEdicao(LojaEntrada):
    status: StatusLoja | None = Field(default=None, description='Vazio = mantém a situação atual')


class StatusEntrada(Entrada):
    status: StatusLoja


class LojaResumo(Esquema):
    id: UUID
    tipo: TipoLoja
    slug: str
    nome: str
    nome_fantasia: str | None
    logo_url: str | None
    cidade: str | None
    uf: str | None
    status: StatusLoja
    plano_id: UUID | None
    plano_nome: str | None = None
    modulos: dict[str, bool] = Field(default_factory=dict, description='Módulos opcionais: ativo ou não')
    funcionarios_ativos: int = 0
    criado_em: datetime


class LojaOpcao(Esquema):
    id: UUID
    nome_fantasia: str | None
    nome: str
    slug: str
    status: StatusLoja


class LojaDetalhe(LojaResumo):
    cnpj: str | None
    email: str | None
    telefone: str | None
    cep: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    fuso_horario: str
    rotulo_local: str = 'Local'
    rotulo_local_plural: str = 'Locais'
    atualizado_em: datetime
    atualizado_por: str | None = Field(default=None, description='funcionario, superadmin ou nulo (rotina)')
    atualizado_por_nome: str | None = None


# --- Módulos da loja -----------------------------------------------------------------------------


class ModuloLoja(BaseModel):
    codigo: str
    nome: str
    descricao: str | None
    opcional: bool
    habilitado: bool = Field(description='Ligado pelo superadmin (módulo base: sempre true)')
    ativo: bool = Field(description='Efetivo: ligado e dentro do prazo')
    observacao: str | None = None
    expira_em: datetime | None = None
    atualizado_em: datetime | None = None
    atualizado_por_nome: str | None = Field(default=None, description='Superadmin da última alteração')


class ModuloEntrada(Entrada):
    """Só os campos enviados mudam (o front altera um de cada vez)."""

    habilitado: bool | None = None
    observacao: texto_opcional(500) = None
    expira_em: DataHora | None = Field(
        default=None, description='Sem fuso = horário da loja. Nulo = sem prazo'
    )


# --- Funcionários pelo suporte -------------------------------------------------------------------


class FuncionarioSuporteEdicao(Entrada):
    nome: texto(150)
    email: EmailStr
    perfil_id: UUID
    telefone: TelefoneOpcional = None
    ativo: bool = True


class FuncionarioSuporteCriacao(FuncionarioSuporteEdicao):
    senha: Senha | None = Field(default=None, description='Vazia = o sistema gera uma senha provisória')


class FuncionarioSuporte(Esquema):
    id: UUID
    nome: str
    email: str
    perfil_id: UUID
    perfil_nome: str | None = None
    perfil_acesso_total: bool = False
    telefone: str | None
    ativo: bool
    ultimo_login_em: datetime | None
    criado_por: Literal['loja', 'superadmin'] | None = None
    criado_em: datetime
    atualizado_em: datetime


class FuncionarioSuporteCriado(FuncionarioSuporte, SenhaProvisoria):
    pass


class LojaCriada(LojaDetalhe, SenhaProvisoria):
    admin: FuncionarioSuporte


class RedefinirSenha(Entrada):
    senha: Senha | None = Field(default=None, description='Vazia = o sistema gera uma senha provisória')


class SenhaRedefinida(SenhaProvisoria):
    mensagem: str


class PerfilOpcao(Esquema):
    id: UUID
    nome: str
    acesso_total: bool


# --- Planos --------------------------------------------------------------------------------------


class PlanoEntrada(Entrada):
    nome: texto(80)
    descricao: texto_opcional() = None
    preco_mensal: Dinheiro
    ativo: bool = True


class PlanoSaida(Esquema):
    id: UUID
    nome: str
    descricao: str | None
    preco_mensal: DecimalSaida
    ativo: bool
    lojas_ativas: int = 0
    criado_em: MomentoPlataforma
    atualizado_em: MomentoPlataforma


# --- Usuários admin ------------------------------------------------------------------------------


class SuperadminEntrada(Entrada):
    nome: texto(150)
    email: EmailStr
    ativo: bool = True
    senha: Senha | None = Field(
        default=None, description='No cadastro: vazia = senha provisória gerada. Na edição: troca a senha.'
    )


class SuperadminSaida(Esquema):
    id: UUID
    nome: str
    email: str
    ativo: bool
    ultimo_login_em: MomentoPlataforma | None
    criado_em: MomentoPlataforma
    atualizado_em: MomentoPlataforma
    voce: bool = Field(default=False, description='É o usuário logado')


class SuperadminCriado(SuperadminSaida, SenhaProvisoria):
    pass


# --- Auditoria e visão geral ---------------------------------------------------------------------

Periodo = Literal['hoje', '7d', '30d', '90d', 'ano', 'intervalo']
TipoQuem = Literal['funcionario', 'superadmin', 'site', 'sistema']


class Quem(BaseModel):
    tipo: TipoQuem
    id: UUID | None = None
    nome: str
    chave: str = Field(description='Valor para o filtro "quem" (f:<id>, s:<id>, site ou sistema)')


class Mudanca(BaseModel):
    campo: str
    antes: Any = None
    depois: Any = None


class AuditoriaItem(BaseModel):
    id: int
    criado_em: datetime
    loja_id: UUID | None
    tabela: str
    tabela_nome: str
    registro_id: str
    rotulo: str = Field(description='Descrição curta do registro (nome, data...)')
    operacao: OperacaoAuditoria
    origem: OrigemAuditoria
    quem: Quem
    mudancas: list[Mudanca] = Field(description='Só em "alterar": campo, antes e depois')
    antes: dict[str, Any] | None
    depois: dict[str, Any] | None


class TabelasAuditoria(BaseModel):
    loja: dict[str, str]
    plataforma: dict[str, str]


class AcaoRecente(BaseModel):
    id: int
    criado_em: MomentoPlataforma
    tabela: str
    tabela_nome: str
    operacao: OperacaoAuditoria
    superadmin_id: UUID | None
    superadmin_nome: str | None
    loja_id: UUID | None
    loja_nome: str | None


class ModuloEmUso(BaseModel):
    codigo: str
    nome: str
    lojas: int = Field(description='Lojas ativas que usam o módulo')


class ModuloExpirando(BaseModel):
    loja_id: UUID
    loja_nome: str
    codigo: str
    nome: str
    expira_em: datetime = Field(description='No fuso da loja')
    vencido: bool = Field(description='O prazo já passou (o módulo está ligado, mas sem efeito)')


class VisaoGeral(BaseModel):
    lojas_ativas: int
    lojas_suspensas: int
    lojas_canceladas: int
    funcionarios_ativos: int = Field(description='Funcionários ativos das lojas ativas')
    receita_mensal: DecimalSaida = Field(description='Soma do preço dos planos das lojas ativas')
    lojas_por_tipo: dict[TipoLoja, dict[StatusLoja, int]]
    modulos_em_uso: list[ModuloEmUso]
    modulos_expirando: list[ModuloExpirando] = Field(
        default_factory=list,
        description='Módulos ligados em lojas ativas com prazo vencido ou que vence nos próximos 30 dias',
    )
    ultimas_acoes: list[AcaoRecente]
