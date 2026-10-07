"""Avisos do cliente no site (SIT-25, NOT-06): o sino da conta.

A conta segue o telefone (SIT-16): vê as notificações ``tipo = cliente`` de **todos os clientes da loja
com o telefone da conta** (não excluídos), nunca as de outro telefone ou de outra loja.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session

from app.models import Cliente, Notificacao
from app.services.agendamento_site import filtro_telefone
from app.services.notificacoes import NAO_VISUALIZADA, TIPO_CLIENTE, VISUALIZADA

AVISOS_POR_PAGINA = 20


@dataclass(frozen=True)
class Aviso:
    id: UUID
    titulo: str
    mensagem: str
    criado_em: datetime
    novo: bool  # ainda não visualizado quando a página foi montada


@dataclass(frozen=True)
class PaginaDeAvisos:
    avisos: list[Aviso]
    total: int
    pagina: int
    paginas: int


def _da_conta(loja_id: UUID, digitos: str) -> list[ColumnElement[bool]]:
    clientes = select(Cliente.id).where(filtro_telefone(loja_id, digitos), Cliente.excluido_em.is_(None))
    return [
        Notificacao.loja_id == loja_id,
        Notificacao.tipo == TIPO_CLIENTE,
        Notificacao.cliente_id.in_(clientes.scalar_subquery()),
        Notificacao.excluido_em.is_(None),
    ]


def avisos_nao_lidos(db: Session, loja_id: UUID, digitos: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notificacao)
            .where(*_da_conta(loja_id, digitos), Notificacao.status_site == NAO_VISUALIZADA)
        )
        or 0
    )


def abrir_avisos(
    db: Session, loja_id: UUID, digitos: str, pagina: int, *, marcar: bool = True
) -> PaginaDeAvisos:
    """Uma página (mais novos primeiro) e, depois de montá-la, marca os dela como visualizados (NOT-06).

    Página fora do intervalo vira a primeira. Os que chegarem depois continuam não visualizados.
    """
    filtro = _da_conta(loja_id, digitos)
    total = db.scalar(select(func.count()).select_from(Notificacao).where(*filtro)) or 0
    paginas = max(1, -(-total // AVISOS_POR_PAGINA))
    if not 1 <= pagina <= paginas:
        pagina = 1
    linhas = db.scalars(
        select(Notificacao)
        .where(*filtro)
        .order_by(Notificacao.criado_em.desc(), Notificacao.id.desc())
        .limit(AVISOS_POR_PAGINA)
        .offset((pagina - 1) * AVISOS_POR_PAGINA)
    ).all()
    avisos = [
        Aviso(
            id=n.id,
            titulo=n.titulo,
            mensagem=n.mensagem,
            criado_em=n.criado_em,
            novo=n.status_site == NAO_VISUALIZADA,
        )
        for n in linhas
    ]
    novos = [a.id for a in avisos if a.novo]
    if novos and marcar:
        db.execute(
            update(Notificacao)
            .where(*filtro, Notificacao.id.in_(novos), Notificacao.status_site == NAO_VISUALIZADA)
            .values(status_site=VISUALIZADA, visualizada_em=func.now())
            .execution_options(synchronize_session=False)
        )
    return PaginaDeAvisos(avisos=avisos, total=total, pagina=pagina, paginas=paginas)
