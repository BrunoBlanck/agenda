"""Acessar loja pelo SUPERADMIN (PLA-17 a PLA-19, estrutura.md 6.5).

O superadmin recebe um token de funcionário do **Administrador** da loja, com a claim ``suporte`` e
validade fixa de 1 hora. Na sessão, tudo fica registrado como o Administrador (decisão do usuário); o ato
de gerar o acesso fica na auditoria da loja como ação do superadmin (PLA-14). Não é um login do
Administrador: ``ultimo_login_em`` não muda.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import criar_token
from app.db import definir_contexto
from app.models import Funcionario, Loja, Perfil
from app.services.auditoria import registrar_acao
from app.services.comum import conflito

MSG_SEM_ADMIN = 'Esta loja não tem um Administrador ativo para acessar.'


@dataclass(frozen=True)
class AcessoSuporte:
    token: str
    expira_em: datetime  # UTC
    funcionario: Funcionario


def administrador_da_loja(db: Session, loja_id: UUID) -> Funcionario | None:
    """Funcionário ativo com o perfil Administrador padrão, o mais antigo (PLA-17)."""
    return db.scalar(
        select(Funcionario)
        .join(Perfil, (Perfil.loja_id == Funcionario.loja_id) & (Perfil.id == Funcionario.perfil_id))
        .where(
            Funcionario.loja_id == loja_id,
            Funcionario.ativo.is_(True),
            Perfil.padrao.is_(True),
            Perfil.acesso_total.is_(True),
        )
        .order_by(Funcionario.criado_em, Funcionario.id)
        .limit(1)
    )


def abrir_acesso_suporte(db: Session, loja: Loja, superadmin_id: UUID, ip: str | None) -> AcessoSuporte:
    """Gera a sessão de suporte da ``loja`` (ativa, suspensa ou cancelada; a excluída nem chega aqui)."""
    # Contexto do superadmin já com a loja: RLS da loja e a linha da auditoria com o loja_id certo
    definir_contexto(db, origem='superadmin', superadmin_id=superadmin_id, loja_id=loja.id, ip=ip)
    admin = administrador_da_loja(db, loja.id)
    if admin is None:
        raise conflito(MSG_SEM_ADMIN)
    registrar_acao(
        db,
        loja_id=loja.id,
        tabela='funcionarios',
        registro_id=str(admin.id),
        # ``nome`` dá o rótulo da linha na tela de auditoria; o histórico mostra só a ação
        depois={'acao': 'acessar_loja', 'como_funcionario': admin.nome, 'nome': admin.nome},
        campos=['acao', 'como_funcionario'],
    )
    token, expira_em = criar_token(admin.id, 'funcionario', loja.id, suporte=True)
    return AcessoSuporte(token=token, expira_em=expira_em, funcionario=admin)
