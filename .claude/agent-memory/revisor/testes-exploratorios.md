---
name: testes-exploratorios
description: Como rodar testes exploratórios do revisor fora do repositório, reaproveitando as fixtures do backend (inclusive concorrência real)
metadata:
  type: reference
---

Testes exploratórios ficam no scratchpad (fora do repo) e reaproveitam `backend/tests/conftest.py` como plugin:

`cd backend && uv run python -m pytest <arquivo fora do repo> -p tests.conftest -c pyproject.toml --rootdir . -p no:cacheprovider -q -s`

- Fixtures úteis: `cliente`, `lojas` (loja-a/loja-b com Admin, Recepção, Profissional), `engine_dono`; `tests.clinica.montar_clinica(cliente, lojas[0])`; `tests.fabricas.usuario_com(engine, loja, {'recurso': 'nivel'})` e `cabecalho(funcionario)`.
- Para ver 500 em vez de exceção: `TestClient(app, raise_server_exceptions=False)`.
- Concorrência real: subir `uvicorn.Server` numa thread (porta 8765) dentro do teste e disparar com `httpx` + `threading.Barrier`; o `TestClient` é sequencial e não reproduz corrida.

- O `conftest` já tem a fixture `servidor` (sessão) e `tests/concorrencia.py` (`rajada`); uma fixture local com outro nome/porta evita conflito.
- Limites de login/site: os contadores ficam em `limites.contadores` (apagados pelo `limpar`). No TestClient o IP é inválido, então tudo cai na chave "desconhecido". Para testar bloqueio sem esperar minutos, altere `get_settings().login_bloqueio_*` no teste e chame `get_settings.cache_clear()` no fim.
- **Nunca** rodar os exploratórios ao mesmo tempo que o `pytest` do projeto: os dois recriam e limpam o mesmo `agenda_test` e geram falhas falsas (IntegrityError/OperationalError). Rode em sequência.
- O `addopts = "-q"` do projeto somado a `-q` esconde o resumo; use `-o addopts=""` para ver "N passed".
- IP por requisição no TestClient: `TestClient(app, client=('203.0.113.5', 50000))`.
- Migração: rodar `alembic upgrade/downgrade` num banco temporário criado pelo dono (`PYTHONPATH=.` ao rodar script fora do repo).
- **API local já de pé (rodada de integração):** script httpx no scratchpad contra `http://localhost:8000/api`, logins do seed (superadmin `rafael@agendaplataforma.com`/`superadmin123`; loja por `slug`+e-mail/`senha123`). Para provar fuso, trocar a `escola-harmonia` para America/Manaus via `PUT /superadmin/lojas/{id}` (corpo com todos os campos de `LojaEntrada`) e **restaurar no fim**. Front: `node` importando `frontend/src/data/api/conversao.js` por `file:///` com `TZ=` variado.

- **nginx (deploy/nginx/agenda.conf):** `nginx -t` e teste de roteamento real com Docker: copiar o conf para o scratchpad junto com um `stub.conf` (`server { listen 127.0.0.1:8000; location / { return 200 "BACK uri=$request_uri xff=$http_x_forwarded_for"; } }`) e subir `nginx:stable-alpine` com `-p 8089:80`, o conf montado em `/etc/nginx/conf.d` e `frontend/dist` em `/var/www/agenda`. Prefixar com `MSYS_NO_PATHCONV=1` no Git Bash. `curl --path-as-is` para caminhos com `..`.
- **Navegador sem MCP:** os navegadores do Playwright já estão em `~/AppData/Local/ms-playwright` (chromium-1243); `npm i playwright-core@1.63.0` numa pasta do scratchpad e script `.mjs` com `chromium.launch()`. Subir API (`uv run uvicorn app.main:app --port 8001`) e Vite (`API_PROXY_ALVO=http://localhost:8001 npx vite --port 5233 --strictPort`) em portas próprias (a 5199 pode estar ocupada); sessionStorage é por aba, então `ctx.newPage()` simula outra aba.
- No dev, o uvicorn confia em X-Forwarded-For vindo de 127.0.0.1 por padrão e o proxy do Vite repassa o cabeçalho do cliente: dá para forjar IP via :5173 (só dev).

Relacionado: [[defeitos-recorrentes]].
