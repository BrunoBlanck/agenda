"""Tarefa de fundo das notificações no processo da API (NOT-07).

Ligada no ``lifespan`` da aplicação quando ``Settings.tarefa_de_notificacoes`` (padrão: fora de
``AMBIENTE=teste``; ``NOTIFICACOES_TAREFA=false`` desliga). A cada ``NOTIFICACOES_INTERVALO`` segundos roda
um ciclo de ``app.services.tarefa_notificacoes.processar`` numa thread (o SMTP bloqueia; o laço de eventos
da API não). Vários processos (workers, réplicas) podem rodar ao mesmo tempo: a reserva com
``SKIP LOCKED`` e o índice único do lembrete evitam e-mail e lembrete repetidos.

Para rodar fora da API (outro contêiner, cron): ``python -m scripts.notificacoes`` (``--uma-vez``).
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import get_settings
from app.services.tarefa_notificacoes import DESPACHANTE, processar

log = logging.getLogger('app.notificacoes')


def um_ciclo() -> None:
    """Um ciclo protegido: erro inesperado vai para o log e o próximo ciclo tenta de novo."""
    try:
        ciclo = processar()
    except Exception:
        log.exception('Falha no ciclo das notificações')
        return
    if ciclo.lembretes or ciclo.enviados or ciclo.falhas:
        log.info(
            'Notificações: %s lembrete(s), %s e-mail(s) enviado(s), %s falha(s)',
            ciclo.lembretes,
            ciclo.enviados,
            ciclo.falhas,
        )


async def rodar_para_sempre(intervalo: int) -> None:
    while True:
        await asyncio.to_thread(um_ciclo)
        await asyncio.sleep(intervalo)


@contextlib.asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    tarefa = None
    if settings.tarefa_de_notificacoes:
        tarefa = asyncio.create_task(rodar_para_sempre(settings.notificacoes_intervalo))
    try:
        yield
    finally:
        if tarefa is not None:
            tarefa.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarefa
            DESPACHANTE.encerrar()
