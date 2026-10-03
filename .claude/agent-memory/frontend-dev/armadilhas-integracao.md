---
name: armadilhas-integracao
description: Armadilhas confirmadas ao ligar telas à API (fuso, CPFs do seed, Form com id, 409 no campo, useConsulta com dado da chave anterior, ponto sem DELETE, route do Playwright)
metadata:
  type: project
---

Confirmado em 2026-10-02 na integração da área A (clientes, funcionários, perfis).

- **Colunas de controle em UTC:** `criado_em`, `atualizado_em` e `ultimo_login_em` saem com `Z` (UTC), não com o fuso da loja (só `inicio`/`fim` de agendamento e bloqueio vêm com `-03:00`). `dataHoraBR`/`lerDataHora` cortam os 19 primeiros caracteres, então `UltimaAlteracao` mostra a hora UTC (3h adiantada). Foi relatado ao coordenador; confira se já corrigiram antes de confiar no horário exibido.
- **O seed tem CPFs inválidos** (Fernanda 111.222.333-44, Maria 123.456.789-00): editar esses clientes dá 422 "CPF inválido." no campo até alguém corrigir o CPF. Não é defeito da tela.
- **Form do CadastroTabela é o mesmo entre aberturas:** um valor que não é campo registrado (ex.: `id` nos valores iniciais) fica no store e passa para o próximo "novo". Para saber se é edição dentro dos campos, registre `<Form.Item name="id" hidden>` (no fim, para não roubar o foco) e use `Form.useWatch('id', form)`; nunca `useWatch(..., { preserve: true })`.
- **409 de unicidade** (CPF, e-mail, nome) vem só com `detail`; o `useTratarErro` só põe no campo o que vem em `campos`. `data/api/registro.js` (`conflitoNoCampo`) converte o erro pelo texto da mensagem.
- **Playwright nesta máquina:** não há pacote no projeto; `npm i playwright-core` numa pasta do scratchpad e `executablePath` = `%LOCALAPPDATA%/ms-playwright/chromium-1243/chrome-win64/chrome.exe`. O token vai direto no `sessionStorage` (`agenda.sessao.loja`) por `addInitScript` (não gasta tentativa de login). Esc não fechou o painel lateral no headless (Cancelar/X fecham); aba ativa do antd 6 = `.ant-tabs-content-active`; Enter no RangePicker envia o `PainelFormulario`.

- **useConsulta mantém os dados antigos enquanto a chave muda** (`carregando` só é true se `dados === inicial`). Hook cujo
  resultado depende de um parâmetro trocável (ex.: ponto aberto por funcionário) mostra por um instante o dado do anterior com o
  botão habilitado: guarde a chave junto do dado (`{ alvo, registro }`) e só use se bater (INT-21, rodada 2).
- **Ponto não tem DELETE:** um lançamento de teste que passa fica no banco. Só envie lançamentos que certamente dão 409.
- **Playwright `route('**/api/**')` pega os módulos do Vite** (`/src/data/api/*.js`) e a tela não carrega: use
  `route('http://localhost:5173/api/**')` para redirecionar só a API.

**Why:** cada um custou investigação; os dois primeiros parecem defeito do front e não são.
**How to apply:** ao testar telas com datas de controle ou clientes do seed, e ao escrever scripts de verificação. Relacionado: [[integracao-api]]
