"""Tarefa de fundo das notificações fora do processo da API (NOT-07): lembretes e e-mails pendentes.

Uso (na pasta backend/):
    uv run python -m scripts.notificacoes            # a cada NOTIFICACOES_INTERVALO segundos, até Ctrl+C
    uv run python -m scripts.notificacoes --uma-vez  # um ciclo só (ex.: cron)

Pode rodar junto com a tarefa da API (``NOTIFICACOES_TAREFA``): a reserva com SKIP LOCKED e o índice
único do lembrete evitam e-mail e lembrete repetidos. Para deixar só este processo,
``NOTIFICACOES_TAREFA=false`` na API.
"""

import argparse
import logging
import time

from app.config import get_settings
from app.tarefas import um_ciclo


def main() -> None:
    parser = argparse.ArgumentParser(description='Envia os e-mails pendentes e cria os lembretes.')
    parser.add_argument('--uma-vez', action='store_true', help='roda um ciclo e sai')
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    if argumentos.uma_vez:
        um_ciclo()
        return
    intervalo = get_settings().notificacoes_intervalo
    try:
        while True:
            um_ciclo()
            time.sleep(intervalo)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
