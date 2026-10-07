# Notificações: sino no painel e no site, e-mail por SMTP da loja, WhatsApp (pendente) e lembrete

- **Slug:** notificacoes · **Branch:** feat/notificacoes (a partir de `feat/mobile-first`, que ainda não está na `main` e traz a conta do cliente) · **Status:** aprovada
- **Área:** painel da loja + site do consumidor (+ Configurações da loja)
- **Pedido original (2026-10-06):** "tabela Notificacoes com 3 colunas de status (whatsapp, email e site) e uma coluna tipo (notificação para o cliente ou para a loja). A loja notifica o vendedor que tem algo novo para aceitar ou que algo foi cancelado; o cliente, atendimento aceito, cancelado etc. Cliente e loja têm um sininho (notificação do site); ele vê e marca como visualizadas todas as que viu, só se clicar no sino. E-mail e WhatsApp: 1 pendente de envio, 2 enviado com sucesso, 3 erro no envio, 4 dado faltando no cadastro. Por agora o WhatsApp vai sempre para 4. Notificar o cliente X minutos antes do atendimento, configurável pela loja; o mesmo valor delimita o prazo a partir do qual o cliente não pode mais cancelar (só a loja)."
- **Decisões do usuário (2026-10-06):** na loja, **só o profissional do agendamento** recebe; o e-mail sai pelo **SMTP configurado por cada loja** no menu de configuração da loja; eventos: situação mudou (cliente), lembrete (cliente), pedido recebido (cliente) e ações do cliente (loja).

## 1. Objetivo
O cliente fica sabendo, sem ligar para a loja, quando o pedido chegou, foi aceito, recusado, cancelado ou mudou de horário, e recebe um lembrete antes do atendimento. O profissional fica sabendo quando um cliente pede, remarca ou cancela um horário dele. Tudo aparece no sino (painel e site) e, quando possível, por e-mail; o WhatsApp fica registrado para quando existir. Uso diário, várias vezes por dia.

## 2. Regras de negócio

