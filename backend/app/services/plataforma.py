"""Consultas da Plataforma (SUPERADMIN): lojas, módulos, planos e quem alterou (estrutura.md, seção 1)."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import (
    Auditoria,
    Funcionalidade,
    Funcionario,
    Loja,
    LojaFuncionalidade,
    Plano,
    SuperadminUsuario,
)
from app.models.enums import StatusLoja
from app.services.comum import nao_encontrado

MSG_LOJA_404 = 'Loja não encontrada.'
MSG_PLANO_404 = 'Plano não encontrado.'

Autor = Literal['funcionario', 'superadmin'] | None


def buscar_loja(db: Session, loja_id: UUID) -> Loja:
    loja = db.scalar(select(Loja).where(Loja.id == loja_id))
    if loja is None:
        raise nao_encontrado(MSG_LOJA_404)
    return loja


def nomes_superadmins(db: Session, ids: Iterable[UUID | None]) -> dict[UUID, str]:
    """Nome de cada superadmin (inclusive excluídos, para histórico)."""
    alvo = {i for i in ids if i is not None}
    if not alvo:
        return {}
    return dict(
        db.execute(
            select(SuperadminUsuario.id, SuperadminUsuario.nome)
            .where(SuperadminUsuario.id.in_(alvo))
            .execution_options(incluir_excluidos=True)
        ).all()
    )


def ultima_alteracao_loja(db: Session, loja_id: UUID) -> tuple[Autor, str | None]:
    """Quem fez a última alteração em ``lojas``: a auditoria diz se foi a loja ou o superadmin.

    (``lojas`` guarda as duas colunas ``atualizado_por_*`` sem dizer qual foi a última.)
    """
    ultima = db.execute(
        select(Auditoria.funcionario_id, Auditoria.superadmin_id)
        .where(Auditoria.loja_id == loja_id, Auditoria.tabela == 'lojas')
        .order_by(Auditoria.id.desc())
        .limit(1)
    ).first()
    if ultima is not None and ultima.funcionario_id:
        nome = db.scalar(
            select(Funcionario.nome)
            .where(Funcionario.id == ultima.funcionario_id, Funcionario.loja_id == loja_id)
            .execution_options(incluir_excluidos=True)
        )
        return 'funcionario', nome
    if ultima is not None and ultima.superadmin_id:
        return 'superadmin', nomes_superadmins(db, [ultima.superadmin_id]).get(ultima.superadmin_id)
    return None, None


def modulos_opcionais_por_loja(
    db: Session, loja_ids: Iterable[UUID], agora: datetime | None = None
) -> dict[UUID, dict[str, bool]]:
    """Módulos opcionais ativos de cada loja (mesma regra de app.services.acesso.modulos_da_loja)."""
    ids = list(set(loja_ids))
    agora = agora or datetime.now(UTC)
    opcionais = list(db.execute(select(Funcionalidade.codigo).where(Funcionalidade.opcional)).scalars())
    resultado = {loja_id: dict.fromkeys(opcionais, False) for loja_id in ids}
    if not ids:
        return resultado
    linhas = db.execute(
        select(LojaFuncionalidade.loja_id, Funcionalidade.codigo)
        .join(Funcionalidade, Funcionalidade.id == LojaFuncionalidade.funcionalidade_id)
        .where(
            LojaFuncionalidade.loja_id.in_(ids),
            LojaFuncionalidade.habilitado,
            Funcionalidade.opcional,
            Funcionalidade.ativo,
            (LojaFuncionalidade.expira_em.is_(None)) | (LojaFuncionalidade.expira_em > agora),
        )
    ).all()
    for loja_id, codigo in linhas:
        resultado[loja_id][codigo] = True
    return resultado


def funcionarios_ativos_por_loja(db: Session, loja_ids: Iterable[UUID]) -> dict[UUID, int]:
    ids = list(set(loja_ids))
    if not ids:
        return {}
    return dict(
        db.execute(
            select(Funcionario.loja_id, func.count())
            .where(Funcionario.loja_id.in_(ids), Funcionario.ativo, Funcionario.excluido_em.is_(None))
            .group_by(Funcionario.loja_id)
        ).all()
    )


def nomes_planos(db: Session, ids: Iterable[UUID | None]) -> dict[UUID, str]:
    alvo = {i for i in ids if i is not None}
    if not alvo:
        return {}
    return dict(
        db.execute(
            select(Plano.id, Plano.nome).where(Plano.id.in_(alvo)).execution_options(incluir_excluidos=True)
        ).all()
    )


def lojas_ativas_por_plano(db: Session) -> dict[UUID, int]:
    return dict(
        db.execute(
            select(Loja.plano_id, func.count())
            .where(
                and_(Loja.status == StatusLoja.ativa, Loja.plano_id.is_not(None), Loja.excluido_em.is_(None))
            )
            .group_by(Loja.plano_id)
        ).all()
    )
