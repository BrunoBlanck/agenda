---
name: padroes-de-tela
description: Padrões de montagem de tela e armadilhas do antd 6 encontradas neste projeto (painel lateral + Form, Drawer className, Table scroll, Enter para enviar)
metadata:
  type: project
---

Padrões adotados em 2026-10-02 e armadilhas confirmadas na prática.

**Why:** evitar repetir investigação e manter todas as telas iguais.

**How to apply:**
- Toda tela começa com `Pagina` (título, descrição, ações) e agrupa em `Secao` (`rente` para tabela encostada). Cadastros simples usam `CadastroTabela`, que já monta a página inteira.
- Formulário por cima da tela = painel lateral (ver [[painel-lateral]]); `valoresIniciais` + `destroyOnHidden` + `preserve={false}`, nada de `useEffect` para preencher. Padrões de registro novo vão em `valoresNovo`/`valoresIniciais`, nunca `initialValue` no Form.Item (gera aviso "Form already set initialValues"). Um botão submit oculto faz o Enter enviar.
- Form.List com `preserve={false}` no Form: os Form.Item dos itens precisam de `preserve`, senão o StrictMode (dev) apaga os valores dos itens ao montar.
- message/modal via `App.useApp()` (main.jsx envolve em `<AntApp>`); não usar `message.useMessage` + contextHolder.
- antd 6: `className` do Drawer vai no próprio `.ant-drawer-section` (não num ancestral) — seletor CSS no mesmo elemento.
- `Tabela` usa `scroll.x = 'max-content'`, que impede quebra de linha; tabelas com texto longo passam `scroll={{ x: <número> }}` (CadastroTabela: prop `larguraTabela`).
- Rotas com `lazy()`; fallback das telas fica na Casca (skeleton), com `LimiteErro` por rota.
- Vite 8: chunks manuais via `build.rolldownOptions.output.codeSplitting.groups` (manualChunks foi removido).
Relacionado: [[identidade-visual]]
