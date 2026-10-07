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
- **Playwright nesta máquina:** não há pacote no projeto; `npm i playwright-core` numa pasta do scratchpad; `executablePath` = Chrome instalado (ver [[verificacao-playwright]]). O token vai direto no `sessionStorage` (`agenda.sessao.loja.<slug>`, uma chave por loja desde 2026-10-03) por `addInitScript` (não gasta tentativa de login). Esc não fechou o painel lateral no headless (Cancelar/X fecham); aba ativa do antd 6 = `.ant-tabs-content-active`; Enter no RangePicker envia o `PainelFormulario`.

- **useConsulta mantém os dados antigos enquanto a chave muda** (`carregando` só é true se `dados === inicial`). Hook cujo
  resultado depende de um parâmetro trocável (ex.: ponto aberto por funcionário) mostra por um instante o dado do anterior com o
  botão habilitado: guarde a chave junto do dado (`{ alvo, registro }`) e só use se bater (INT-21, rodada 2).
- **Ponto não tem DELETE:** um lançamento de teste que passa fica no banco. Só envie lançamentos que certamente dão 409.
- **Playwright `route('**/api/**')` pega os módulos do Vite** (`/src/data/api/*.js`) e a tela não carrega: use
  `route('http://localhost:5173/api/**')` para redirecionar só a API.

**Why:** cada um custou investigação; os dois primeiros parecem defeito do front e não são.
**How to apply:** ao testar telas com datas de controle ou clientes do seed, e ao escrever scripts de verificação. Relacionado: [[integracao-api]]

Mais (2026-10-03, acessar-loja):
- Efeito do filho roda **antes** do efeito do Provider da sessão: token gravado no efeito de uma tela (ex.: `/suporte`) é visto pelo `useEffect` de montagem do Provider, que dispara um `GET /eu` paralelo **sem** as checagens da tela. Ao recusar o token, `controle.current?.abort()` nessa conferência, senão ela termina depois e marca `logado` (comprovado: token comum plantado na entrega entrava no painel).
- Provar que nada sensível vai para o histórico global: `chromium.launchPersistentContext(pasta, { executablePath: <chrome-win64/chrome.exe>, headless: true })` grava `Default/History` (copiar o arquivo e ler a tabela `urls` com o sqlite3 do Python).

Mais (2026-10-06, conta-cliente):
- `useConsulta(..., { ativo: false })` zera `dados`: num `PainelLateral` que busca "a cada abertura", desligar com o painel fechando faz o conteúdo piscar para o estado vazio durante a animação. Padrão usado em `useCodigosSite`: contador de aberturas (setState no render quando `ativo` vira true) na chave, consulta ligada desde a primeira abertura, e itens só quando `consulta.atual`.
  **Why:** confirmado em 2026-10-06 ao ligar a conta-cliente.
  **How to apply:** todo hook "busca de novo ao reabrir".
- Para forçar bordas (null, 502 HTML, rede fora, 401) com o back-end real rodando, `page.route` do Playwright no endpoint é suficiente e não mexe no banco; o 404 real do DELETE dá para provocar servindo um GET falso com `possui_conta: true`.
- Código de confirmação real do site (conta-cliente): `/clinica-sorriso/conta/criar` com o telefone da Maria do seed `(11) 98888-1111`; o código só é consumido ao salvar a senha. Remover acesso também invalida os códigos pendentes do telefone (a lista do painel esvazia).
