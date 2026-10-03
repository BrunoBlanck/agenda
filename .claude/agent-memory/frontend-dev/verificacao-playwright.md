---
name: verificacao-playwright
description: Como verificar telas no navegador sem o MCP do Playwright e sem gastar tentativas de login (bloqueio após 5 falhas por IP)
metadata:
  type: reference
---

- Sem MCP do Playwright nesta máquina, mas o Chromium já está em `%LOCALAPPDATA%/ms-playwright/chromium-1243/chrome-win64/chrome.exe`. Basta `npm i playwright-core` numa pasta do scratchpad e `chromium.launch({ executablePath })`.
- Para não logar pela tela (5 falhas seguidas bloqueiam a conta no IP): pegar o token por curl (`POST /api/loja/auth/login` com `slug`, `email`, `senha`; `POST /api/superadmin/auth/login`) e injetar com `ctx.addInitScript` em `sessionStorage` nas chaves `agenda.sessao.loja` / `agenda.sessao.superadmin`.
- Perfil com nível diferente sem mexer no banco: `page.route('**/api/loja/eu')` e alterar `acessos.<recurso>` na resposta (só a interface; a API continua decidindo).
- Recepção do seed (juliana@clinica.com) tem `config_loja = nenhum` (não `leitura`): a tela Dados da loja mostra "Sem acesso".
- O proxy do Vite (localhost:5173/api) aceita multipart normalmente; logo servida em `/api/arquivos/logos/...` passa pelo mesmo proxy.

Relacionado: [[integracao-logo]]
