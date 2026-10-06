---
name: celular
description: Decisões e armadilhas do painel no celular (DIR-004, 2026-10-06) - Tabela em cartões, dicas no toque, RangePicker de um mês, campos de 16 px, verificação com Playwright
metadata:
  type: project
---

Painel e SUPERADMIN mobile first desde 2026-10-06 (DIR-004). A API de colunas do modo cartão está documentada no topo de `components/base/Tabela.jsx`.

**Why:** ordem do usuário: tabelas viram cartões empilhados no celular, sem rolagem horizontal da página até 360 px.

**How to apply:**
- Tela nova com tabela: escolha o lugar de cada coluna no cartão (`cartao: 'titulo' | 'subtitulo' | 'etiqueta' | 'bloco' | 'acoes' | false`). Situação/status quase sempre `'etiqueta'`; data+hora de agendamento `'subtitulo'` com o cliente como `'titulo'`; campo editável ou Segmented na linha = `'bloco'`. Conteúdo do título precisa ser *phrasing* (fica dentro de `h3`): use `span.recurso`, não `div`.
- Informação que no desktop só existe numa dica (Tooltip) some no toque: repita numa coluna `soNoCartao: true` (ex.: justificativa do ponto).
- Tooltip que só repete o nome de um botão de ícone leva `rootClassName="dica-icone"` (some em `hover: none`); no toque a dica ficava presa por cima do painel lateral aberto pelo botão.
- Filtros de coluna (`filters`/`filterDropdown`) viram botões acima dos cartões; `sorter` não tem equivalente no cartão (a ordem é a da API).
- RangePicker: no celular o CSS global mostra um mês só (os dois lado a lado passavam de 560 px). As setas "próximo" do primeiro painel existem com `visibility: hidden` inline no rc-picker e funcionam se forçadas a visíveis.
- Estilos do antd vêm com `:where(.css-…)` e 3 classes em alguns seletores (presets do picker): para vencer, iguale as classes e some um elemento (`body …`).
- Campos com 16 px abaixo de 768 px (senão o iOS amplia a tela ao focar).
- `Descriptions` dentro de painel lateral: `column={{ xs: 1, sm: 2 }}`.
- Verificação: Playwright em 360/375 e 1280, `scrollWidth <= clientWidth` (o Chromium do MCP tem barra de rolagem de 15 px, por isso cw = 360 em 375). Painel lateral só termina a animação depois de alternar o tamanho da janela 1 px algumas vezes. A API do seed (porta 4823, front 4824) às vezes fica minutos sem responder quando o agente de back-end está trabalhando: skeleton eterno não é bug da tela, confira `/api/saude`.
Relacionado: [[padroes-de-tela]], [[painel-lateral]], [[identidade-visual]]
