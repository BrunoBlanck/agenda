---
name: verificacao-playwright
description: Como verificar telas no navegador sem o MCP do Playwright e sem gastar tentativas de login (bloqueio após 5 falhas por IP)
metadata:
  type: reference
---

- Sem MCP do Playwright nesta máquina. Em 2026-10-04 a pasta `%LOCALAPPDATA%/ms-playwright` não existia mais: use o Chrome instalado (`C:/Program Files/Google/Chrome/Application/chrome.exe`) como `executablePath`, com `npm i playwright-core` numa pasta do scratchpad.
- O console do navegador sempre loga `Failed to load resource ... 422/500` quando o teste provoca o erro de propósito: é do Chrome, não da tela; filtre essas linhas ao exigir "console sem erros".
- Para provocar um 422 **real** sem estado ruim no banco: `route.continue({ postData })` trocando o corpo (ex.: uuid inexistente ou malformado) antes de chegar à API.
- Para não logar pela tela (5 falhas seguidas bloqueiam a conta no IP): pegar o token por curl (`POST /api/loja/auth/login` com `slug`, `email`, `senha`; `POST /api/superadmin/auth/login`) e injetar com `ctx.addInitScript` em `sessionStorage` nas chaves `agenda.sessao.loja.<slug>` (uma por loja, desde 2026-10-03) / `agenda.sessao.superadmin`. Abra a página em `/{slug}/painel/...` (o painel não fica mais em `/painel`).
- Perfil com nível diferente sem mexer no banco: `page.route('**/api/loja/eu')` e alterar `acessos.<recurso>` na resposta (só a interface; a API continua decidindo).
- Recepção do seed (juliana@clinica.com) tem `config_loja = nenhum` (não `leitura`): a tela Dados da loja mostra "Sem acesso".
- O proxy do Vite (localhost:5173/api) aceita multipart normalmente; logo servida em `/api/arquivos/logos/...` passa pelo mesmo proxy.
- Erro **real** da API sem estragar dados (2026-10-05): 401 = `route.continue({ headers: { ...req.headers(), authorization: 'Bearer invalido' } })` só na rota testada (o resto da sessão segue válido e a tela vai ao login); 404 do SUPERADMIN = `route.continue({ url: 'http://localhost:8000/api/superadmin/lojas/<uuid zero>/...' })` (trocar de origem funciona).
- Avisos `[api] <status> ...` no console vêm do próprio `useConsulta`/cliente em DEV quando o teste provoca o erro: esperados, não são defeito.

Relacionado: [[integracao-logo]]
