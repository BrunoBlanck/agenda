# Conta do cliente no site: login, meus agendamentos, remarcar e cancelar

- **Slug:** conta-cliente · **Branch:** feat/conta-cliente · **Status:** aprovada
- **Área:** site do consumidor (+ uma seção pequena no painel da loja, tela Clientes)
- **Pedido original (2026-10-06):** "1) o cliente tem que ter de fato uma conta com login com usuário e senha, pode fazer login desde o começo ou pode ser igual hoje somente no final (cuidado com quem já tem cadastro na loja: sincroniza SEMPRE PELO TELEFONE, login = telefone + senha). 2) logado vê os próprios agendamentos, atuais e histórico. 3) pode remarcar e cancelar por ali. Remarcar precisa de confirmação novamente, cancelamento não."
- **Decisões do usuário (2026-10-06):** conta **por loja**; telefone confirmado por **código** (provedor trocável; por enquanto o código **aparece no painel da loja**, que repassa ao cliente, em vez de SMS/WhatsApp); remarcar **troca o horário na hora e volta a `pendente`** (horário antigo liberado); cancelar/remarcar **até 2 h antes** (provisório).

Entrega em duas fases na mesma branch: **Fase A** (conta, código, login, meus agendamentos, login no fluxo de agendamento, seção no painel) e **Fase B** (cancelar e remarcar).

## 1. Objetivo
O cliente final cria uma senha para o seu telefone na loja, entra com telefone + senha e acompanha os próprios agendamentos (próximos e histórico), podendo cancelar ou remarcar sem ligar para a loja. Pode entrar antes de agendar (o passo 3 já vem preenchido) ou agendar como hoje, sem conta. Uso frequente, quase sempre pelo celular.

## 2. Regras de negócio

