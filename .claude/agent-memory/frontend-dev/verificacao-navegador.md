---
name: verificacao-navegador
description: Como verificar telas no navegador sem o MCP do Playwright (playwright-core no scratchpad + chromium já instalado) e armadilhas de seletor no antd 6
metadata:
  type: reference
---

Sem MCP do Playwright, dá para testar de verdade: `npm i playwright-core` numa pasta do scratchpad e
`chromium.launch({ executablePath: %LOCALAPPDATA%/ms-playwright/chromium-1243/chrome-win64/chrome.exe })`
(o navegador já está instalado na máquina; o pacote `playwright` não está no projeto).

Seletores que funcionaram no antd 6 (2026-10-02):
- painel lateral aberto: `.ant-drawer-section:visible` (o `rootClassName` fica no root, e o label pode apontar para fora dele);
- aba ativa: `[role=tabpanel]:visible` (não existe `.ant-tabs-tabpane-active`);
- Popconfirm com Tooltip por cima do botão: clicar o OK com `evaluate((b) => b.click())`.

Armadilha confirmada: dois `Form` na mesma tela com o mesmo campo (`nome`) geram `id="nome"` duplicado e o
label de um focava o input do outro. Dê `name` ao Form (`PainelFormulario` repassa props ao Form). Ver [[integracao-superadmin]].

Mais (2026-10-02, área de cadastros):
- Popconfirm aberto "não estável" (animação parada no headless): `page.locator('.ant-popconfirm .ant-btn-dangerous').last().dispatchEvent('click')`.
- Token via `addInitScript` é regravado a **cada navegação**: para testar 401 com token inválido, grave só uma vez (marcador no sessionStorage) num contexto novo.
- `page.keyboard.press('Enter')` num DatePicker dentro do `PainelFormulario` envia o formulário (Enter envia); use `Tab` para confirmar a data.
- Linhas de dados da Table: `.ant-table-row` (o primeiro `tbody tr` é a linha de medida, vazia).
