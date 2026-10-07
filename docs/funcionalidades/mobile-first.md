# Mobile first: site do consumidor e painéis (DIR-004)

Status: aprovada · Branch: `feat/mobile-first` (a partir de `feat/conta-cliente`) · Criada em 2026-10-06

## 1. Objetivo
Aplicar a diretriz **DIR-004** no código que já existe: o site do cliente final passa a ser pensado primeiro para o celular (bonito também no desktop) e o painel da loja/SUPERADMIN fica 100% usável no celular, com toda tabela virando cartões empilhados abaixo de 768 px.

Diretrizes que tocam: **DIR-001** (painel lateral; no celular em tela cheia), **DIR-002** (identidade "agenda de papel" no painel; o site mantém as cores da loja SIT-09/13/15), **DIR-003** (site sem caminho para o painel; a palavra "login" não aparece nos templates), **DIR-004**.

## 2. Regras de negócio
Nenhuma regra nova e nenhuma mudança de comportamento: mesmas rotas, mesmos formulários, mesmos nomes de campo, mesmos fluxos (agendar, entrar, criar conta, código, minha conta, remarcar, cancelar). Só apresentação.

## 3. API
Sem mudança. Nenhuma rota nova, nenhum campo novo.

## 5. Tela

### 5.1 Site (backend: `backend/app/templates/site/**`, `backend/app/static/site/**`)
Reescrever o CSS mobile first e ajustar o HTML dos templates conforme DIR-004 (seção "Site do consumidor"):
- Cabeçalho compacto no celular (logo pequeno + nome + "Minha conta"), capa completa só no largo; contato (endereço/telefone) acessível sem ocupar a dobra.
- Etapas do agendamento: indicador compacto no celular ("Passo 2 de 4 · Horário" + barra de progresso), lista completa no largo.
- Escolhas (serviço, profissional, local, dia, horário) como opções grandes tocáveis (radio estilizado / links), ≥ 44 px; dias em faixa horizontal com `scroll-snap`; horários em grade de chips que se adapta à largura.
- Ação principal de cada passo e dos formulários de conta numa barra inferior sticky no celular (com `env(safe-area-inset-bottom)`); no largo volta ao fluxo normal.
- `viewport-fit=cover`, `meta theme-color` (cor do topo da loja), `100dvh`, campos ≥ 16 px com teclado certo, foco visível, AA, `prefers-reduced-motion`, dark mode já existente preservado.
- Desktop: conteúdo centrado com largura confortável (cartão ~ 640–720 px; passos com mais colunas quando couber).
- Sem JS obrigatório; testes do back-end existentes continuam verdes (ajustar só asserções de HTML que dependam de marcação alterada, sem afrouxar o que elas garantem).

### 5.2 Painel React (frontend-ui: `frontend/src/components`, `layout`, `pages`, `superadmin`, CSS)
- `components/base/Tabela.jsx`: abaixo de 768 px (`Grid.useBreakpoint`) renderiza a lista como cartões empilhados (`<ul>`/`<li>` ou `article`), com: título = coluna principal (padrão: primeira coluna; prop de coluna `cartao: 'titulo'`), demais colunas como rótulo/valor (usar `title` da coluna; `cartao: false` esconde; `cartao: 'rodape'` para ações), coluna `acoes` no rodapé do cartão com botões ≥ 44 px, `destaqueId` → cartão destacado, `loading` → skeleton de cartões, vazio → mesmo `EstadoVazio`, paginação igual, `expandable` → conteúdo expandível dentro do cartão, `onRow`/clique preservado. Mesma API para quem já usa; nenhuma tela precisa mudar para funcionar, mas ajuste as colunas das telas onde o padrão não ficar bom.
- Revisar em 375 px: `Casca`/`AppLayout` (gaveta), `Pagina` (título + ações quebrando bem; botão "Novo" acessível), `BarraFiltros` (empilhada), `PainelFormulario`/`PainelLateral` (tela cheia, rodapé fixo), Agenda (exceção: quadro rola por dentro), Dashboard, Controle de tempo, Perfis, SUPERADMIN.
- Tokens da DIR-002, sem cor solta.

## 6. Testes e verificação
- Backend: `pytest` verde, `ruff` ok.
- Front: `npm run lint` e `npm run build` ok.
- Playwright em 375×812 e 1280×800: site (todos os passos e páginas de conta) e telas do painel com tabela, conferindo cartões e `scrollWidth <= innerWidth`.

## 9. Histórico
- 2026-10-06 · especificação criada.
- 2026-10-06 · frontend-ui entregou (lint/build ok; Playwright 360/375/1280 em 11 telas da loja + 6 do SUPERADMIN). **Divergências aceitas:** papéis extras de coluna no cartão (`subtitulo`, `etiqueta`, `bloco`, `soNoCartao`, `expandable.rotuloCartao`); colunas com `sorter` não ordenam no cartão (ordem da API); campos 16 px e calendário de período de um mês também no painel; filtros de coluna viram botões acima dos cartões.

### API de colunas no modo cartão (`Tabela`, < 768 px)
| Prop da coluna | No cartão |
|---|---|
| `cartao: 'titulo'` | título (padrão: 1ª coluna; só elementos de texto, fica dentro de `h3`) |
| `cartao: 'subtitulo'` | linha sob o título (data, horário) |
| `cartao: 'etiqueta'` | canto direito do título (situação) |
| `cartao: 'bloco'` | rótulo em cima, valor em largura total |
| `cartao: 'acoes'` / `'rodape'` | rodapé, alvos 44 px (padrão de `key: 'acoes'`) |
| `cartao: false` | escondida no cartão |
| (nada) | par rótulo/valor com o `title`; valor vazio esconde o par |
| `soNoCartao: true` | coluna só no cartão |
| `expandable.rotuloCartao` | texto (ou função) do botão de expandir |

- 2026-10-06 · backend entregou o site (pytest 1049 verdes, ruff ok; Chrome em 320/375/1280/1440, claro/escuro, com e sem JS). **Divergências aceitas:** filtro de profissional virou faixa de links com o mesmo parâmetro `profissional=` (um toque, sem JS; sai o `<select>` + "Atualizar" e os campos de contexto `acao`, `servico_id`, `dia_escolhido`); `Paleta.topo_escuro`/`cores_do_topo()` para o `theme-color`; ajuste mínimo em `templates/base.html` (página de erro usada pelo site).
- 2026-10-06 · rodada 1 · **APROVADO** (pytest 1049 verdes, ruff ok, lint/build ok, Chrome 320/375/1280 no painel e no site; DIR-001/002/003/004 ok). Sugestões não aplicadas: repassar `onChange` do Table e `rowSelection`/`summary` à `TabelaCartoes` (nenhuma tela usa hoje); título vazio cair em "—"; troca de modo ao cruzar 768 px perde página/filtro local; espaço em `HistoricoAlteracoes.jsx:320`.
