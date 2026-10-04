"""Locais de atendimento e rótulos do menu (estrutura.md, 2.19 e 2.21)."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import TipoLocal
from app.schemas.comum import LISTA_MAX, Controle, Entrada, Referencia, regra, texto, texto_opcional


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
    servico_ids: list[UUID] | None = Field(
        default=None,
        max_length=LISTA_MAX,
        description='Serviços que acontecem aqui ([] = nenhum). Nulo = não muda. '
        'Ignorado com o módulo Serviços desligado.',
    )

    _link = field_validator('link_padrao')(validar_link)

    @field_validator('servico_ids')
    @classmethod
    def _sem_repetidos(cls, ids: list[UUID] | None) -> list[UUID] | None:
        return None if ids is None else list(dict.fromkeys(ids))

    @model_validator(mode='after')
    def _link_so_online(self) -> 'LocalEntrada':
        # Ao trocar de online para presencial, o link fixo deixa de valer
        if self.tipo == TipoLocal.presencial:
            self.link_padrao = None
        return self


class ServicoDoLocal(Referencia):
    ativo: bool


class LocalSaida(Controle):
    id: UUID
    nome: str
    tipo: TipoLocal
    link_padrao: str | None
    descricao: str | None
    ativo: bool
    servicos: list[ServicoDoLocal] = Field(
        default_factory=list,
        description='Serviços vinculados a este local (os sem vínculo aceitam qualquer local). '
        'Vazio com o módulo Serviços desligado.',
    )
    proximos_agendamentos: int = Field(default=0, description='Agendamentos ativos de hoje em diante')


class ServicoOpcaoLocal(ServicoDoLocal):
    locais_vinculados: int = Field(ge=0, description='Locais vinculados ao serviço hoje (0 = qualquer local)')


class OpcoesLocal(BaseModel):
    """Lista do formulário de local, sem exigir acesso a Serviços."""

    servicos: list[ServicoOpcaoLocal] | None = Field(description='Nulo = módulo Serviços desligado')


class RotulosEntrada(Entrada):
    rotulo_local: texto(40) = Field(description='Ex.: Sala, Cadeira, Consultório')
    rotulo_local_plural: texto(40) = Field(description='Ex.: Salas, Cadeiras, Consultórios')


class RotulosSaida(Controle):
    rotulo_local: str
    rotulo_local_plural: str