| Código | Regra | Onde é garantida |
|---|---|---|
| SIT-01, SIT-09, SIT-10, SIT-12 | Continuam valendo em todas as páginas novas (404 da loja indisponível, funciona sem JS, limites, renderizado pelo back-end) | rotas HTML |
| SIT-07 | Telefone só dígitos, mesma loja; antes de o telefone ser confirmado, nada revela se ele tem cadastro ou conta | serviço + textos |
| AGE-07/08/09/12/13 | Remarcação passa pelas mesmas regras de horário do site (SIT-04/05) | serviço + banco |
| AGE-19 | Cancelar exige motivo: o site grava o motivo fixo "Cancelado pelo cliente pelo site." | serviço |
| DIR-003 | Nenhuma página nova leva ao painel/SUPERADMIN; a palavra "login" não aparece nos templates (usar "Entrar", "Minha conta") | template + teste |
| **SIT-16** (nova) | **Conta do cliente por loja, identificada pelo telefone** (só dígitos, 10 ou 11). Uma conta por (loja, telefone). A conta **não** pertence a um registro de cliente: ela enxerga os agendamentos de **todos os clientes da loja com aquele telefone** (comparação por dígitos, como SIT-07). Se a loja trocar o telefone de um cliente no painel, os agendamentos dele passam a seguir o telefone novo (sincroniza sempre pelo telefone). | banco (único) + serviço |
| **SIT-17** (nova) | **Criar conta e trocar a senha exigem confirmar o telefone com um código** de 6 dígitos: vale 15 min, no máximo 5 tentativas erradas, pedir um novo invalida o anterior. Limites: 1 código por telefone a cada 60 s, 5 por telefone por hora, 10 por IP por hora (além de `limite_site`). O envio passa por um **provedor trocável** (`EnvioCodigo`); o provedor atual, **"painel"**, só grava o código, que a loja vê no painel (provisório até existir SMS/WhatsApp, ABE-12). A página diz "peça o código à loja" enquanto o provedor for "painel". | serviço + banco |
| **SIT-18** (nova) | O mesmo caminho serve para **criar conta** e **esqueci minha senha**: telefone → código → nova senha. Só depois do código certo a página pode revelar se o telefone já tem cadastro (pede nome e sobrenome **apenas** se não houver nenhum cliente com aquele telefone; nesse caso cria o cliente com canal `site`). Cliente já cadastrado: nada do cadastro muda (SIT-07). | serviço |
| **SIT-19** (nova) | **Senha**: 8 a 128 caracteres, diferente dos dígitos do telefone; Argon2 (`app/auth/senhas.py`). Entrar = telefone + senha, com o bloqueio progressivo de `BloqueioLogin` (chave `site`, slug, dígitos) e `limite_login` por IP. Mensagem de erro única: "Telefone ou senha incorretos." | serviço + rota |
| **SIT-20** (nova) | **Sessão por cookie** `HttpOnly`, `SameSite=Lax`, `Path=/{slug}`, `Secure` fora de `AMBIENTE=desenvolvimento`, com token assinado (tipo `cliente`, loja, conta, versão), validade **30 dias** (provisório). Trocar a senha ou a loja remover o acesso **incrementa a versão** e derruba todas as sessões. Cada página confere loja, conta e versão. Todo `POST` confere `mesma_origem` (como o envio do pedido). | serviço + rota |
| **SIT-21** (nova) | **Meus agendamentos**: "Próximos" = `pendente`/`agendado`/`confirmado` com `fim` ≥ agora (início crescente, até 50); "Histórico" = o resto (início decrescente, 20 por página). Mostra serviço (ou "Atendimento"), dia, hora, profissional, local (nome, nunca link), preço e a situação. Agendamentos excluídos não aparecem. O motivo de recusa/cancelamento da loja **não** aparece (pode ser anotação interna). | serviço + template |
| **SIT-22** (nova) | **Agendar logado**: o passo 3 não pede nome/telefone (mostra "Agendando como <nome>" e só Observações); o pedido usa o cliente mais antigo da loja com o telefone da conta (mesma regra de `_cliente`) e passa pelos mesmos limites de pedidos e de pendentes. Sem conta, o fluxo é igual ao de hoje, com um link "Já tem conta? Entrar" que volta ao mesmo passo depois de entrar, e no fim um convite para criar senha. | rota + serviço |
| **SIT-23** (nova) | **Cancelar pelo site**: só `pendente`, `agendado` ou `confirmado`, e só até **2 h antes do início** (constante `ANTECEDENCIA_CLIENTE` = 2 h, provisória, ABE-11). Vira `cancelado` na hora (sem aceite da loja), motivo fixo, `app.origem = 'site'`. Uma página "Tem certeza?" antes (sem JS, `GET` mostra, `POST` cancela). | serviço + rota |
| **SIT-24** (nova) | **Remarcar pelo site**: mesmas situações e mesmo prazo da SIT-23; mantém serviço, preço congelado e a **duração atual** (`fim − inicio`); o cliente escolhe profissional (entre os habilitados e ativos; "qualquer profissional" permitido) e um horário **oferecido** (SIT-04), sem contar o próprio agendamento como ocupado. Ao confirmar, o mesmo agendamento muda `inicio`/`fim`/profissional/local e **volta a `pendente`** (a loja aceita ou recusa como um pedido novo, AGE-17); o horário antigo fica livre na hora. Serviço inativo ou removido, ou módulo/locais que impeçam: "Para remarcar este horário, fale com a loja." (cancelar continua possível). | serviço + rota + banco |
| **AGE-25** (nova) | Transições exclusivas do cliente pelo site: `agendado`/`confirmado` → `pendente` (remarcação, SIT-24) e `pendente` → `pendente` com novo horário. Nenhum caminho do painel usa essas transições. | serviço |
| **CLI-NN** (nova; o backend usa o próximo código livre de `cadastros.md`) | No painel, **ver o código pendente** do telefone e **remover o acesso ao site** exigem **escrita** em `clientes`. | rota + tela |

**Diretrizes aplicáveis:** `DIR-003` (site sem caminho para o painel) no site; `DIR-001` (painel lateral) e `DIR-002` (identidade visual) na seção nova do painel React.

**Acesso:** site público + sessão de cliente. Painel: escrita em `clientes` para ver códigos e remover acesso. **Módulos:** Serviços desligado → itens "Atendimento" e remarcação com a duração atual entre os funcionários do SIT-08; Locais ligado → local escolhido pelo servidor como no pedido.

## 3. Banco (migração `0007_conta_cliente`)

Toda tabela nova segue GER-04 e GER-08 a GER-12 (loja_id + RLS, colunas de controle, triggers de auditoria, exclusão lógica), como `clientes`.