| Código | Regra | Onde é garantida |
|---|---|---|
| **NOT-01** (nova) | Toda notificação é uma linha em `notificacoes`, com `tipo` = `cliente` (destinatário: um registro de cliente) ou `loja` (destinatário: um funcionário). Gravada **na mesma transação** do fato que a gerou (se a mudança de status não grava, a notificação também não). O texto (título e mensagem) é **congelado** na criação: editar o agendamento depois não muda notificações antigas. | banco (CHECK) + serviço |
| **NOT-02** (nova) | **Eventos do cliente** (`tipo = cliente`, destinatário = cliente do agendamento): `pedido_recebido` (pedido pelo site, inclusive remarcação pelo site); `agendamento_criado` (criado no painel); `confirmado` (qualquer ida para `confirmado`, inclusive aceitar pedido/remarcação); `cancelado` (cancelado ou recusado **pela loja**; o motivo **não** vai na mensagem, SIT-21); `horario_alterado` (a loja mudou início, profissional ou local de um agendamento não final); `lembrete` (NOT-05). Ida para `concluido`/`nao_compareceu` e reabertura não notificam. Ação feita pelo próprio cliente no site não gera notificação de `cancelado` para ele. | serviço |
| **NOT-03** (nova) | **Eventos da loja** (`tipo = loja`, destinatário = **só o profissional** do agendamento): `novo_pedido` (pedido pelo site), `remarcacao_pedida` (remarcação pelo site; se o profissional mudou, o antigo recebe `cancelado_pelo_cliente` com o texto "remarcou para outro profissional" e o novo recebe `remarcacao_pedida`), `cancelado_pelo_cliente` (cancelamento pelo site). Profissional inativo ou excluído não recebe. | serviço |
| **NOT-04** (nova) | **Status por canal.** `status_site`: 1 não visualizada, 2 visualizada. `status_email` e `status_whatsapp`: **1 pendente de envio, 2 enviado com sucesso, 3 erro no envio, 4 dado faltando no cadastro** (destinatário sem e-mail/telefone). **WhatsApp: sempre 4 por enquanto** (não implementado; `erro` explica). E-mail: sem e-mail no destinatário = 4; loja sem SMTP ativo = 3 com o erro "O envio de e-mail da loja não está configurado."; falha temporária = continua 1 e tenta de novo (até 3 tentativas, espera crescente), depois 3 com a mensagem do erro (sem senha, sem dados pessoais além do endereço). Status só avança: 2, 3 e 4 são finais. | banco (CHECK 1..4 / 1..2) + serviço |
| **NOT-05** (nova) | **Lembrete**: para agendamento `agendado` ou `confirmado`, não excluído, quando `agora ≥ inicio − antecedência da loja` e `agora < inicio`, cria **uma** notificação `lembrete` (único por agendamento: índice parcial). Se o agendamento for criado/confirmado já dentro da janela, o lembrete sai no próximo ciclo. Pendente não recebe lembrete. Remarcação para outro horário permite um novo lembrete (o índice considera o `inicio` lembrado). | banco (único) + tarefa |
| **NOT-06** (nova) | **Marcar como visualizada só ao clicar no sino**: abrir o sino marca como visualizadas **as notificações mostradas naquela abertura** (ids enviados pelo front no painel; as da página aberta no site). Notificação que chegou depois continua não visualizada. Cada um só lê e marca **as suas**: funcionário = `tipo loja` com o seu `funcionario_id`; cliente = `tipo cliente` de qualquer cliente da loja com o telefone da conta (SIT-16). | rota + serviço |
| **NOT-07** (nova) | **Envio fora da transação do usuário** (outbox): a rota só grava a linha; uma tarefa de fundo envia os e-mails pendentes (`FOR UPDATE SKIP LOCKED`, segura com vários processos) e cria os lembretes, a cada 30 s (configurável). Tempo limite de SMTP 15 s. A tarefa roda com origem `sistema` (GER-08/12). | tarefa |
| **NOT-08** (nova) | E-mail para o **cliente** nunca tem link para o painel/SUPERADMIN (DIR-003); pode ter o link do site `/{slug}/conta` quando `URL_PUBLICA` estiver configurada. Datas no fuso da loja (GER-15). Remetente = remetente configurado pela loja. Texto simples (sem HTML) por enquanto. | serviço |
| **CFG-05** (nova) | **Antecedência do cliente** em `loja_configuracoes.antecedencia_cliente_minutos` (int, padrão **120**, de 0 a 10080 = 7 dias). O **mesmo valor** é o horário do **lembrete** (NOT-05) e o **prazo para o cliente cancelar ou remarcar pelo site** (substitui a constante `ANTECEDENCIA_CLIENTE`, SIT-23/24). Depois do prazo, só a loja altera. Editado em Configurações › Dados da loja (escrita em `config_loja`); a tela aceita minutos ou horas, a API só minutos. | banco (CHECK) + serviço + tela |
| **CFG-06** (nova) | **SMTP por loja** (escrita em `config_loja`): ativo, servidor, porta (25, 465, 587 ou 2525), segurança (`ssl` ou `starttls`), usuário, senha, e-mail e nome do remetente. A **senha é cifrada** no banco (chave `CHAVE_CIFRA` no `.env`, Fernet), **nunca volta na API** (só `senha_definida`) e é **mascarada na auditoria**. Servidor que resolve para endereço privado, loopback ou link-local é recusado (422) fora de `AMBIENTE=desenvolvimento`/`teste` (SSRF). "Enviar e-mail de teste" manda para um endereço informado e devolve o resultado na hora (limite: 5 por loja a cada 10 min). | banco + serviço + rota |
| **SIT-25** (nova) | **Sino no site**: logado, o cabeçalho mostra "Avisos" com a quantidade não visualizada (sem número quando zero). `GET /{slug}/conta/avisos` lista as notificações do telefone da conta (20 por página, mais novas primeiro) e marca como visualizadas as da página mostrada (NOT-06). Funciona sem JS. Sem link de local e sem motivo de cancelamento. | rota + template |
| SIT-23, SIT-24 (alteradas) | O prazo passa de "2 h fixas" para CFG-05. Mensagem de fora do prazo continua com o telefone da loja. | serviço |
| AGE-17/19/25, SIT-06/16 | Continuam valendo; as notificações são efeito colateral, nunca bloqueiam a mudança de status. | serviço |

