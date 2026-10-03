---
name: armadilhas-ambiente-e-fuso
description: Armadilhas do back-end - uvicorn --reload trava no Windows; TimeZone da sessão do Postgres é o fuso da loja (afeta casts de data em SQL e o JSON da auditoria)
metadata:
  type: project
---

1. **uvicorn --reload trava no Windows (visto em 2026-10-02).** O processo do usuário (`uvicorn --reload --reload-dir app`, porta 8000) parou de recarregar: o worker manteve o CreationDate antigo e o `/openapi.json` não mostrava as rotas novas, mesmo com `touch` em app/.
   **Why:** o usuário pede para não parar o processo dele.
   **How to apply:** conferir pelo `/openapi.json` ou pelo CreationDate do processo (PowerShell `Get-CimInstance Win32_Process`); para testar de ponta a ponta, subir um uvicorn temporário em outra porta (ex.: 8011) e derrubar só ele no fim; avisar o usuário que precisa reiniciar o servidor.

2. **TimeZone da transação = fuso da loja.** `app.db.definir_contexto` faz `set_config('TimeZone', <fuso da loja>, true)` quando há `loja_id` (UTC sem loja). Consequências não óbvias:
   - SQL com `::date`, `date_trunc`, `extract(dow ...)` sobre timestamptz passa a usar o dia da loja nas rotas da loja/site (e UTC no superadmin). Não escreva SQL que dependa do fuso da sessão sem pensar nisso; prefira calcular os limites do dia em Python (`intervalo_de_dias`).
   - `to_jsonb(NEW)` dos triggers grava timestamptz com o offset da loja no `antes`/`depois` da auditoria (linhas antigas têm `+00:00`). Quem lê a auditoria deve usar `fromisoformat(...).astimezone(zona)`.
   - Objetos carregados antes do `definir_contexto` com loja ficam em UTC (identity map).

Ver também [[login-fora-do-historico]] se existir (marca `app.login`, migração 0004).
