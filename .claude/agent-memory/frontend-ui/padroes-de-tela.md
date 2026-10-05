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
- `useConsulta` (data/api) mantém os dados antigos ao trocar a chave (semana, filtro): `carregando` fica false e só `atualizando` liga. Skeleton por período precisa saber qual chave terminou de carregar (Agenda.jsx guarda `carga.chave` com setState na renderização quando `atualizando` muda). Senão a semana nova aparece "vazia" enquanto carrega.
- Carregando = skeleton no formato real: grade da semana com blocos `.agenda-fantasma`, mês com `.agenda-fantasma-linha`, listas do Início com `CarregandoLinhas`. Nada de `Spin`/"Carregando…" (UI-22). Skeleton com animação própria precisa de `animation: none` em `prefers-reduced-motion` (a regra global só encurta a duração e um loop infinito de 0,01 ms pisca).
- Agendamento que passa da meia-noite (decisão 2026-10-02): na semana é cortado às 24h (borda de baixo tracejada + "continua amanhã até 1h") e a sobra aparece no topo do dia seguinte (borda de cima tracejada, "até 1h"); se a sobra termina antes da primeira hora da grade, vira aviso compacto de 22 px no topo, sem esticar a grade até 0h. A API de agenda devolve por sobreposição, então o agendamento do sábado anterior vem junto para a continuação do domingo.
- Permissão por parte da tela (UI-25): em telas com duas permissões (Perfis e horários = `perfis_acesso` + `config_agendamentos`), a etiqueta "Somente leitura" vai no cabeçalho só quando tudo é leitura; senão vai em `tabBarExtraContent` da aba que não pode alterar.
- ACE-19 na tela: a API compara os níveis **gravados** no perfil (não os efetivos com módulo desligado). Para desabilitar opções, use `perfil.acessos` da lista de perfis (meu perfil = teto), não `useAcesso().nivel`, que dá falso bloqueio com módulo desligado.
- Painel da loja vive em /:slug/painel (2026-10-03, roteamento-url): todo caminho do painel sai de `layout/caminhos.js` (`usePainelPath`, `caminhoPainel`, `caminhoSite`); menu (`navegacao.jsx`) guarda só `rota` relativa. Site da loja e "Abrir painel" do SUPERADMIN são `<a target=_blank rel=noopener>` (página inteira), nunca navigate. Rota inexistente = `layout/NaoEncontrada` (com `inicio` dentro das cascas; sem, tela solta só com texto).
- Verificação visual sem MCP: `npm i playwright-core` no scratchpad e `chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })` (em 2026-10-04 não havia mais `%LOCALAPPDATA%/ms-playwright`). Sessão da loja: `sessionStorage['agenda.sessao.loja.<slug>']` + `GET /api/loja/eu` simulado. Ao simular a API com `page.route`, use predicado `url.pathname.startsWith('/api/')`: o glob `**/api/**` captura os módulos `/src/data/api/*.js` do Vite e a tela não carrega. Rotas são `lazy`: espere ~1 s após `goto` antes de ler a URL de um redirect.
- Abrir outra aba depois de um await (Acessar loja, 2026-10-03): `window.open('about:blank')` no clique (com `noopener` ele devolve null), depois `aba.opener = null` + `aba.location.replace(URL absoluta)`. A aba aberta com opener **copia o sessionStorage** da original (inclusive o token do SUPERADMIN): avisar o frontend-dev quando isso importar.
- Ler e apagar algo da URL uma vez só (ex.: `#token=`): ref inicializada com `undefined` + `useEffectEvent` no efeito; a ref sobrevive ao duplo efeito do StrictMode, a segunda execução não acha mais o fragmento.
- `onFinish` do Form só recebe campos **registrados** (Form.Item com `name` montado), mesmo que `initialValues` traga mais chaves. Para mostrar um valor sem enviá-lo (ex.: opções com erro não podem apagar vínculos), troque o Form.Item por um sem `name` com `value` fixo. `CadastroTabela` aceita `campos` como função `(registro) => campos` quando o campo depende do registro aberto.
- Textos com o rótulo do local da loja (Sala, Cadeira, Consultório): o gênero varia, então frases sem artigo/adjetivo concordando com o local ("qualquer sala", "vinculado aqui"), nunca "este/os marcados".
- Mocks provisórios que precisam de estados forçados: chave `mock.*` no sessionStorage só em `import.meta.env.DEV` (o Playwright liga com `addInitScript`).
- Aviso que não bloqueia salvar (ex.: contraste em Cores do site, 2026-10-05): regra `warningOnly` no Form.Item. Cada validação só roda as regras do gatilho e **substitui** erros/avisos do campo, então a regra de aviso precisa valer em `onChange` e `onBlur`; formato só `onBlur` (some ao digitar, volta ao sair). Componente próprio dentro do Form.Item recebe `onBlur` e tem de repassá-lo. Depois de um 422 da API no campo, limpar `warnings` do campo (`form.setFields`) para não repetir a frase. O laranja do aviso do antd (#C26A00) não passa AA: usar `--tom-atencao`.
- Skeleton do antd 6 com largura própria: os estilos do antd (`.ant-skeleton.ant-skeleton-element`) vencem um seletor de 2 classes; prefixe com o contêiner do componente.
- `ColorPicker` com `children` = gatilho próprio (`<button>` acessível com `aria-label`); `disabledAlpha` + `disabledFormat` + `format="hex"`; `toHexString()` devolve minúsculas.
Relacionado: [[identidade-visual]]
