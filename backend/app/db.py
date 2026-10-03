"""Engine, sessão e contexto da transação.

Cada requisição roda numa única transação. No início dela, quem está agindo é gravado com
set_config(..., true) (equivale a SET LOCAL): os triggers de alteração, exclusão lógica e
auditoria e as políticas de RLS leem esses valores. Fora da transação eles somem sozinhos.

Com uma loja no contexto, o fuso da transação (TimeZone) passa a ser o da loja: toda data/hora lida
do banco chega ao Python (e à resposta) no fuso da loja (GER-15), sem conversão rota a rota. Sem loja
(superadmin, rotinas), fica em UTC. Um fuso que o Postgres não conhece não derruba a requisição: vale
FUSO_PADRAO e o problema vai para o log.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.config import get_settings
from app.models.base import ControleMixin

Origem = Literal['painel', 'superadmin', 'site', 'sistema']

FUSO_PADRAO = 'America/Sao_Paulo'  # o mesmo default da coluna lojas.fuso_horario

log = logging.getLogger('app.db')

_fusos_do_banco: frozenset[str] | None = None


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url.get_secret_value()
    # hide_parameters: erros e logs do SQLAlchemy não mostram valores (CPF, telefone, senha...)
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


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
    login: bool = False,
) -> None:
    """Grava quem está agindo na transação atual (lido pelos triggers e pelo RLS).

    Sempre grava todos os valores (vazio = nenhum), para nada sobrar de um contexto anterior
    na mesma transação. Com ``loja_id``, o fuso da transação vira o da loja (sem loja, UTC; fuso que o
    Postgres não conhece, FUSO_PADRAO).

    login: a transação é um login. Os triggers não tratam como alteração (nem auditoria, nem
    "última alteração") o UPDATE que só muda ``ultimo_login_em`` e ``senha_hash`` (novo hash da
    mesma senha); qualquer outra coluna alterada continua auditada (migração 0004).
    """
    valores = {
        'funcionario_id': str(funcionario_id) if funcionario_id else '',
        'superadmin_id': str(superadmin_id) if superadmin_id else '',
        'loja_id': str(loja_id) if loja_id else '',
        'origem': origem,
        'ip': ip or '',
        'login': 'sim' if login else '',
    }
    fuso_da_loja = db.execute(
        text(
            "SELECT set_config('app.funcionario_id', :funcionario_id, true),"
            " set_config('app.superadmin_id', :superadmin_id, true),"
            " set_config('app.loja_id', :loja_id, true),"
            " set_config('app.origem', :origem, true),"
            " set_config('app.ip', :ip, true),"
            " set_config('app.login', :login, true),"
            " (SELECT l.fuso_horario FROM lojas l WHERE l.id = CAST(nullif(:loja_id, '') AS uuid))"
        ),
        valores,
    ).one()[-1]
    zona = 'UTC'
    if fuso_da_loja is not None:
        zona = fuso_da_loja
        if not fuso_conhecido_pelo_banco(db, fuso_da_loja):
            log.warning(
                'Loja %s com fuso desconhecido pelo banco (%r); usando %s', loja_id, fuso_da_loja, FUSO_PADRAO
            )
            zona = FUSO_PADRAO
    db.execute(text("SELECT set_config('TimeZone', :zona, true)"), {'zona': zona})


def fuso_conhecido_pelo_banco(db: Session, nome: str) -> bool:
    """O Postgres aceita ``nome`` como TimeZone (lista de pg_timezone_names, lida uma vez por processo)."""
    global _fusos_do_banco
    if _fusos_do_banco is None:
        _fusos_do_banco = frozenset(db.scalars(text('SELECT name FROM pg_timezone_names')))
    return nome in _fusos_do_banco


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
