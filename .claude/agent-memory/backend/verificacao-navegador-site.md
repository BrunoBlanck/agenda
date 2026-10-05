---
name: verificacao-navegador-site
description: Como conferir as páginas HTML do site (/{slug}) num navegador real sem tocar no banco de dev nem derrubar a API do usuário
metadata:
  type: reference
---

Receita usada em 2026-10-04 (funcionalidade site-agendamento):

1. Banco próprio `agenda_navegador`: script no scratchpad que troca o nome do banco nas URLs do `.env`
   (`make_url(...).set(database=...)`), põe em `os.environ`, `get_settings.cache_clear()`, recria o banco
   (DROP/CREATE pelo dono), `scripts.criar_papel_app.criar_papel_app(url_dono)`, `alembic upgrade head`
   (Config('alembic.ini') com `attributes['url']`) e `scripts.seed.executar()`. **Não importe
   `tests.conftest`**: ele aponta o ambiente para o `agenda_test` ao ser importado.
2. uvicorn temporário em outra porta (8011) com esse `DATABASE_URL`, em background; parar com TaskStop
   e apagar o banco no fim.
3. `npm i playwright-core` numa pasta do scratchpad, `chromium.launch({ executablePath:
   'C:/Program Files/Google/Chrome/Application/chrome.exe' })`; `javaScriptEnabled: false` testa o
   fluxo sem JS; `colorScheme: 'dark'` o tema escuro; estouro horizontal =
   `document.documentElement.scrollWidth > innerWidth`. Caminho de saída: `fileURLToPath(new URL('.',
   import.meta.url))` (o nome do usuário tem acento e `pathname` vem com %C3%A1).

O único erro de console esperado é o 404 do `/favicon.ico` (o back-end não serve favicon).

Relacionado: [[armadilhas-ambiente-e-fuso]]
