---
name: identidade-visual
description: Direção visual adotada em 2026-10-02 (agenda de papel, tinta + marca-texto, Atkinson Hyperlegible Next) e regras de uso que não ficam óbvias só lendo o código
metadata:
  type: project
---

Identidade definida na revisão completa do front-end (2026-10-02): "agenda de papel da recepção".
Tinta #2340A8 (primária), grafite #1E2230 (texto), papel #F3F4F7 (fundo), marca-texto #FFE45C.

**Why:** o usuário pediu identidade própria, sem cara de antd padrão nem de IA. Teal antigo (#0f766e) e índigo do SUPERADMIN foram abandonados.

**How to apply:**
- Marca-texto (classe `.marca-texto`, tom `marca` da Etiqueta) é o único destaque "ousado": só para o que pede atenção agora (solicitação do site/pendente, hoje, estoque a repor). Não usar como decoração.
- Superfícies com borda e sem sombra; sombra só em camadas flutuantes. Raio 10 contêiner / 6 controle / 4 etiqueta.
- Status sempre via `components/Etiquetas.jsx` (tom + ícone + texto); mapas de status em data/ têm `tom`, não `color` do antd.
- Horários exibidos como "9h", "14h30" (`horaCurta`); formulários continuam HH:mm.
- Fonte Atkinson Hyperlegible Next tem zero cortado em todos os modos (não há alternativa via font-feature); foi aceito como traço de legibilidade. Se o usuário reclamar, trocar só em tema.js e index.css.
- SUPERADMIN = mesma Casca com barra lateral grafite (`temaPlataforma`).
- Site do consumidor saiu do React (2026-10-03, vira HTML do back-end). As cores por tipo que o protótipo usava (`temasSite`: clínica #1F5C99, barbearia #8A4B1F com topo grafite, escola #2F6B3A) ficam no histórico do git, para a especificação do site.
- Cores existem em dois lugares (tema.js para o antd, :root em index.css): mudar os dois.
Relacionado: [[padroes-de-tela]]