**`cliente_contas`** — uma por (loja, telefone)
| Coluna | Tipo | Null | Regra |
|---|---|---|---|
| `id`, `loja_id`, controle | padrão | | |
| `telefone_digitos` | varchar(11) | não | CHECK `^[0-9]{10,11}$`; **único** `(loja_id, telefone_digitos) WHERE excluido_em IS NULL` |
| `senha_hash` | text | não | Argon2; **nunca** na auditoria (mascarar como as senhas de funcionário) |
| `sessao_versao` | int | não | default 1, CHECK ≥ 1 |
| `ultimo_acesso_em` | timestamptz | sim | atualizado ao entrar |

Remover o acesso (painel) = exclusão lógica da conta + versão incrementada. Criar conta de novo no mesmo telefone depois disso cria outra linha.

**`cliente_codigos`** — códigos de confirmação
| Coluna | Tipo | Null | Regra |
|---|---|---|---|
| `id`, `loja_id`, controle | padrão | | |
| `telefone_digitos` | varchar(11) | não | mesmo CHECK; índice `(loja_id, telefone_digitos, criado_em desc)` |
| `codigo` | char(6) | não | só dígitos (CHECK). Guardado legível **de propósito** (o provedor "painel" precisa mostrar); curta duração. Na auditoria, mascarado |
| `expira_em` | timestamptz | não | `criado_em + 15 min` |
| `tentativas` | smallint | não | default 0, CHECK 0..5 |
| `usado_em` | timestamptz | sim | |
| `invalidado_em` | timestamptz | sim | preenchido quando um novo código é pedido |
| `provedor` | varchar(20) | não | `painel` por enquanto |

"Pendente" = não usado, não invalidado, `expira_em` > agora e `tentativas` < 5.

`agendamentos`: nenhuma coluna nova (a remarcação aparece na auditoria com origem `site`).

## 4. Contrato

### 4.1 Páginas HTML do site (back-end)
Mesmas regras de cabeçalho, CSP, `noindex` (em todas as páginas de conta), `limite_site`, 404 de loja indisponível e "parâmetro estranho nunca dá 500" da `site-agendamento.md`. Todo `POST` exige `mesma_origem` (403 HTML senão). Formulários com erro: 200 com valores (menos senhas e código) e mensagem ao lado do campo + resumo no topo. Sem sessão válida nas páginas que exigem conta: 303 para `/{slug}/conta/entrar?voltar=<caminho>`.

`voltar`: só caminhos relativos começando com `/{slug}/` e casando com a lista de páginas do site (regex fechada; nunca `//`, esquema ou outro slug); senão `/{slug}/conta`.

