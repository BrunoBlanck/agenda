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
- **Navegador com os servidores de dev já de pé (5173/8000):** o frontend-dev deixa no scratchpad da sessão `node_modules/playwright-core` e `tok.txt` (token da clinica-sorriso); `chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })`, token em `sessionStorage['agenda.sessao.loja.clinica-sorriso']` via `addInitScript`, e `page.route` interceptando PUT/POST com `fulfill(503)` para inspecionar o corpo sem gravar no banco de dev.
- **Navegador sem MCP:** os navegadores do Playwright já estão em `~/AppData/Local/ms-playwright` (chromium-1243); `npm i playwright-core@1.63.0` numa pasta do scratchpad e script `.mjs` com `chromium.launch()`. Subir API (`uv run uvicorn app.main:app --port 8001`) e Vite (`API_PROXY_ALVO=http://localhost:8001 npx vite --port 5233 --strictPort`) em portas próprias (a 5199 pode estar ocupada); sessionStorage é por aba, então `ctx.newPage()` simula outra aba.
- **Histórico global do navegador** (provar que um segredo na URL ficou gravado): `chromium.launchPersistentContext(<pasta no scratchpad>, { headless: true, channel: 'chromium' })` (o headless-shell padrão não grava History), fechar o contexto e ler `Default/History` (sqlite, tabela `urls`) com Python. `history.replaceState` não apaga a URL já registrada ali (comprovado em 2026-10-03 com `#token=`).
- **Corrida no front (duas buscas paralelas do mesmo dado):** forçar as duas ordens com `page.route('**/api/...', ...)` atrasando a requisição n (contador). No dev o StrictMode duplica o efeito do Provider (a 2ª chamada é abortada; a que vale é a 3ª). Depois de `waitForURL`, use `getByText(...).waitFor()` e não `count()` (dá 0 antes de renderizar: falso negativo em 2026-10-03).
- Abas abertas por `window.open` sem `noopener` copiam o `sessionStorage` de quem abriu; o opener consegue gravar no `sessionStorage` da aba `about:blank` antes de navegá-la (entrega de token sem URL).
- No dev, o uvicorn confia em X-Forwarded-For vindo de 127.0.0.1 por padrão e o proxy do Vite repassa o cabeçalho do cliente: dá para forjar IP via :5173 (só dev).

- **Site do consumidor em HTML (2026-10-04):** importar ajudantes/fixtures direto de `tests.test_site_paginas` (`site`, `formulario_direto`, `enviar`, `ocultos`, `parametros`, `alterar_loja`) no arquivo exploratório; fuzz de GET/POST com `TestClient(raise_server_exceptions=False)` checando status >= 500 **e** `content-type` JSON (página HTML não pode cair no tratador JSON). Corrida de duplo envio: fixture `servidor` + `threading.Barrier`, repetir em várias horas e também com `site_pendentes_por_telefone=1` (limite na fronteira). Navegador: Chrome do sistema + `javaScriptEnabled: false` no contexto para provar "funciona sem JS"; interceptar só o POST com `page.route`.

- **Banco e servidores próprios (sem tocar no dev do usuário, 2026-10-05):** `TEST_DATABASE_NAME=agenda_revisor uv run pytest` roda a suíte num banco só do revisor (os de migração viram `agenda_revisor_migracao*`). Para o navegador: criar `agenda_rev_nav` pelo dono, exportar `DATABASE_URL`/`DATABASE_OWNER_URL` apontando para ele (as variáveis de ambiente vencem o `.env`), `criar_papel_app` + `alembic upgrade head` + `scripts.seed`, uvicorn na 8011 e Vite na 5244 com `API_PROXY_ALVO`. No fim: TaskStop não mata o node filho do Vite (achar o PID pela porta e `taskkill`), e `DROP DATABASE ... WITH (FORCE)` nos dois bancos.
- **Regra igual no front e no back (ex.: contraste):** varrer no node todos os valores possíveis importando o util do front por `file:///`, gravar os casos perto da fronteira e conferir no Python com a função do back.

- **Conta do cliente no site (2026-10-06):** importar de `tests.test_conta_cliente` (`pedir_codigo`, `confirmar`, `criar_conta`, `ultimo_codigo`, `zerar_limites`); fixture `navegador(ip)` dá cookies próprios por IP. Para rajadas repetidas, `monkeypatch.setattr(get_settings(), 'limite_codigo_intervalo', 1)` e limites altos. No Windows, `PYTHONIOENCODING=utf-8` antes de dar `print` com caracteres não latinos. Ao esperar o pytest em segundo plano encadeado com ruff, procure `" in [0-9.]*s"` no arquivo de saída, não "passed" (o "All checks passed!" do ruff casa antes). O MCP do Playwright só grava arquivos dentro do repo (`.playwright-mcp/`, ignorado pelo git): apague o que gravar.

- **Mobile/375 px (2026-10-06):** o scratchpad da sessão é dividido com os construtores (já traz `node_modules/playwright-core` e `preparar_banco.py`): trabalhe numa subpasta própria (`rev/`). Painel: login pela tela (`getByLabel(/e-mail/i)`, `/senha/i`) em contexto `isMobile+hasTouch` 375x812; medir `scrollWidth`, `.cartao-tabela` e `.ant-table`; nulos/vazio/500 com `page.route('**/api/loja/clientes?**')`. Site: 320/375/1280 com e sem JS seguindo os hrefs reais (`a.servico`, `a.chip`, `a.horario`). Arquivo de teste exploratório passado ao pytest pelo Git Bash como `/c/...` quebra a coleta (go-link no Temp): rode pelo PowerShell com caminho Windows.

- **SMTP de verdade (notificações, 2026-10-06):** servidor de socket numa thread em 127.0.0.1 nas portas permitidas (25/465/587/2525) gotejando bytes; para TLS "aceito", `monkeypatch.setattr(envio_email.ssl, 'create_default_context', lambda *a, **k: ssl._create_unverified_context())` e certificado autoassinado gerado com `cryptography`. Cuidado: os testes do projeto (`test_notificacoes_revisao.py`) usam a porta 2525 e dão **skip** se ela estiver ocupada; não rode exploratórios com servidor nessas portas junto com a suíte. No Windows, conexão recusada em 127.0.0.1 leva ~2 s.

Relacionado: [[defeitos-recorrentes]].