**Diretrizes aplicáveis:** `DIR-001` (painel lateral: o sino abre um `PainelLateral`, nunca modal/popover grande), `DIR-002` (identidade visual, só tokens), `DIR-003` (site e e-mail ao cliente sem caminho para o painel), `DIR-004` (mobile first: sino tocável ≥ 44 px no site e no painel; lista em cartões).

**Acesso:** notificações do painel são **pessoais**: qualquer funcionário logado lê e marca as suas (sem `exigir` de recurso; só `ContextoLoja`), nunca as de outro (404 ao tentar marcar id alheio: ignorado em silêncio na marcação em lote). Configurações de notificação e SMTP: leitura/escrita em `config_loja`. Site: sessão de cliente (SIT-20). **Módulos:** nenhum módulo desliga notificações; sem Serviços a mensagem usa "Atendimento"; sem Locais não cita local.

## 3. Banco (migração `0008_notificacoes`)

**`notificacoes`** (regras GER-04, GER-08 a GER-12, como `cliente_contas` na 0007)
| Coluna | Tipo | Null | Regra |
|---|---|---|---|
| `id`, `loja_id`, controle | padrão | | |
| `tipo` | varchar(10) | não | CHECK `cliente`/`loja` |
| `cliente_id` | uuid | sim | FK composta `(loja_id, cliente_id)`; preenchido **só** com `tipo = cliente` (CHECK) |
| `funcionario_id` | uuid | sim | FK composta; preenchido **só** com `tipo = loja` (CHECK) |
| `agendamento_id` | uuid | sim | FK composta para `agendamentos` |
| `evento` | varchar(30) | não | CHECK com os eventos de NOT-02/NOT-03 |
| `titulo` | varchar(120) | não | congelado |
| `mensagem` | varchar(1000) | não | congelada |
| `status_site` | smallint | não | default 1, CHECK 1..2 |
| `visualizada_em` | timestamptz | sim | preenchida junto com `status_site = 2` |
| `status_email` | smallint | não | CHECK 1..4 |
| `email_destino` | varchar(254) | sim | copiado na criação (NULL quando 4) |
| `email_tentativas` | smallint | não | default 0, CHECK 0..3 |
| `email_proxima_tentativa_em` | timestamptz | sim | |
| `email_enviado_em` | timestamptz | sim | |
| `email_erro` | varchar(300) | sim | |
| `status_whatsapp` | smallint | não | CHECK 1..4 (hoje sempre 4) |
| `whatsapp_erro` | varchar(300) | sim | "Envio por WhatsApp ainda não disponível." |
| `lembrete_inicio` | timestamptz | sim | só no evento `lembrete`: o `inicio` lembrado |

Índices: `(loja_id, funcionario_id, criado_em desc) WHERE tipo='loja' AND excluido_em IS NULL`; `(loja_id, cliente_id, criado_em desc) WHERE tipo='cliente' AND excluido_em IS NULL`; parcial para a fila `(email_proxima_tentativa_em) WHERE status_email = 1 AND excluido_em IS NULL`; **único** `(loja_id, agendamento_id, lembrete_inicio) WHERE evento='lembrete' AND excluido_em IS NULL`.

