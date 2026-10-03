---
name: armadilhas-ambiente
description: Armadilhas confirmadas ao verificar a integração contra a API local (uvicorn --reload no Windows, curl com acentos no Git Bash, limites do site)
metadata:
  type: project
---

- `uvicorn --reload` no Windows pode **parar de recarregar** sem aviso (2026-10-02: worker ficou com o código das 21:14 enquanto o back-end mudava). Antes de concluir que a API "não faz X", confira se o código novo está no ar: `curl localhost:8000/openapi.json` e veja o parâmetro/campo novo. Se não está e não pode reiniciar a 8000, suba uma instância própria (`uv run uvicorn app.main:app --port 80NN`) e, no Playwright, redirecione `/api/**` com `route.fetch({ url })`.
- `curl -d '{"x":"área"}'` no Git Bash manda acento fora de UTF-8: a API responde **400** (JSON inválido), não 422. Use só ASCII no corpo ou um arquivo `--data-binary @arquivo.json`.
- Site do consumidor: limite de **10 pedidos/hora por IP em cada loja** (contador no banco, vale para toda a máquina) e 3 pendentes por telefone. Planeje os POSTs de teste; simule 429 com `page.route` em vez de estourar o limite real.
- Pedido de teste do site se desfaz com `POST /api/loja/agendamentos/{id}/recusar` (Administrador).

**Why:** perdi tempo achando que um filtro novo não funcionava, quando a API em execução era antiga.
**How to apply:** em toda verificação contra o back-end real (INT-24).

Mais (2026-10-03, roteamento por URL):
- A porta **5173 pode estar ocupada por outro projeto** desta máquina (um Vite do HomeFinance, só em `[::1]`): suba o nosso com `npx vite --port 5180 --strictPort` em vez de matar o processo alheio.
- `TaskStop` numa tarefa `npx vite ...` mata o shell e **deixa o node órfão** escutando a porta: depois de parar, confira `Get-NetTCPConnection -LocalPort <porta> -State Listen` e derrube o PID (só os que você subiu).
- Vite com `base: '/_app/'` imitando o nginx: o painel abre em `localhost:<porta>/{slug}/painel`; `/` e `/{slug}` vão para o back-end (precisa da API no ar, senão o proxy dá erro). `vite preview` precisa ser reiniciado depois de mudar o `vite.config.js` (o dev reinicia sozinho).
