"""Login e dados do usuário logado."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import NivelAcesso, TipoLoja
from app.schemas.comum import Esquema


class LoginLoja(BaseModel):
    slug: str = Field(min_length=1, max_length=60, description='Identificador da loja (ex.: clinica-sorriso)')
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class LoginSuperadmin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class Token(BaseModel):
    token: str
    tipo_token: str = 'bearer'  # noqa: S105 (não é senha)
    expira_em: datetime


class CargoResumo(Esquema):
    id: UUID
    nome: str


class FuncionarioEu(Esquema):
    id: UUID
    nome: str
    email: str
    telefone: str | None
    cor_agenda: str | None
    perfil_id: UUID
    cargo: CargoResumo | None = None


class PerfilEu(Esquema):
    id: UUID
    nome: str
    descricao: str | None
    padrao: bool
    acesso_total: bool


class LojaEu(Esquema):
    id: UUID
    tipo: TipoLoja
    slug: str
    nome: str
    nome_fantasia: str | None
    logo_url: str | None
    fuso_horario: str
    rotulo_local: str = 'Local'
    rotulo_local_plural: str = 'Locais'


class SessaoEu(BaseModel):
    suporte: bool = Field(description='Sessão aberta pelo SUPERADMIN em "Acessar loja" (PLA-17)')
    expira_em: datetime | None = Field(description='Quando o token vence, no fuso da loja')


class Eu(BaseModel):
    """O que o front precisa para montar o menu e esconder botões (ver useAcesso.js)."""

    funcionario: FuncionarioEu
    perfil: PerfilEu
    loja: LojaEu
    sessao: SessaoEu
    modulos: dict[str, bool] = Field(description='Todos os módulos do catálogo; true = ativo na loja')
    acessos: dict[str, NivelAcesso] = Field(
        description=(
            'Nível efetivo em cada recurso (módulo desligado = nenhum, inclusive para o Administrador)'
        )
    )


class SuperadminEu(Esquema):
    id: UUID
    nome: str
    email: str