**`loja_configuracoes`** (colunas novas, modelo da 0006): `antecedencia_cliente_minutos int NOT NULL DEFAULT 120 CHECK 0..10080`; `smtp_ativo bool NOT NULL DEFAULT false`; `smtp_servidor varchar(255)`, `smtp_porta int CHECK IN (25,465,587,2525)`, `smtp_seguranca varchar(10) CHECK IN ('ssl','starttls')`, `smtp_usuario varchar(255)`, `smtp_senha_cifrada text` (**mascarada na auditoria**), `smtp_remetente_email varchar(254)`, `smtp_remetente_nome varchar(120)`; CHECK: `smtp_ativo` exige servidor, porta, segurança e remetente preenchidos.

`.env`: `CHAVE_CIFRA` (Fernet; obrigatória para salvar senha SMTP; sem ela, 422 "O servidor não está configurado para guardar senhas de e-mail."), `URL_PUBLICA` (opcional), `NOTIFICACOES_TAREFA` (liga a tarefa de fundo no processo da API; padrão ligada fora de `teste`), `NOTIFICACOES_INTERVALO` (s, padrão 30). Dependência nova: `cryptography`.

## 4. Contrato da API

Erros comuns de todas as rotas do painel: 401 "Faça login para continuar.", 403 de loja suspensa como as demais.

### `GET /api/loja/notificacoes?pagina=1&por_pagina=20`
- **Permissão:** funcionário logado (só as suas, `tipo = loja`).
- **Saída 200:** `{ itens: [Notificacao], total, pagina, por_pagina, nao_visualizadas: int }`, mais novas primeiro. `por_pagina` máx. 50.
  ```json
  { "id": "uuid", "evento": "novo_pedido", "titulo": "Novo pedido pelo site", "mensagem": "Maria Souza pediu Limpeza para ter 14/10 às 09:30.",
    "agendamento_id": "uuid|null", "inicio_agendamento": "datetime|null", "visualizada": false, "visualizada_em": "datetime|null",
    "status_email": 1, "status_whatsapp": 4, "criado_em": "datetime" }
  ```
  `agendamento_id`/`inicio_agendamento` `null` se o agendamento foi excluído.
- **Erros:** 422 em `pagina`/`por_pagina` inválidos ("Verifique os dados informados.").

### `GET /api/loja/notificacoes/resumo`
- **Permissão:** funcionário logado. **Saída 200:** `{ "nao_visualizadas": int }`. Leve (o front consulta a cada 60 s e ao voltar o foco da aba).

### `POST /api/loja/notificacoes/visualizar`
- **Permissão:** funcionário logado.
- **Entrada:** `{ "ids": ["uuid"] }` (1 a 100). Ids que não são do usuário, de outra loja ou inexistentes são **ignorados** (sem erro, sem revelar).
- **Saída 200:** `{ "marcadas": int, "nao_visualizadas": int }`. Idempotente (já visualizada não muda `visualizada_em`).
- **Erros:** 422 lista vazia, mais de 100 ou id inválido.

### `GET /api/loja/configuracoes/notificacoes`
- **Permissão:** `exigir("config_loja", "leitura")`.
- **Saída 200:**
  ```json
  { "antecedencia_cliente_minutos": 120,
    "email": { "ativo": false, "servidor": "string|null", "porta": "int|null", "seguranca": "ssl|starttls|null", "usuario": "string|null",
               "senha_definida": false, "remetente_email": "string|null", "remetente_nome": "string|null" },
    "whatsapp_disponivel": false,
    "atualizado_em": "datetime", "atualizado_por": "uuid|null", "atualizado_por_nome": "string|null" }
  ```

### `PUT /api/loja/configuracoes/notificacoes`
- **Permissão:** `exigir("config_loja", "escrita")`.
- **Entrada:** `antecedencia_cliente_minutos` (int 0..10080, obrigatório); `email` objeto (obrigatório): `ativo` bool; `servidor` string(255)|null (nome de host ou IP, sem esquema); `porta` 25/465/587/2525|null; `seguranca` `ssl`/`starttls`|null; `usuario` string(255)|null; `senha` string(1..255) **pode faltar** (= mantém a atual) ou `null` (= apaga); `remetente_email` e-mail|null; `remetente_nome` string(120)|null. Com `ativo = true`, servidor, porta, segurança e remetente são obrigatórios.
- **Saída 200:** igual ao GET.
- **Erros:** 403 "Você só tem permissão de leitura aqui."; 422 com `erros[]` por campo (`antecedencia_cliente_minutos`, `email.servidor` "Servidor não permitido." para endereço interno, `email.porta`, `email.remetente_email`, `email.senha` sem `CHAVE_CIFRA`).

