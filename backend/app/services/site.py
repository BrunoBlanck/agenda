"""Loja vista pelo público: usada pela API do site (/api/site/{slug}) e pelas páginas HTML (/{slug}).

Regra única de visibilidade (SIT-01): só a loja ativa aparece; inexistente, excluída, suspensa ou
cancelada é tratada como inexistente (404), sem dizer o motivo.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import definir_contexto
from app.models import Loja, LojaConfiguracao
from app.models.enums import StatusLoja
from app.schemas.site import LojaPublica
from app.services.slugs import endereco_de_loja


def carregar_loja_publica(db: Session, slug: str, ip: str | None) -> Loja | None:
    """Loja ativa do endereço, ou None. Deixa a transação no contexto do site e da loja (RLS)."""
    if not endereco_de_loja(slug):
        return None
    definir_contexto(db, origem='site', ip=ip)
    loja = db.scalar(select(Loja).where(Loja.slug == slug))
    if loja is None or loja.status != StatusLoja.ativa:
        return None
    # RLS: daqui em diante só enxerga os dados desta loja
    definir_contexto(db, origem='site', loja_id=loja.id, ip=ip)
    return loja


def configuracao_publica(db: Session, loja: Loja) -> LojaConfiguracao | None:
    """Configurações da loja que mudam o site (rótulo do local, cores), sem criar a linha se faltar."""
    return db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == loja.id))


def dados_publicos(
    db: Session, loja: Loja, modulos: dict[str, bool], configuracao: LojaConfiguracao | None = None
) -> LojaPublica:
    """Só o que o consumidor pode ver da loja (contato, endereço e o que muda o site).

    configuracao: a já lida por quem chama (``configuracao_publica``); se faltar, é lida aqui.
    """
    configuracao = configuracao or configuracao_publica(db, loja)
    return LojaPublica(
        tipo=loja.tipo,
        slug=loja.slug,
        nome_fantasia=loja.nome_fantasia or loja.nome,
        logo_url=loja.logo_url,
        telefone=loja.telefone,
        email=loja.email,
        logradouro=loja.logradouro,
        numero=loja.numero,
        complemento=loja.complemento,
        bairro=loja.bairro,
        cidade=loja.cidade,
        uf=loja.uf,
        fuso_horario=loja.fuso_horario,
        usa_servicos=modulos.get('servicos', False),
        usa_locais=modulos.get('locais', False),
        rotulo_local=configuracao.rotulo_local if configuracao else 'Local',
    )