| Rota | Fase | Faz |
|---|---|---|
| `GET /{slug}/conta/entrar` · `POST` | A | Telefone + senha (+ `voltar`). Sucesso: cookie (SIT-20) e 303 para `voltar`. Erro: "Telefone ou senha incorretos." Bloqueio: 429 com o formulário e o tempo. Links "Esqueci minha senha" e "Criar conta" (ambos `/conta/criar`). Já logado: 303 para `/conta`. |
| `POST /{slug}/conta/sair` | A | Apaga o cookie; 303 para `/{slug}`. |
| `GET /{slug}/conta/criar` · `POST` | A | Passo 1: telefone. `POST` gera o código (SIT-17) e responde **igual** exista ou não cadastro/conta: 303 para `/conta/codigo` levando um **token assinado** (telefone, loja, 15 min) em campo oculto/parâmetro `t`. Limite de códigos: 429 com o formulário. |
| `GET /{slug}/conta/codigo?t=` · `POST` | A | Passo 2: "Digite o código de 6 dígitos" + texto do provedor ("Por enquanto, peça o código à <loja> pelo telefone ou WhatsApp."). Errado: "Código incorreto ou vencido." (conta tentativa). 5 erradas/vencido: pede para gerar outro. Certo: marca usado e 303 para `/conta/senha` com token assinado "telefone verificado" (15 min, uso único: amarrado ao id do código). Token `t` inválido/vencido: 303 para `/conta/criar`. |
| `GET /{slug}/conta/senha?v=` · `POST` | A | Passo 3: Senha + Repetir senha; Nome e Sobrenome **só** se não houver cliente com o telefone. Salva/atualiza a conta (versão +1 se já existia), cria o cliente se preciso, inicia a sessão e 303 para `voltar` ou `/conta`. |
| `GET /{slug}/conta?pagina=` | A | Minha conta: "Olá, <nome>", Próximos, Histórico paginado (SIT-21), botão "Sair", link "Agendar" (`/{slug}`). Na Fase B, cada item elegível ganha "Remarcar" e "Cancelar"; inelegível por prazo mostra "Para alterar, fale com a loja: <telefone>". |
| Passo 3 do agendamento (`/agendar/dados`, `POST /agendar`) | A | SIT-22. Logado: formulário só com Observações; a validação do `POST` não exige nome/telefone quando há sessão válida (sessão vencida no envio → volta ao passo 3 sem sessão, com aviso). Sem conta: link "Já tem conta? Entrar" (`voltar` = passo 3 atual). `/agendar/pronto`: sem sessão, "Crie sua senha para acompanhar seus agendamentos" → `/conta/criar`; logado, "Ver meus agendamentos". |
| Cabeçalho do site | A | Link "Entrar" (sem sessão) ou "Minha conta" (com sessão) em todas as páginas da loja. |
| `GET /{slug}/conta/agendamentos/{id}/cancelar` · `POST` | B | Resumo + "Cancelar este agendamento?" e botão. `POST`: SIT-23, 303 para `/conta` com aviso "Agendamento cancelado." |
| `GET /{slug}/conta/agendamentos/{id}/remarcar?profissional=&dia=` | B | Igual ao passo 2 (faixa de 31 dias, filtro de profissional), título "Remarcar: <serviço>", mostrando o horário atual. Cada horário leva à confirmação. |
| `GET /{slug}/conta/agendamentos/{id}/remarcar/confirmar?profissional=&inicio=&local=` · `POST` | B | "De <atual> para <novo>", aviso "A loja vai confirmar o novo horário. O horário atual fica livre." e botão "Confirmar remarcação". `POST`: SIT-24, 303 para `/conta` com aviso "Pedido de remarcação enviado." Horário não oferecido/ocupado (inclusive 23P01): 303 para a escolha com `aviso=ocupado`. |

Agendamento de outro telefone, de outra loja, inexistente ou excluído: **404 HTML** (nunca 403). Fora do prazo ou situação final: página com "Este agendamento não pode mais ser alterado pelo site. Fale com a loja: <telefone>." (status 409). Avisos depois de redirecionar: parâmetro `aviso` com códigos fixos (`cancelado`, `remarcado`, `ocupado`, `prazo`, `sessao`), como já existe.

### 4.2 API do painel (JSON)

#### `GET /api/loja/clientes/codigos-site`
- **Permissão:** `exigir("clientes", "escrita")`. Registrada **antes** de `/{id}`.
- **Saída 200:** lista dos códigos **pendentes** da loja, mais novo primeiro (máx. 100, sem paginação):
  ```json
  [{ "telefone": "(11) 98888-1111", "codigo": "482913", "expira_em": "datetime", "criado_em": "datetime",
     "clientes": [{ "id": "uuid", "nome": "Maria Souza" }] }]
  ```
  `clientes` = clientes da loja com aquele telefone (pode ser `[]`: telefone ainda sem cadastro).
- **Erros:** 401, 403 (sem escrita: "Você só tem permissão de leitura aqui."), 403 de loja suspensa como as demais.

#### `GET /api/loja/clientes/{id}/conta-site`
- **Permissão:** `exigir("clientes", "escrita")`.
- **Saída 200:**
  ```json
  { "possui_conta": true, "criada_em": "datetime|null", "ultimo_acesso_em": "datetime|null",
    "codigo_pendente": { "codigo": "482913", "expira_em": "datetime" } }
  ```
  `criada_em`/`ultimo_acesso_em` `null` sem conta; `codigo_pendente` `null` sem código pendente. Tudo pelo telefone atual do cliente.
- **Erros:** 401, 403, 404 "Cliente não encontrado." (outra loja/inexistente/excluído).

#### `DELETE /api/loja/clientes/{id}/conta-site`
- **Permissão:** `exigir("clientes", "escrita")`. Remove a conta do telefone do cliente (SIT-20: exclusão lógica + versão +1) e invalida códigos pendentes do telefone.
- **Saída:** 204.
- **Erros:** 401, 403, 404 "Cliente não encontrado.", 404 "Este cliente não tem acesso ao site."