### `POST /api/loja/configuracoes/notificacoes/testar-email`
- **Permissão:** `exigir("config_loja", "escrita")`. Usa a configuração **salva** (não a do formulário).
- **Entrada:** `{ "destino": "email" }`.
- **Saída 200:** `{ "enviado": true }` ou `{ "enviado": false, "erro": "Não foi possível conectar ao servidor de e-mail." }` (mensagem tratada, nunca a senha nem o stack).
- **Erros:** 403; 409 "Configure e ative o envio de e-mail antes de testar."; 422 destino inválido; 429 "Muitos testes seguidos. Tente de novo em alguns minutos."

### Site (HTML, back-end)
| Rota | Faz |
|---|---|
| Cabeçalho (`base.html`) | Logado: link "Avisos" com a contagem (`aria-label="Avisos, 3 não lidos"`) ao lado de "Minha conta"; alvo de toque ≥ 44 px. |
| `GET /{slug}/conta/avisos?pagina=` | Exige sessão (303 para entrar). Lista (título, mensagem, quando; destaque nas não visualizadas **desta** abertura) e marca as da página como visualizadas depois de montar a lista. Vazio: "Nenhum aviso por enquanto." `noindex`. Página fora do intervalo/estranha: primeira página, nunca 500. |

### Testes obrigatórios (backend)
- Cada evento de NOT-02/NOT-03 gera exatamente as linhas esperadas (destinatário, `tipo`, status dos canais); concluir/não compareceu/reabrir não geram; rollback da mudança de status não deixa notificação.
- Status: cliente sem e-mail = 4; loja sem SMTP = 3; WhatsApp sempre 4; falha temporária → 1 com nova tentativa → 3 após 3; sucesso → 2 (SMTP falso nos testes); dois processos não enviam o mesmo e-mail (SKIP LOCKED).
- Lembrete: janela antes/depois, uma vez só, pendente não recebe, remarcação gera novo, cancelado não recebe.
- CFG-05: cancelar/remarcar no site respeita o valor da loja (0, 120, 1440); o teste que fixava 2 h passa a ler a configuração.
- CFG-06: senha cifrada no banco, ausente da API e mascarada na auditoria; servidor interno recusado; limite do teste; leitura = 403 no PUT.
- NOT-06: funcionário não lê nem marca de outro; loja A não vê loja B; cliente vê as de todos os clientes do telefone da conta e não as de outro telefone.
- DIR-003: e-mail ao cliente e template de avisos sem `painel`/`superadmin`/`login`.

## 5. Contrato de tela

### 5.1 Painel React
- **Sino no cabeçalho** (`AppLayout.jsx`, antes de `<Usuario>`): botão com ícone de sino e contador (≥ 1 mostra o número, > 99 mostra "99+"); `aria-label` "Notificações, N não lidas". Clicar abre um **`PainelLateral`** "Notificações" com a lista (mais novas primeiro, "Carregar mais" por página). **Ao abrir**, depois de carregar a primeira página, marca como visualizadas as não visualizadas mostradas (as carregadas por "Carregar mais" também são marcadas ao aparecer); na abertura, as que eram não lidas ficam destacadas até fechar o painel. Cada item: título, mensagem, há quanto tempo/data (fuso da loja), e, se `agendamentoId`, link "Ver na agenda" (abre a agenda no dia do `inicioAgendamento`).
- **Configurações › Dados da loja**: seção nova **"Avisos e e-mail"** (formulário próprio, botão Salvar da seção): "Antecedência do cliente" (número + seletor minutos/horas; texto de ajuda: "O cliente recebe o lembrete com essa antecedência e só pode cancelar ou remarcar pelo site até esse momento."); bloco "E-mail da loja (SMTP)" com Ativo, Servidor, Porta, Segurança, Usuário, Senha (campo vazio com "Senha salva — deixe em branco para manter" quando `senhaDefinida`; botão "Remover senha"), E-mail e Nome do remetente; botão "Enviar e-mail de teste" (abre campo de destino na própria seção, mostra o resultado em `Alert`). Linha "WhatsApp: em breve" (texto, sem controle). Sem escrita: tudo só leitura, sem botões.

