"""Engine, sessão e contexto da transação.

Cada requisição roda numa única transação. No início dela, quem está agindo é gravado com
set_config(..., true) (equivale a SET LOCAL): os triggers de alteração, exclusão lógica e
auditoria e as políticas de RLS leem esses valores. Fora da transação eles somem sozinhos.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.config import get_settings
from app.models.base import ControleMixin

Origem = Literal['painel', 'superadmin', 'site', 'sistema']


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url.get_secret_value()
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    # expire_on_commit=False: a resposta é montada depois do commit
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=True)


def definir_contexto(
    db: Session,
    *,
    origem: Origem,
    funcionario_id: UUID | None = None,
    superadmin_id: UUID | None = None,
    loja_id: UUID | None = None,
    ip: str | None = None,
) -> None:
    """Grava quem está agindo na transação atual (lido pelos triggers e pelo RLS).

    Sempre grava todos os valores (vazio = nenhum), para nada sobrar de um contexto anterior
    na mesma transação.
    """
    valores = {
        'funcionario_id': str(funcionario_id) if funcionario_id else '',
        'superadmin_id': str(superadmin_id) if superadmin_id else '',
        'loja_id': str(loja_id) if loja_id else '',
        'origem': origem,
        'ip': ip or '',
    }
    db.execute(
        text(
            "SELECT set_config('app.funcionario_id', :funcionario_id, true),"
            " set_config('app.superadmin_id', :superadmin_id, true),"
            " set_config('app.loja_id', :loja_id, true),"
            " set_config('app.origem', :origem, true),"
            " set_config('app.ip', :ip, true)"
        ),
        valores,
    )


def sessao() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão com transação aberta; commit no fim, rollback em erro.

    Use com Depends(sessao, scope='function') (ver app.auth.dependencias) para o commit
    acontecer antes de a resposta ser enviada.
    """
    with get_sessionmaker()() as db, db.begin():
        yield db


@event.listens_for(Session, 'do_orm_execute')
def _ocultar_excluidos(estado: ORMExecuteState) -> None:
    """Toda leitura pelo ORM ignora linhas excluídas logicamente (excluido_em preenchido).

    Para ler também as excluídas (auditoria, restaurar vínculo), use
    .execution_options(incluir_excluidos=True).
    """
    if (
        estado.is_select
        and not estado.is_column_load
        and not estado.is_relationship_load
        and not estado.execution_options.get('incluir_excluidos', False)
    ):
        estado.statement = estado.statement.options(
            with_loader_criteria(
                ControleMixin,
                lambda cls: cls.excluido_em.is_(None),
                include_aliases=True,
            )
        )
