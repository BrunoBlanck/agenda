# Pagamento do atendimento: concluir só ao marcar como pago

- **Slug:** pagamento-atendimento · **Branch:** feat/pagamento-atendimento (a partir de `feat/notificacoes`, que ainda não está na `main`) · **Status:** aprovada
- **Área:** painel da loja (agenda) + site do consumidor (Minha conta)
- **Pedido original (2026-10-07):** "no painel da loja e para o cliente também adicione aos atendimentos um status, e o status de finalizado só é feito quando a loja marca o pedido como pago. Por agora só registra a forma de pagamento: cartão, dinheiro ou pix; no futuro vamos colocando mais coisas."
- **Decisões do usuário (2026-10-07):** os status continuam os mesmos e com os mesmos nomes (Aguardando aceite, Agendado, Confirmado, **Concluído**, Cancelado, Não compareceu); o "finalizado" é o **Concluído**, que passa a exigir o pagamento. Registra **forma e valor** (valor já preenchido com o preço do agendamento, editável). Formas: **crédito, débito, dinheiro, pix**. O cliente vê no site a situação e a forma ("Concluído · pago no Pix · R$ 50,00").

## 1. Objetivo
Recepção, profissional ou administrador, ao fim do atendimento, marca "Registrar pagamento", escolhe a forma e confere o valor: o agendamento vira Concluído com o pagamento gravado. Sem pagamento, não existe Concluído. O cliente vê no site que o atendimento foi concluído e como pagou. Uso diário, a cada atendimento. A tabela de pagamentos nasce pronta para crescer (parcelas, mais de uma forma, comissão: ABE-13).

## 2. Regras de negócio

| Código | Regra | Onde é garantida |
|---|---|---|
| **AGE-26** (nova) | **Concluir = registrar o pagamento.** A única forma de um agendamento ir para `concluido` é a rota de pagamento (`POST .../pagamento`), que grava o pagamento e muda o status **na mesma transação** (com a baixa de materiais da AGE-20 e o `FOR UPDATE` de hoje). `POST .../status` e `PUT` com `status = concluido` são recusados (422 "Para concluir o atendimento, registre o pagamento."). Só a partir de **`confirmado`** (TRANSICOES de hoje: `agendado` não vai direto para `concluido`; `pendente` precisa ser aceito). Já concluído: 409 "Este atendimento já está pago.". Outra situação: 409 `Não é possível passar de "<rótulo>" para "Concluído".`. Concluir continua sem notificar (NOT-02). | serviço + rota |
| **AGE-27** (nova) | **Dados do pagamento:** `forma` ∈ `credito`, `debito`, `dinheiro`, `pix` (rótulos: Crédito, Débito, Dinheiro, Pix); `valor` decimal(10,2) obrigatório, **≥ 0** e ≤ 99 999 999,99 (zero = cortesia). A tela preenche com o `preco` do agendamento (vazio quando o preço é nulo, módulo Serviços desligado); o `preco` do agendamento **não muda**. Grava quem registrou (`criado_por`) e quando (`pago_em` = hora do servidor). **Um pagamento ativo por agendamento** por enquanto (índice único parcial; dividir em várias formas é futuro). | banco (CHECK, único) + schema |
| **AGE-28** (nova) | **Reabrir um concluído** (só Administrador, como hoje) **exclui logicamente** o pagamento ativo (`excluido_em`/`excluido_por`, histórico na auditoria) junto com o estorno de materiais (AGE-20). Concluir de novo exige novo pagamento. Concluído continua não editável nem excluível (AGE-21). | serviço |
| **AGE-29** (nova) | Concluídos **antigos sem pagamento** (anteriores a esta funcionalidade) continuam válidos: `pagamento = null`; o painel mostra "Pagamento não registrado" e o site mostra só "Concluído". | tela + site |
| **SIT-26** (nova) | **Minha conta do site:** agendamento concluído com pagamento mostra a situação com a forma e o valor: "Concluído · pago no Pix · R$ 50,00" (forma em minúsculas no meio da frase: "no crédito", "no débito", "em dinheiro", "no Pix"). Sem pagamento: só "Concluído". Nada de quem registrou nem hora. | rota + template |
| AGE-17, AGE-19, AGE-20, AGE-21, AGE-22, NOT-02 | Continuam valendo. AGE-22: quem pode mudar status do agendamento (escrita na agenda; só *Minha agenda* = só os próprios) pode registrar o pagamento. | serviço |