```
[≡ Agenda ......................  🔔3  Usuário  Sair]
                                   ┌ Notificações ─────────── × ┐
                                   │ ● Novo pedido pelo site    │
                                   │   Maria pediu Limpeza ...  │
                                   │   há 5 min · Ver na agenda │
                                   │ ○ Cancelado pelo cliente   │
                                   │ ...      [Carregar mais]   │
                                   └────────────────────────────┘
```

#### Hooks de dados
| Hook (em `frontend/src/data/`) | Retorna | Ações |
|---|---|---|
| `useNotificacoesResumo()` (consulta a cada 60 s e ao focar a aba) | `{ naoVisualizadas, carregando, erro, recarregar }` | — |
| `useNotificacoes(aberto)` (só busca com `aberto = true`; reinicia ao abrir) | `{ itens: Notificacao[], total, temMais, carregando, erro, recarregar }` | `carregarMais() → Promise<void>`, `marcarVisualizadas(ids) → Promise<{ naoVisualizadas }>` |
| `useConfigNotificacoes()` | `{ config: ConfigNotificacoes \| null, carregando, erro, recarregar }` | `salvar(dados) → Promise<ConfigNotificacoes>`, `testarEmail(destino) → Promise<{ enviado, erro }>` |

| Tela | API | Tipo | Null |
|---|---|---|---|
| `Notificacao.id`, `evento`, `titulo`, `mensagem` | mesmos nomes | string | não |
| `Notificacao.agendamentoId` | `agendamento_id` | string | sim |
| `Notificacao.inicioAgendamento` | `inicio_agendamento` | dayjs (fuso da loja) | sim |
| `Notificacao.visualizada` / `visualizadaEm` | `visualizada` / `visualizada_em` | bool / dayjs | não / sim |
| `Notificacao.statusEmail` / `statusWhatsapp` | `status_email` / `status_whatsapp` | 1–4 | não |
| `Notificacao.criadoEm` | `criado_em` | dayjs | não |
| `ConfigNotificacoes.antecedenciaClienteMinutos` | `antecedencia_cliente_minutos` | int | não |
| `ConfigNotificacoes.email` | `email` → `{ ativo, servidor, porta, seguranca, usuario, senhaDefinida, remetenteEmail, remetenteNome }` | objeto | campos internos sim |
| `ConfigNotificacoes.whatsappDisponivel` | `whatsapp_disponivel` | bool | não |
| `salvar(dados).email.senha` | `email.senha` | string \| null \| ausente | ausente = mantém |

Erros: padrão `{ status, mensagem, campos }` da skill `integracao-api` (campos `email.servidor` → `email.servidor` na tela). Falha do resumo não mostra erro (sino sem número); falha de `marcarVisualizadas` não bloqueia a lista (tenta de novo na próxima abertura).

#### Estados
Sino: carregando (sem número), zero (sem número), 1–99, 99+. Painel: carregando (esqueleto), vazio ("Nenhuma notificação por enquanto."), erro (mensagem + tentar de novo), um item, muitos (carregar mais), mensagem longa (quebra), agendamento excluído (sem link). Configurações: sem escrita (só leitura), sem senha, senha salva, ativo sem dados (erros por campo), teste ok/erro, 429.

### 5.2 Site (Jinja, backend)
`site/avisos.html` herdando `base.html`, tokens atuais, mobile first, sem JS. Item não visualizado com marcador **e** texto "Novo" (GER-28). Paginação "‹ Anteriores · Mais novos ›".