### 4.3 Testes obrigatórios (backend)
- Criar conta (telefone novo e telefone já cadastrado), código errado/vencido/5 tentativas/novo invalida o anterior, limites de código (telefone e IP), resposta igual com e sem cadastro, token `t`/`v` adulterado/vencido/reusado/de outra loja.
- Entrar/sair, bloqueio progressivo, cookie com flags certas, versão derrubando sessão (troca de senha e remoção pelo painel), cookie de uma loja não vale em outra.
- SIT-16: dois clientes com o mesmo telefone aparecem na mesma conta; trocar o telefone no painel tira os agendamentos da conta.
- SIT-21: próximos/histórico, paginação, excluídos fora, sem motivo de cancelamento, sem link de local.
- SIT-22: pedido logado sem nome/telefone, limites valem, `voltar` aceita só caminhos do site (open redirect testado).
- SIT-23/24 e AGE-25: prazo de 2 h (antes/depois), situações finais, agendamento de outro telefone/loja = 404, remarcação volta a `pendente` e libera o horário antigo, o próprio horário não conta como ocupado, corrida (23P01), serviço inativo bloqueia remarcar mas não cancelar, Serviços desligado e Locais ligado, auditoria com origem `site`.
- Painel: códigos pendentes e conta-site com escrita; leitura = 403; outra loja = 404; senha e código mascarados na auditoria.
- `POST` de outro host = 403 em todas as páginas novas. DIR-003: nenhum template contém `painel`, `superadmin` ou `login`.

## 5. Contrato de tela

### 5.1 Site (templates Jinja, backend)
Templates novos em `backend/app/templates/site/` herdando `site/base.html`, com os tokens e cores atuais (SIT-09/13/15), mobile first, sem JS obrigatório. Campos: telefone `type="tel" autocomplete="tel"`; senha `autocomplete="current-password"` (entrar) / `"new-password"` (definir); código `inputmode="numeric" autocomplete="one-time-code" maxlength="6"`. Acessibilidade como na `site-agendamento.md`.

```
[topo da loja ............................ Minha conta]
Olá, Maria                                   [Sair]
Próximos
 ┌─────────────────────────────────────────────┐
 │ Limpeza · ter 14/10 · 09:30                 │
 │ Dra. Ana · Sala 2 · R$ 120,00               │
 │ Aguardando confirmação  [Remarcar][Cancelar]│
 └─────────────────────────────────────────────┘
Histórico
 Limpeza · 02/09 · Concluído
 ...                                  ‹ Anterior  Próxima ›
[Agendar novo horário]
```
Estados: sem próximos ("Você não tem horários marcados." + Agendar), histórico vazio, muitos itens (paginação), fora do prazo (texto com telefone da loja), avisos de retorno, sessão expirada.

### 5.2 Painel React (tela Clientes) — frontend-ui + frontend-dev
- No `PainelFormulario` de **edição** de cliente, com escrita em `clientes`, uma seção **"Acesso ao site"**: "Sem conta no site" ou "Conta criada em <data> · último acesso <data/—>"; se houver código pendente, o código em destaque (fonte grande, monoespaçada) com "vale até HH:MM" e o texto "Passe este código ao cliente para ele confirmar o telefone no site."; botão "Remover acesso ao site" (com `Popconfirm`: "O cliente sai de todos os aparelhos e precisará criar a senha de novo."). Botão "Atualizar" na seção. Sem escrita: a seção não aparece.
- No cabeçalho da tela Clientes, com escrita: botão **"Códigos do site"** que abre um `PainelLateral` com a lista de códigos pendentes (telefone, código, nome(s) do cliente ou "Sem cadastro ainda", vale até) e botão "Atualizar". Vazio: "Nenhum código aguardando."
- DIR-001 (painel lateral) e DIR-002 (só tokens, identidade "agenda de papel").

#### Hooks de dados
| Hook (em `frontend/src/data/`) | Retorna | Ações |
|---|---|---|
| `useContaSiteCliente(clienteId)` (não busca com `clienteId` nulo) | `{ conta: ContaSite \| null, carregando, erro, recarregar }` | `removerAcesso() → Promise<void>` |
| `useCodigosSite(ativo)` (só busca com `ativo = true`) | `{ itens: CodigoSite[], carregando, erro, recarregar }` | — |