**Diretrizes aplicáveis:** `DIR-001` (o registro do pagamento acontece **dentro do painel lateral** do agendamento, nunca em modal/Popconfirm com formulário), `DIR-002` (identidade visual, só tokens), `DIR-003` (site sem caminho para o painel), `DIR-004` (mobile first: formas de pagamento como opções tocáveis ≥ 44 px; na lista de Agendamentos, abaixo de 768 px, cartões).

**Acesso:** registrar pagamento = escrita em `agenda_propria`/`agenda_equipe` + `exigir_edicao` (como `/status`). Ver o pagamento = quem vê o agendamento. **Módulos:** nenhum desliga o pagamento. Serviços desligado: valor começa vazio se o preço for nulo. Materiais: baixa como hoje.

## 3. Banco (migração `0009_pagamentos`)

Tipo novo: `CREATE TYPE forma_pagamento AS ENUM ('credito', 'debito', 'dinheiro', 'pix');`

**`agendamento_pagamentos`** (regras transversais GER-04, GER-08 a GER-12, como as tabelas das migrações 0007/0008: `loja_id`, RLS, auditoria, trigger de `atualizado_em`, soft delete)
| Coluna | Tipo | Null | Regra |
|---|---|---|---|
| `id` | uuid | não | PK |
| `loja_id` | uuid | não | FK → lojas |
| `agendamento_id` | uuid | não | FK composta `(loja_id, agendamento_id)` → agendamentos |
| `forma` | `forma_pagamento` | não | |
| `valor` | numeric(10,2) | não | CHECK `valor >= 0` |
| `pago_em` | timestamptz | não | DEFAULT now() |
| `criado_por` | uuid | sim | FK `(loja_id, criado_por)` → funcionarios |
| `criado_em`, `atualizado_em`, `atualizado_por`, `excluido_em`, `excluido_por` | padrão | | CHECK `excluido_por IS NULL OR excluido_em IS NOT NULL` (exclusão pelo sistema/superadmin grava `excluido_por` nulo) |

Índice **único** `agendamento_pagamentos_ativo_uk (loja_id, agendamento_id) WHERE excluido_em IS NULL`. Downgrade remove tabela e tipo.

## 4. Contrato da API

### `POST /api/loja/agendamentos/{agendamento_id}/pagamento`
- **Permissão:** `EscreverAgenda` + `exigir_edicao` (igual a `/status`).
- **Entrada:**
  | Campo | Tipo | Obrigatório | Null | Regra |
  |---|---|---|---|---|
  | `forma` | enum `credito`/`debito`/`dinheiro`/`pix` | sim | não | AGE-27 |
  | `valor` | decimal(10,2) (número no JSON) | sim | não | 0 a 99 999 999,99, no máximo 2 casas |
- **Saída 200:** `AgendamentoSaida` (detalhe, com materiais), agora com `status = "concluido"` e `pagamento` preenchido (ver abaixo).
- **Erros:**
  | Status | Quando | `detail` |
  |---|---|---|
  | 401 | sem token | Faça login para continuar. |
  | 403 | só leitura | Você só tem permissão de leitura aqui. |
  | 403 | agendamento de outro profissional (só *Minha agenda*) | Você só pode alterar os seus próprios agendamentos. |
  | 404 | inexistente, excluído, de outra loja ou não visível | Agendamento não encontrado. |
  | 409 | já concluído | Este atendimento já está pago. |
  | 409 | status ≠ `confirmado` | Não é possível passar de "<rótulo atual>" para "Concluído". |
  | 409 | deadlock/serialização | Tente novamente. (padrão atual) |
  | 422 | forma/valor inválidos | Verifique os dados informados. (+ `erros[]` com `forma`/`valor`) |

### Alterações em rotas existentes
- **`AgendamentoSaida`** (lista `GET /api/loja/agendamentos`, detalhe `GET /{id}` e todas as respostas de escrita) ganha:
  ```json
  "pagamento": { "id": "uuid", "forma": "pix", "valor": 50.0, "pago_em": "datetime", "registrado_por_nome": "string|null" } | null
  ```
  `null` quando não há pagamento ativo (qualquer status que não seja `concluido`, ou concluído antigo — AGE-29). Na lista, carregar sem N+1 (join/`selectinload` do ativo).