## 6. Critérios de aceite
- [ ] Cliente pede um horário pelo site: ele recebe "Pedido recebido" (sino do site e e-mail, se tiver e-mail e a loja tiver SMTP) e o profissional vê "Novo pedido" no sino do painel; WhatsApp fica 4 nas duas.
- [ ] A recepção aceita: o cliente recebe "Confirmado"; recusa ou cancela: "Cancelado", sem o motivo.
- [ ] Cliente cancela ou remarca pelo site: o profissional recebe a notificação; outro funcionário não.
- [ ] Com antecedência de 3 h, o cliente recebe um único lembrete 3 h antes e não consegue mais cancelar/remarcar pelo site depois disso (a página mostra o telefone da loja); a loja ainda consegue.
- [ ] Cliente sem e-mail: `status_email = 4`. Loja sem SMTP: 3 com o motivo. SMTP errado: tenta 3 vezes e fica 3.
- [ ] Abrir o sino marca só as que apareceram; uma que chegar depois continua contando.
- [ ] A senha SMTP nunca aparece na API, na tela nem na auditoria; servidor `127.0.0.1` é recusado em produção.
- [ ] Ninguém lê notificação de outro funcionário, de outra loja ou de outro telefone (testes).
- [ ] Sino tocável em 360 px no site e no painel; site funciona sem JS; nenhuma página/e-mail ao cliente leva ao painel.

## 7. Fora do escopo
- Envio real por WhatsApp (ABE-12; fica 4).
- E-mail em HTML/modelos editáveis pela loja; preferências do cliente para não receber.
- Tela de "notificações enviadas" para a loja acompanhar o status de e-mail de cada cliente (sugestão para depois).
- SMTP pelo SUPERADMIN (só a loja edita por enquanto).
- Trocar o provedor "painel" do código da conta (SIT-17) por e-mail/WhatsApp.

## 8. Decisões e perguntas
- Coordenador: loja sem SMTP ativo grava `status_email = 3` com motivo (e não 1), para não disparar e-mails velhos quando a loja configurar depois.
- Coordenador: o prazo CFG-05 vale para **cancelar e remarcar** (hoje os dois usam a mesma constante).
- Coordenador: padrão de 120 min mantém o comportamento atual.
- Coordenador: tarefa de fundo dentro do processo da API (lifespan), segura com vários processos; comando separado para rodar fora dele fica a cargo do backend se for simples.

- **Divergências do frontend-ui aceitas (2026-10-06):** `campos` dos erros no formato do projeto (`ErroApi`, lista `{campo, mensagem}` com o nome da API, ex. `email.servidor`); depois de marcar, o sino reconsulta o resumo (ignora o `nao_visualizadas` devolvido); link "Ver na agenda" usa `?dia=AAAA-MM-DD` na Agenda; porta 465 sugere `ssl`, as outras `starttls`. **Decisão do coordenador:** em acesso de suporte (SUPERADMIN acessando a loja), abrir o sino **não marca** como visualizadas (front não chama; back-end responde `marcadas: 0` sem alterar). Texto das mensagens usa horas no padrão do painel ("9h30", UI-18).
- **Divergências do backend aceitas (2026-10-06):** a configuração também traz `criado_em` (GER-21); `testar-email` com senha que não decifra (chave trocada) = 200 `{enviado:false, erro:"Não foi possível ler a senha do e-mail da loja. Salve a senha de novo."}`; em produção, servidor que não resolve no DNS = 422 "Servidor não permitido."; `processar` recebe fábrica de sessões; avisos do site com data "dd/mm/aaaa às 9h30"; lojas suspensas/canceladas não são processadas pela tarefa (provisório); função `notificacoes_lojas_com_trabalho` SECURITY DEFINER só devolve ids de lojas; comando `python -m scripts.notificacoes [--uma-vez]` roda a tarefa fora da API.

