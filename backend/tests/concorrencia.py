"""Rajadas de requisições simultâneas contra o servidor real (fixture ``servidor``).

Uma barreira solta todas as threads ao mesmo tempo; cada uma tem o seu cliente HTTP (conexão
própria com a API e, na API, transação própria no banco).
"""

import threading
from typing import Any

import httpx

Pedido = tuple[str, str, Any, dict[str, str] | None]  # método, caminho, corpo JSON, cabeçalhos


def rajada(url: str, pedidos: list[Pedido]) -> list[httpx.Response]:
    barreira = threading.Barrier(len(pedidos))
    respostas: list[httpx.Response | None] = [None] * len(pedidos)
    erros: list[BaseException] = []

    def enviar(i: int) -> None:
        metodo, caminho, corpo, cabecalhos = pedidos[i]
        try:
            with httpx.Client(base_url=url, timeout=60) as cliente:
                barreira.wait()
                respostas[i] = cliente.request(metodo, caminho, json=corpo, headers=cabecalhos)
        except BaseException as erro:  # repassado ao teste depois do join
            erros.append(erro)

    threads = [threading.Thread(target=enviar, args=(i,)) for i in range(len(pedidos))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if erros:
        raise erros[0]
    return [r for r in respostas if r is not None]
