"""Configurações da loja que não são dados cadastrais (``loja_configuracoes``, estrutura.md 2.21).

Usado pelo painel da loja (rótulos dos locais, cores do site) e pelo SUPERADMIN (cores do site, PLA-20).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Loja, LojaConfiguracao
from app.schemas.configuracoes import CoresPadrao, CoresSite, CoresSiteEntrada
from app.services.comum import fuso, nomes_funcionarios
from app.services.cores_site import paleta_do_tipo


def configuracao_da_loja(db: Session, loja_id: UUID) -> LojaConfiguracao:
    """Configurações da loja (toda loja nasce com uma; recria se faltar)."""
    configuracao = db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == loja_id))
    if configuracao is None:
        configuracao = LojaConfiguracao(loja_id=loja_id)
        db.add(configuracao)
        db.flush()
    return configuracao


def cores_do_site(db: Session, loja: Loja) -> CoresSite:
    """Cores escolhidas (nulas = padrão), a paleta do tipo e a última alteração, no fuso da loja.

    atualizado_por / atualizado_por_nome: o funcionário que alterou por último; nulos quando foi o
    superadmin ou o sistema (GER-13; quem foi fica na auditoria).
    """
    configuracao = configuracao_da_loja(db, loja.id)
    paleta = paleta_do_tipo(loja.tipo)
    zona = fuso(loja.fuso_horario)
    autor = configuracao.atualizado_por
    return CoresSite(
        cor_topo=configuracao.cor_site_topo,
        cor_destaque=configuracao.cor_site_destaque,
        padrao=CoresPadrao(cor_topo=paleta.topo, cor_destaque=paleta.destaque),
        tipo=loja.tipo,
        criado_em=configuracao.criado_em.astimezone(zona),
        atualizado_em=configuracao.atualizado_em.astimezone(zona),
        atualizado_por=autor,
        atualizado_por_nome=nomes_funcionarios(db, loja.id, [autor]).get(autor) if autor else None,
    )


def salvar_cores_do_site(db: Session, loja: Loja, dados: CoresSiteEntrada) -> CoresSite:
    """Grava as cores já validadas (formato e contraste na ``CoresSiteEntrada``). A mesma cor de novo
    não muda nada (nem a última alteração)."""
    configuracao = configuracao_da_loja(db, loja.id)
    if configuracao.cor_site_topo != dados.cor_topo:
        configuracao.cor_site_topo = dados.cor_topo
    if configuracao.cor_site_destaque != dados.cor_destaque:
        configuracao.cor_site_destaque = dados.cor_destaque
    db.flush()
    return cores_do_site(db, loja)
