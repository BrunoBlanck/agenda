---
id: DIR-004
titulo: Mobile first no site do consumidor e no painel da loja; tabelas viram cartões no celular
status: ativa
escopo: [backend, frontend-ui, frontend-dev, revisor, coordenador]
onde: backend/app/templates/site/**, backend/app/static/site/**, frontend/src/components/base/Tabela.jsx, frontend/src/**/*.jsx, frontend/src/**/*.css (painel da loja e SUPERADMIN)
criada_em: 2026-10-06
substitui: —
---

## Ordem do usuário
"Preciso que essa página do cliente FINAL seja completamente mobile first, dê uma atenção extra a deixá-la focada no uso pelo mobile; claro que deve ser bonita também no desktop, mas foco total no mobile, no padrão mais atual e moderno de usabilidade. Mobile first: painel da loja também deve ser 100% compatível, com os componentes de tabelas todos padronizados para virarem cards no mobile, de forma que fiquem um debaixo do outro exibindo a lista de uma forma amigável no mobile." (2026-10-06)

## Regra

### Site do consumidor (`/{slug}...`, templates Jinja + `static/site/`)
- CSS escrito **mobile first**: estilos base para 360 px; `@media (min-width: …)` só acrescenta o layout largo. Nada de `max-width` para "consertar" o celular.
- Padrões atuais de usabilidade móvel: alvos de toque com **no mínimo 44×44 px** e 8 px entre alvos vizinhos; corpo do texto ≥ 16 px (campos com `font-size` ≥ 16 px para o iOS não dar zoom); ação principal de cada passo **ao alcance do polegar** (barra inferior fixa/sticky no celular, respeitando `env(safe-area-inset-bottom)`); `viewport-fit=cover` + áreas seguras; `100dvh` em vez de `100vh`; teclado certo em cada campo (`type`/`inputmode`/`autocomplete`); listas de escolha (serviços, profissionais, dias, horários) como opções grandes e tocáveis, dias em faixa rolável horizontal com `scroll-snap` quando couber; cabeçalho compacto no celular (a capa grande não empurra o conteúdo para baixo da dobra); `meta theme-color` com a cor do topo; `prefers-reduced-motion`, `prefers-color-scheme`, foco visível e contraste AA.
- Sem rolagem horizontal da página de 320 px a 1440 px. No desktop o conteúdo fica centrado, com largura de leitura confortável, sem esticar.
- Funciona sem JS (o JS só melhora).

### Painel da loja e SUPERADMIN (React)
- Toda lista em tabela usa o componente base `Tabela` (nunca `Table` do antd direto). Abaixo de **768 px** a `Tabela` mostra cada linha como um **cartão**, um debaixo do outro: o título do cartão é a coluna principal, as demais colunas aparecem como pares rótulo/valor, as ações da linha ficam no cartão com alvo de toque ≥ 44 px, o destaque da linha aberta (`destaqueId`) e o estado vazio/carregando/paginação continuam funcionando. Nenhuma tabela com rolagem horizontal no celular.
- Colunas podem ajustar o cartão por props da própria coluna (ex.: qual é a principal, qual some no cartão), com padrão sensato quando nada é informado.
- Layout do painel no celular: menu em gaveta, cabeçalho da página e ações sem quebrar, barra de filtros empilhada, painel lateral em tela cheia (DIR-001 continua valendo), sem rolagem horizontal da página até 360 px.

## Exceções
- A grade da Agenda (dia/semana) pode rolar horizontalmente **dentro** do próprio quadro no celular, mas a página não.

## Como verificar
- `grep -rn "from 'antd'" frontend/src | grep -w Table` → só `components/base/Tabela.jsx`.
- Abrir cada tela com tabela em 375 px (Playwright `browser_resize` 375×812): linhas como cartões, `document.documentElement.scrollWidth <= innerWidth`.
- Site: `grep -n "max-width" backend/app/static/site/site.css` em `@media` → nenhuma media query `max-width` (só `min-width`/preferências); em 360 px e 1280 px cada passo sem rolagem horizontal; botões e opções com altura ≥ 44 px; `<meta name="viewport" ... viewport-fit=cover>` e `theme-color` no `site/base.html`.

## Aplicação no código existente
- [x] Site do consumidor: `site/base.html`, todos os templates de `templates/site/` e `static/site/site.css`/`site.js` reescritos mobile first.
- [x] `components/base/Tabela.jsx`: modo cartão abaixo de 768 px (vale para todas as telas: Clientes, Serviços, Locais, Materiais, Funcionários, Agendamentos, Controle de tempo, Dashboard, Perfis de acesso, Jornada/Bloqueios, SUPERADMIN Lojas/Detalhe/Planos/Usuários/Visão geral/Histórico).
- [x] Revisão de cada tela do painel e do SUPERADMIN em 375 px (cabeçalho, filtros, colunas principais e ações nos cartões).
