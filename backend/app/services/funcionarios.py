"""Regras de funcionários usadas pelo painel da loja e pelo suporte do superadmin (estrutura.md, 2.4)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Funcionario, Perfil

MSG_ULTIMO_ADMIN = 'A loja precisa de pelo menos um Administrador ativo.'


def outros_admins_ativos(db: Session, loja_id: UUID, exceto: UUID) -> int:
    """Quantos Administradores ativos a loja tem além de ``exceto``.

    Trava (FOR UPDATE) os Administradores ativos da loja, sempre na mesma ordem: duas alterações
    simultâneas (dois admins se desativando, ou o superadmin e a loja ao mesmo tempo) são
    serializadas, e a segunda já vê o resultado da primeira (LOG-02).
    """
    ids = db.scalars(
        select(Funcionario.id)
        .join(Perfil, (Perfil.id == Funcionario.perfil_id) & (Perfil.loja_id == Funcionario.loja_id))
        .where(
            Funcionario.loja_id == loja_id,
            Funcionario.ativo,
            Funcionario.excluido_em.is_(None),
            Perfil.acesso_total,
            Perfil.excluido_em.is_(None),
        )
        .order_by(Funcionario.id)
        .with_for_update(of=Funcionario)
    ).all()
    return sum(1 for i in ids if i != exceto)


def deixa_loja_sem_admin(
    db: Session, loja_id: UUID, atual: Funcionario, era_admin: bool, continua_admin: bool
) -> bool:
    """A alteração tira o último Administrador ativo da loja?"""
    return (
        era_admin and atual.ativo and not continua_admin and not outros_admins_ativos(db, loja_id, atual.id)
    )
