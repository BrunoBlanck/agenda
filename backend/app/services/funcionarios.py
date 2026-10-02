"""Regras de funcionários usadas pelo painel da loja e pelo suporte do superadmin (estrutura.md, 2.4)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Funcionario, Perfil

MSG_ULTIMO_ADMIN = 'A loja precisa de pelo menos um Administrador ativo.'


def outros_admins_ativos(db: Session, loja_id: UUID, exceto: UUID) -> int:
    """Quantos Administradores ativos a loja tem além de ``exceto``."""
    return (
        db.scalar(
            select(func.count())
            .select_from(Funcionario)
            .join(Perfil, (Perfil.id == Funcionario.perfil_id) & (Perfil.loja_id == Funcionario.loja_id))
            .where(
                Funcionario.loja_id == loja_id,
                Funcionario.id != exceto,
                Funcionario.ativo,
                Funcionario.excluido_em.is_(None),
                Perfil.acesso_total,
                Perfil.excluido_em.is_(None),
            )
        )
        or 0
    )


def deixa_loja_sem_admin(
    db: Session, loja_id: UUID, atual: Funcionario, era_admin: bool, continua_admin: bool
) -> bool:
    """A alteração tira o último Administrador ativo da loja?"""
    return (
        era_admin and atual.ativo and not continua_admin and not outros_admins_ativos(db, loja_id, atual.id)
    )
