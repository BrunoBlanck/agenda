---
id: DIR-002
titulo: Identidade visual própria
status: ativa
escopo: [frontend-ui, revisor]
onde: frontend/src/**/*.jsx, frontend/src/**/*.css, frontend/src/tema.js
criada_em: 2026-10-02
substitui: —
---

## Ordem do usuário
Identidade própria nos painéis, sem cara de Ant Design padrão nem de tela gerada por IA (2026-10-02).

## Regra
Identidade "agenda de papel da recepção": tinta `#2340A8`, grafite `#1E2230`, papel `#F3F4F7`, marca-texto `#FFE45C` (só para o que pede atenção agora), fonte Atkinson Hyperlegible Next, superfícies com borda e sem sombra. Cores, espaços, raios e fontes só por tokens (`tema.js` + variáveis em `index.css`, os dois sempre juntos). Nada da lista de sinais proibidos (`padroes-ui` UI-31). Detalhes e armadilhas: memória do `frontend-ui` (`identidade-visual.md`).

## Como verificar
- `grep -rnE "#[0-9a-fA-F]{3,8}\b" frontend/src --include=*.jsx`: nenhuma cor solta em JSX (tokens via `theme.useToken()` ou classes CSS).
- Cores novas existem em `tema.js` **e** em `:root` do `index.css`.
- Nenhum sinal de UI-31 na tela alterada.

## Aplicação no código existente
- [x] Revisão completa do front-end com a identidade (2026-10-02).