## 9. Histórico de revisão
- **2026-10-06 · rodada 1 · REPROVADO** (pytest 1146 ✔ / 1 ✘; ruff, lint e build ok; DIR-001 a 004 ok; front sem achados). Achados, todos do backend:
  - A1 (bloqueante): `test_site_paginas.py::test_fluxo_completo_sem_js` não conhece a auditoria `('notificacoes','inserir')`.
  - A2 (bloqueante): limite de 15 s é por operação de socket; uma loja com SMTP lento/fora segura a fila de todas (e o testar-email prende thread). Correção: prazo total por envio, interromper o lote da loja na primeira falha de conexão (devolvendo à fila sem gastar tentativa), orçamento de tempo por loja.
  - A3 (bloqueante): reserva calculada com o `agora` do início do ciclo e menor que o pior caso → envio em dobro. Correção: relógio do momento da reserva, reserva > pior caso, token de reserva conferido ao gravar o resultado.
  - A4 (importante): trocar servidor/usuário mantém a senha e o teste a entrega a outro servidor. **Decisão do coordenador:** mudar `servidor` ou `usuario` com senha salva exige mandar `senha` de novo (422 em `email.senha`: "Informe a senha de novo ao trocar o servidor ou o usuário."); a tela avisa no texto de ajuda.
  - A5 (importante): lembrete pendente sai depois de cancelado/remarcado. **Decisão do coordenador:** na reserva, lembrete de agendamento que não está mais `agendado`/`confirmado`, com `inicio` ≠ `lembrete_inicio` ou já iniciado vira 3 ("Aviso vencido: o agendamento mudou."); qualquer e-mail pendente com mais de 24 h ou cujo agendamento já começou vira 3 ("Aviso vencido.").
  - Sugestões aplicadas na mesma correção: HEAD não marca avisos; `REVOKE` da função SECURITY DEFINER de PUBLIC; IPv4 embutido em IPv6 (NAT64, `::a.b.c.d`) conferido; mensagem certa para e-mail não-ASCII sem SMTPUTF8; DNS do PUT fora da transação. Não aplicadas: volume de auditoria; e-mail "agendado" para horário passado.
- **2026-10-06 · rodada 2 · REPROVADO** (pytest 1177 ✔; ruff, lint e build ok; DIR ok). A1, A3, A4, A5 e sugestões resolvidos e comprovados; A2 resolvido em parte. Achado novo do backend:
  - A6 (bloqueante): o vigia dispara uma vez e fecha `conexao.sock`; se disparar durante o handshake TLS (STARTTLS: socket já desligado por `detach`; SMTPS: `sock` ainda `None`), nada mais limita o envio (46,7 s com prazo 15 s), e o `pool.map` faz uma loja presa adiar o ciclo de todas. Correção: derrubar a conexão TCP bruta (`shutdown(SHUT_RDWR)` no socket guardado antes do TLS) e conferir o prazo em toda operação depois do disparo; o ciclo não espera loja atrasada (loja ainda em envio fica de fora do próximo ciclo, as outras seguem); teste com o prazo estourando em cada fase (DNS/connect, handshake, depois do handshake), STARTTLS e SMTPS.
  - Sugestão aplicada junto: conferir a permissão `config_loja` escrita (sem banco aberto, ou com limite de taxa) antes da consulta DNS do PUT.
- **2026-10-06 · rodada 3 · APROVADO** (pytest completo 1184 ✔ + 3 pulados por porta 2525 ocupada pelo revisor; reexecutados com a porta livre: 84 ✔; ruff ok; lint e build ok na rodada 2, sem mudança no front). A6 resolvido (15 s em todas as fases, STARTTLS e SMTPS; ciclo não espera loja presa); sem vazamento de thread/socket em 200 envios. Sugestões não aplicadas: `Despachante.encerrar()` não limpa a lista de lojas em andamento das tarefas canceladas (só importa se reaproveitado no mesmo processo); `scripts/notificacoes.py` não encerra o despachante no Ctrl+C (espera até ~75 s).