- **`POST .../status`** com `status = concluido` → **422** "Para concluir o atendimento, registre o pagamento." (antes de olhar transição). Reabrir concluído (Administrador) passa a excluir o pagamento (AGE-28).
- **`PUT /api/loja/agendamentos/{id}`** com `status = concluido` → mesmo 422.
- **Site — `GET /{slug}/conta` e páginas da conta que usam `item_da_conta`:** `situacao` passa a ser o texto da SIT-26 quando `status = concluido` e houver pagamento. A consulta dos agendamentos da conta carrega o pagamento ativo (sem N+1).

## 5. Contrato de tela

### Telas e componentes
1. **Painel do agendamento** (`components/AgendamentoPainel.jsx`, `PainelFormulario`):
   - O seletor **Situação** deixa de oferecer "Concluído" (`opcoesDeStatus` em `data/useAgendamentos.js`), em qualquer situação.
   - Agendamento `confirmado` e usuário com edição: seção **"Pagamento"** no painel com botão secundário **"Registrar pagamento"**. Ao tocar, a seção abre (no próprio painel, sem modal) com:
     - **Forma**: 4 opções tocáveis (Crédito, Débito, Dinheiro, Pix), uma escolhida, sem padrão pré-selecionado; obrigatória ("Escolha a forma de pagamento").
     - **Valor** (R$): preenchido com `preco` do agendamento; obrigatório; ≥ 0.
     - Botões **"Confirmar pagamento"** (primário) e "Voltar". Confirmar chama `registrarPagamento` e o painel passa a mostrar o agendamento Concluído. Se o formulário principal tem alterações não salvas, o botão "Registrar pagamento" avisa "Salve ou descarte as alterações antes de registrar o pagamento." (não perde edição).
   - Agendamento `agendado`: a seção mostra o texto de apoio "Confirme o atendimento para registrar o pagamento." (sem botão).
   - Agendamento `concluido`: a seção mostra o resumo, só leitura: **"Pago no Pix · R$ 50,00"** e, em texto de apoio, "em ter 07/10 às 14h30 por Ana" (fuso da loja, padrão de horas do painel). Sem pagamento (AGE-29): "Pagamento não registrado."
   - Outras situações (pendente, cancelado, não compareceu): seção não aparece.
2. **Lista de Agendamentos** (`pages/Agendamentos.jsx`): a coluna Situação, para concluído com pagamento, mostra abaixo da etiqueta o texto pequeno "Pix · R$ 50,00" (no cartão abaixo de 768 px, igual).
3. Etiqueta e rótulo "Concluído" não mudam (`dominio.js`). Acrescentar `formasPagamento` em `data/dominio.js`: `{ credito: { label: 'Crédito', frase: 'no crédito' }, debito: { label: 'Débito', frase: 'no débito' }, dinheiro: { label: 'Dinheiro', frase: 'em dinheiro' }, pix: { label: 'Pix', frase: 'no Pix' } }` e o resumo "Pago no Pix" usa `frase`.

Esboço da seção no painel (confirmado):
```
 Pagamento
 ┌──────────────────────────────────────────┐
 │ [ Crédito ] [ Débito ] [ Dinheiro ] [Pix]│   (2×2 no celular)
 │ Valor  R$ [ 50,00        ]               │
 │            [Voltar] [Confirmar pagamento]│
 └──────────────────────────────────────────┘
```

### Hooks de dados (fronteira entre frontend-ui e frontend-dev)
| Hook / função (em `frontend/src/data/`) | Retorna | Ações |
|---|---|---|
| `useAgendamentos.js` (existente) | agendamentos com o campo novo `pagamento` | nova função exportada `registrarPagamento(id, { forma, valor }) → Promise<Agendamento>` (ao lado de `mudarStatusAgendamento`) |

Objeto `pagamento` na tela (null quando não há):
| Tela | API | Tipo na tela | Pode ser null |
|---|---|---|---|
| `pagamento` | `pagamento` | objeto | sim |
| `pagamento.id` | `id` | string | não |
| `pagamento.forma` | `forma` | `'credito'|'debito'|'dinheiro'|'pix'` | não |
| `pagamento.valor` | `valor` | number | não |
| `pagamento.pagoEm` | `pago_em` | dayjs no fuso da loja | não |
| `pagamento.registradoPorNome` | `registrado_por_nome` | string | sim |

Erros de `registrarPagamento`: rejeita no padrão do cliente HTTP do projeto (`{ status, mensagem, campos: [{ campo, mensagem }] }`, skill `integracao-api`), com `campo` = `forma` ou `valor`. 409 mostra a mensagem e reconsulta o agendamento (como hoje); 422 com campos marca os campos da seção.