| Tela | API | Tipo | Null |
|---|---|---|---|
| `ContaSite.possuiConta` | `possui_conta` | bool | não |
| `ContaSite.criadaEm` | `criada_em` | dayjs (fuso da loja) | sim |
| `ContaSite.ultimoAcessoEm` | `ultimo_acesso_em` | dayjs | sim |
| `ContaSite.codigoPendente` | `codigo_pendente` → `{ codigo, expiraEm }` | objeto | sim |
| `CodigoSite.telefone` | `telefone` | string | não |
| `CodigoSite.codigo` | `codigo` | string | não |
| `CodigoSite.expiraEm` / `criadoEm` | `expira_em` / `criado_em` | dayjs | não |
| `CodigoSite.clientes` | `clientes[] {id, nome}` | lista | não (pode ser vazia) |

Erros: padrão `{ status, mensagem, campos }` da skill `integracao-api`; 403 mostra a mensagem; 404 em `removerAcesso` recarrega a seção.

Estados: carregando (esqueleto na seção/lista), erro (mensagem + tentar de novo), sem conta, com conta sem código, só código (sem conta ainda), lista vazia, muitos códigos, código vencendo (só mostra o horário; o back-end decide).

## 6. Critérios de aceite
- [ ] Em `/clinica-sorriso`, "Entrar" → "Criar conta" com o telefone da Maria do seed; a recepção vê o código na ficha da Maria (e em "Códigos do site"); com o código, a Maria define a senha e vê os agendamentos dela, inclusive os criados no painel.
- [ ] Telefone novo: depois do código, a página pede nome e sobrenome e o cliente aparece no painel com canal site.
- [ ] Antes do código, nenhuma página diz se o telefone tem cadastro ou conta.
- [ ] Entrar com telefone + senha funciona com ou sem máscara; senha errada várias vezes bloqueia por um tempo.
- [ ] Logado, o passo 3 só pede observações e o pedido cai no cliente certo; sem conta, o fluxo de hoje continua igual, com "Já tem conta? Entrar" voltando ao mesmo passo.
- [ ] Cancelar um horário a mais de 2 h: some de Próximos, vai ao Histórico como Cancelado e o painel mostra cancelado com o motivo do site; a menos de 2 h, só aparece o telefone da loja.
- [ ] Remarcar um confirmado: escolhe novo horário, confirma, ele volta a "Aguardando confirmação", o horário antigo fica livre no site e no painel, e a loja aceita no painel como um pedido.
- [ ] Trocar a senha (esqueci a senha) ou a loja "Remover acesso" desconecta o cliente em todos os aparelhos.
- [ ] Um cliente nunca vê nem altera agendamento de outro telefone ou de outra loja (testes automatizados).
- [ ] Tudo funciona com JavaScript desligado e em 360 px; nenhuma página leva ao painel (DIR-003).
- [ ] No painel, quem só tem leitura em Clientes não vê códigos nem a seção "Acesso ao site".

## 7. Fora do escopo
- Envio real do código por SMS/WhatsApp (só a interface do provedor; ABE-12).
- Prazo configurável por loja (constante por enquanto).
- Editar o próprio cadastro pelo site (nome, e-mail).
- Conta única entre lojas.
- Marcar no painel que o pendente veio de uma remarcação (fica na auditoria) — sugestão para depois.

