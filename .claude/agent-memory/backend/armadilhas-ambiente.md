---
name: armadilhas-ambiente
description: Armadilhas do ambiente Windows/Git Bash e do pytest neste backend (fim de linha, resumo do pytest, fuso de teste)
metadata:
  type: project
---

- `sed -i` no Git Bash regrava o arquivo inteiro com LF; vários .py do backend estão com CRLF (core.autocrlf=true), então o diff vira o arquivo todo. Edite com Edit/Write ou Python (`open(..., 'w')` mantém CRLF no Windows), nunca `sed -i`.
- `pyproject.toml` já tem `addopts = "-q"`; `pytest -q` vira `-qq` e some a linha "N passed". Sem F/E nos pontos = passou; para contar, `pytest --collect-only -q`.
- Testar "hoje no fuso da loja" de forma determinística: trocar `lojas.fuso_horario` para `Pacific/Pago_Pago` (UTC-11) e `Pacific/Kiritimati` (UTC+14) via `engine_dono`; não depende da hora em que o teste roda.
- Lista de fusos do Postgres fica em cache no processo (`app.db._fusos_do_banco`); nos testes, `monkeypatch.setattr('app.db._fusos_do_banco', frozenset(...))` simula um fuso que o PG não conhece.

**Why:** perdi tempo com um `sed -i` que reescreveu `servicos.py` inteiro e com o resumo do pytest sumindo.
**How to apply:** antes de editar por shell e ao ler a saída do pytest.