### Estados obrigatórios
- Carregando: botão "Confirmar pagamento" em `loading`, opções desabilitadas.
- Erro: mensagem no topo da seção (409/rede); campos com erro (422).
- Sem permissão (leitura ou agendamento de outro profissional): sem botão, só o resumo quando concluído.
- Preço nulo: valor vazio, obrigatório.
- Nome longo do registrador: quebra de linha, sem estourar o painel.
- Concluído antigo sem pagamento: "Pagamento não registrado."

## 6. Critérios de aceite
- [ ] Agendamento confirmado: Recepção registra pagamento no Pix de R$ 50,00 e ele vira Concluído com o pagamento gravado; materiais baixados (com o módulo ativo).
- [ ] O seletor de Situação não oferece mais "Concluído"; `POST /status` e `PUT` com `concluido` devolvem 422 "Para concluir o atendimento, registre o pagamento.".
- [ ] Agendado, pendente, cancelado ou não compareceu: `POST /pagamento` = 409; concluído = 409 "Este atendimento já está pago."; dois pagamentos simultâneos geram um só (trava + índice único).
- [ ] Forma fora do enum, valor negativo, com 3 casas ou acima do limite = 422 com o campo.
- [ ] Profissional (só Minha agenda) registra pagamento nos próprios; no de outro = 403 (ou 404 se não visível); só leitura = 403.
- [ ] Loja A não registra nem vê pagamento de agendamento da loja B (teste automatizado: 404).
- [ ] Administrador reabre um concluído: o pagamento é excluído logicamente (`pagamento = null`), materiais estornados; concluir de novo exige novo pagamento e funciona.
- [ ] Lista e detalhe trazem `pagamento`; lista sem N+1.
- [ ] Concluído antigo sem pagamento aparece como "Pagamento não registrado" no painel e "Concluído" no site.
- [ ] Site, Minha conta: concluído com pagamento mostra "Concluído · pago no Pix · R$ 50,00"; sem link para o painel.
- [ ] Mobile (< 768 px): opções de forma com alvo ≥ 44 px, sem rolagem horizontal; lista em cartões mostra "Pix · R$ 50,00".
- [ ] Migração 0009 sobe e desce; testes, lint e build passam.

## 7. Fora do escopo
- Financeiro completo (ABE-13): caixa, relatórios, comissão, parcelas, troco, várias formas num atendimento, estorno de dinheiro, cobrança online.
- Mostrar forma de pagamento no Histórico do cliente (painel) e nos e-mails/notificações.
- Formas configuráveis por loja.

## 8. Decisões e perguntas
- **Provisório:** só `confirmado` pode ser pago (TRANSICOES atuais); se a loja quiser pagar direto de `agendado`, é mudança de regra a decidir com o usuário.
- **Provisório:** um pagamento ativo por agendamento (índice único); dividir em formas = futuro.
- Valor ≥ 0 (zero permitido para cortesia).

## 9. Histórico de revisão

### Rodada 1 (2026-10-07): REPROVADO
Back-end aprovado (ruff, 1228 testes, migração reversível; segurança, concorrência e N+1 conferidos). Front:
- [A1] importante · frontend-ui · editar o formulário principal com a seção de pagamento aberta e confirmar o pagamento perde a edição em silêncio (e a marca "Alterações não salvas" fica).
- [A2] importante · frontend-ui · Enter numa opção de forma submete o formulário do agendamento (fecha o painel com "Nada foi alterado.") em vez de registrar o pagamento.
- Sugestões: [S1] 409 por cancelamento/não compareceu some junto com a seção (mostrar aviso); [S2] "total gasto" do Histórico do cliente soma `preco`, não o `valor` pago (fora do escopo, levar ao usuário); [S3] `Dinheiro` aceita algarismos não ASCII e "5_0" (preexistente).

### Rodada 2 (2026-10-07): APROVADO
frontend-ui corrigiu A1 (confirmar confere alterações não salvas; `PainelFormulario` ganhou `ocupado` que trava o formulário durante o envio; marca zerada após pagar), A2 (Enter nas formas registra o pagamento) e S1 (aviso com a mensagem do servidor quando a seção some após 409). Sem regressão nas outras telas do `PainelFormulario`. Sugestões abertas: orientar melhor o aviso ("Salve as alterações (ou feche e descarte)…") e um "Desfazer alterações"; S2 (total gasto do Histórico usa `preco`) para o usuário decidir; S3 preexistente.