## 8. Decisões e perguntas
- Decisões do usuário: ver o topo. Provisórias (constantes fáceis de trocar): prazo de 2 h, sessão de 30 dias, código de 15 min/5 tentativas, limites de código.
- Coordenador: a conta é por **telefone** e não por registro de cliente (não há telefone único em `clientes`; assim o "sincroniza sempre pelo telefone" vale também para cadastros duplicados e para troca de telefone no painel).
- Coordenador: o código fica legível no banco por causa do provedor "painel"; ao trocar por SMS/WhatsApp, guardar só o hash.
- Coordenador: login de cliente inativo é permitido (ABE-04 segue: o pedido não reativa o cliente).
- **Divergências do backend (Fase A) aceitas (2026-10-06):** `t`/`v` levam o id do código assinado (HMAC, loja + passo, 15 min), nunca o telefone; `v` é de uso único e pedir código novo derruba um `v` ainda não usado; logado num telefone sem nenhum cliente, o passo 3 pede nome e sobrenome (sem telefone); o link "Entrar" do cabeçalho leva `voltar` = página atual; mensagem de bloqueio própria ("Muitas tentativas. Aguarde N minuto(s)…", sem "login", DIR-003); código fora do formato não conta tentativa; limite de 10 códigos por IP é global (todas as lojas); pedido logado repetido (telefone + profissional + início + observações, 10 min) leva à confirmação já gravada; criar conta num telefone já cadastrado não acrescenta o canal `site` (só o pedido acrescenta); título "Nova senha" quando o telefone já tem conta (só depois do código). Cookie `sessao_cliente`. Regra de acesso do painel = **CLI-06**.
- **Divergências/decisões do backend (Fase B) aceitas (2026-10-06):** remarcar com Locais desligado limpa o local antigo (e `link_reuniao` quando o local muda), como o pedido do site; escolher o mesmo horário volta com aviso `mesmo` (se já `pendente`, trata como clique repetido → `aviso=remarcado`); cancelar de novo um cancelado pelo site → `aviso=cancelado` (cancelado pela loja → 409); avisos novos `horario` e `mesmo`; a página "fale com a loja" da remarcação é 409 com telefone e link para cancelar; o botão Remarcar aparece em todo item alterável (a impossibilidade é explicada na página de remarcar); a remarcação não passa pelo limite de pendentes por telefone; sem o módulo Serviços o título usa o nome do serviço que o agendamento tem.
- **Divergências do frontend-ui aceitas (2026-10-06):** os dois hooks também devolvem `atualizando: bool` (recarga com dados já na tela; opcional, sem ele a tela funciona); `campos` dos erros segue o formato do projeto (`ErroApi`, lista `{campo, mensagem}`); hora no padrão do painel ("vale até 16h28", UI-18); filtro local por telefone/nome no painel "Códigos do site" com mais de 6 itens; código mostrado como "482 913" com botão de copiar (copia só os dígitos), fonte `--fonte-codigo`.

## 9. Histórico de revisão
- **2026-10-06 · rodada 1 · REPROVADO** (1028 testes verdes; ruff, lint e build ok; DIR-001/002/003 ok). Achados, todos do backend:
  - A1 (bloqueante): dígitos Unicode (`²`, árabes) em `pagina`, `codigo` e `telefone` → 500 ou 422 em JSON. Correção: só ASCII.
  - A2 (bloqueante): deadlock entre `enviar_senha` (trava código → telefone) e `gerar_codigo`/`remover_acesso` (telefone → código), 11 de 12 rajadas. Correção: mesma ordem (telefone primeiro) + 40P01/40001 tratados nas páginas da conta.
  - A3 (importante): terceiro invalida o código da vítima e esgota o limite por telefone (negação de serviço). **Decisão do coordenador:** pedir código com um pendente válido **não gera outro** (mesma resposta, o mesmo código continua valendo); o limite por telefone conta só códigos realmente gerados; intervalo de 60 s por (telefone, IP); tentativas erradas limitadas a 5 por (código, IP) e 20 no total por código.
  - A4 (importante): testes dos três casos.
  - Sugestão aplicada: limite de "entrar" por IP do site separado do limite do painel. Sugestões não aplicadas: "Sair" revogar no servidor (derrubaria os outros aparelhos; fica para "sair de todos os aparelhos"); risco de engenharia social registrado no ABE-12.
- **2026-10-06 · rodada 2 · APROVADO** (1042 testes; ruff, lint e build ok; DIR-001/002/003 ok). A1 a A4 resolvidos e comprovados de novo; sem regressão em `app/erros.py` (erro de banco fora de `/api` responde HTML) nem no `so_digitos` ASCII. Risco residual aceito pelo coordenador como provisório (enquanto o provedor for "painel"): com 4 IPs dá para esgotar as 20 tentativas de um código, e um telefone visado continuamente recebe até 100 palpites/hora (≈7%/mês de acertar um código). Registrado no ABE-12; opções para depois: total por código menor, teto de erros por telefone, aviso à loja.
