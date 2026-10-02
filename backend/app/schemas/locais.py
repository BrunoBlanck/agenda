"""Locais de atendimento e rótulos do menu (estrutura.md, 2.19 e 2.21)."""

from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.enums import TipoLocal
from app.schemas.comum import Controle, Entrada, Referencia, regra, texto, texto_opcional


def validar_link(link: str | None) -> str | None:
    if link is not None and not link.lower().startswith(('https://', 'http://')):
        raise regra('Informe um link válido (https://...).')
    return link


class LocalEntrada(Entrada):
    nome: texto(80)
    tipo: TipoLocal = TipoLocal.presencial
    link_padrao: texto_opcional(500) = Field(default=None, description='Só para local online: link fixo')
    descricao: texto_opcional() = None
    ativo: bool = True

    _link = field_validator('link_padrao')(validar_link)

    @model_validator(mode='after')
    def _link_so_online(self) -> 'LocalEntrada':
        # Ao trocar de online para presencial, o link fixo deixa de valer
        if self.tipo == TipoLocal.presencial:
            self.link_padrao = None
        return self


class LocalSaida(Controle):
    id: UUID
    nome: str
    tipo: TipoLocal
    link_padrao: str | None
    descricao: str | None
    ativo: bool
    servicos: list[Referencia] = Field(
        default_factory=list,
        description='Serviços que citam este local (os sem vínculo aceitam qualquer local)',
    )
    proximos_agendamentos: int = Field(default=0, description='Agendamentos ativos de hoje em diante')


class RotulosEntrada(Entrada):
    rotulo_local: texto(40) = Field(description='Ex.: Sala, Cadeira, Consultório')
    rotulo_local_plural: texto(40) = Field(description='Ex.: Salas, Cadeiras, Consultórios')


class RotulosSaida(Controle):
    rotulo_local: str
    rotulo_local_plural: str
