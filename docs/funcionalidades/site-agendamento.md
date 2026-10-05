# Site do consumidor: agendamento online

- **Slug:** site-agendamento · **Branch:** feat/site-agendamento · **Status:** em revisão (rodada 2)
- **Área:** site do consumidor
- **Pedido original:** "Preciso de uma tela para o cliente final conseguir fazer os agendamentos." Hoje `/{slug}` mostra só "Agendamento online em breve" (SIT-11). Referência visual: o protótipo React antigo (cabeçalho colorido com nome/endereço/telefone, passos Serviço → Horário → Seus dados → Pronto, faixa de dias com a quantidade de horários, filtro "Qualquer profissional").

## 1. Objetivo
O cliente final abre `/{slug}` (geralmente pelo celular, vindo do Instagram/WhatsApp da loja), escolhe o serviço, o dia e o horário, informa nome e telefone e envia o pedido. A loja confirma depois no painel (AGE-17). Uso diário, por pessoas sem cadastro e sem login.

## 2. Regras de negócio
| Código | Regra | Onde é garantida |
|---|---|---|
| SIT-01 | Loja inexistente, excluída, suspensa ou cancelada → página 404 em todas as páginas do fluxo | rota HTML (mesma checagem de `/api/site`) |
| SIT-02 | Só dados públicos: nada de clientes, links de locais online, e-mails de funcionários | template/serviço |
| SIT-03 | Fluxo: serviço → profissional (opcional, "qualquer profissional") → dia e horário → dados → confirmação | rotas HTML |
| SIT-04 | Horários livres calculados no servidor com as regras do painel (reusar `services/horarios_livres.py`, sem duplicar) | serviço |
| SIT-05 | Pedido só num horário **oferecido**; corrida entre dois pedidos → banco recusa (409) e a página volta à escolha de horário com aviso | serviço + rota |
| SIT-06 | Pedido vira agendamento `pendente`, `origem = site`, `app.origem = 'site'` (reusar a mesma função da rota `POST /api/site/{slug}/agendamentos`) | serviço |
| SIT-07 | Cliente identificado pelo telefone; existente não tem nada alterado nem devolvido | serviço |
| SIT-08 | Sem o módulo Serviços: passo 1 some, vai direto para o "Atendimento" genérico | rota |
| SIT-09 | Identidade própria por tipo de loja (tokens por tipo), mobile first, poucos passos, **funciona sem JS**; JS só melhora | templates/CSS |
| SIT-10 | Proteção contra abuso: as páginas HTML do fluxo entram nos mesmos limites de `app/limites.py` (`limite_site` e, no envio, `limite_site_pedido`) e no limite de pendentes por telefone | rota |
| SIT-11 | **Substituída por SIT-12** (a página provisória sai) | — |
| SIT-12 (nova) | O site do consumidor em `/{slug}` é o fluxo de agendamento descrito aqui, renderizado pelo back-end. Endereços do fluxo: seção 4. Qualquer outro `/{slug}/...` (menos `painel`) continua 404 | rota HTML |
| DIR-003 | Nenhum link, texto ou endereço para o painel, login de funcionário ou SUPERADMIN | template + teste |

**Diretrizes aplicáveis:** `DIR-003` (site sem caminho para o painel). `DIR-001`/`DIR-002` são dos painéis React e **não** se aplicam (o site tem identidade própria, SIT-09).

Acesso: público. Módulos: Serviços (SIT-08), Locais (local escolhido automaticamente pelo servidor, mostrado na confirmação com o rótulo da loja; nunca o link do local online).

## 3. Banco
Nenhuma alteração.

## 4. Contrato (páginas HTML do back-end)

Todas as páginas: `text/html; charset=utf-8`, `Cache-Control: no-store`, `<meta name="robots" content="noindex">` nas páginas de passo 2 em diante (a página inicial da loja pode ser indexada, como hoje), cabeçalhos de segurança já usados nas páginas existentes, sem recursos externos obrigatórios (CSS inline ou servido pelo próprio back-end; fontes do sistema). Parâmetros inválidos (uuid malformado, data fora do formato, serviço de outra loja/inativo, profissional que não faz o serviço) **nunca** dão 500: voltam ao passo anterior válido com uma mensagem curta, ou 404 quando não há passo para voltar.

### `GET /{slug}` — Passo 1: Serviço
- Cabeçalho da loja: tipo (Clínica/Barbearia/Escola), nome, frase do tipo (ex.: "Agende sua consulta online, em poucos passos."), endereço resumido e telefone (link `tel:`), logo se houver.
- Indicador de passos (1 Serviço · 2 Horário · 3 Seus dados · 4 Pronto).
- Lista de serviços ativos com profissionais: nome, descrição (se houver), duração, preço (se houver; formato `R$ 120,00`). Cada um é um link para o passo 2.
- Sem serviços disponíveis: mensagem "No momento não há horários para agendar online." com o telefone da loja.
- SIT-08: sem o módulo Serviços, `GET /{slug}` já mostra o passo 2 do "Atendimento".

### `GET /{slug}/agendar?servico=<uuid>&profissional=<uuid|vazio>&dia=<AAAA-MM-DD>` — Passo 2: Horário
- Título "<Serviço> · <duração> min", link "Voltar" para o passo 1.
- Filtro de profissional: `<form method="get">` com `<select>` ("Qualquer profissional" + os habilitados) e botão "Atualizar" (com JS, troca ao escolher e o botão some).
- Faixa de dias (31 dias a partir de hoje, no fuso da loja): cada dia é um link com dia da semana, data e "N horários" ou "Sem horários" (desabilitado). Rolagem horizontal no celular. O dia escolhido fica marcado; sem `dia`, marca o primeiro dia com horários.
- Horários do dia escolhido: botões/links com a hora (`HH:MM`); com "Qualquer profissional", o horário mostra também o nome do profissional que vai atender. Cada horário leva ao passo 3 carregando `servico`, `profissional` (o do horário), `inicio` e `local` (se houver).
- Nenhum horário em 31 dias: mensagem com o telefone da loja.

### `GET /{slug}/agendar/dados?servico=&profissional=&inicio=&local=` — Passo 3: Seus dados
- Resumo do que foi escolhido (serviço, dia por extenso, hora, profissional, local se houver) com link "Trocar horário".
- `<form method="post" action="/{slug}/agendar">` com: Nome*, Sobrenome*, WhatsApp com DDD* (`type="tel"`, `autocomplete="tel"`), E-mail (opcional), Observações (opcional, até 500), campos ocultos da escolha, campo-armadilha anti-robô escondido (honeypot) e botão "Pedir agendamento".
- Texto curto: "A <loja> vai confirmar seu horário pelo WhatsApp." (sem prometer prazo).
- Se o horário já não estiver livre ao abrir esta página: volta ao passo 2 do mesmo dia com aviso "Esse horário acabou de ser ocupado. Escolha outro."

### `POST /{slug}/agendar` — Envia o pedido
- `application/x-www-form-urlencoded`. Valida igual a `SolicitacaoEntrada` (mesmas mensagens em português).
- Honeypot preenchido → responde como sucesso aparente sem gravar nada (não ensina o robô).
- Proteção CSRF simples: aceitar só `Origin`/`Referer` do próprio host quando presentes (é formulário público sem sessão; o objetivo é impedir post vindo de outro site).
- Erro de validação → **200 com o formulário do passo 3 de novo**, valores preenchidos e a mensagem ao lado de cada campo (e um resumo no topo, com foco).
- Horário ocupado (409 / não oferecido) → redireciona (303) ao passo 2 do mesmo dia com o aviso.
- Limite de pedidos/pendentes (429 ou regra de pendentes) → página do passo 3 com a mensagem da regra, sem perder o que foi digitado.
- Sucesso → **303** para `GET /{slug}/agendar/pronto?c=<código>`.

### `GET /{slug}/agendar/pronto?c=<código>` — Passo 4: Pronto
- `<código>` é assinado (HMAC com o segredo da aplicação, expira em 24 h) e identifica o agendamento; inválido/expirado/de outra loja → 404 genérica.
- Mostra: "Pedido enviado!", serviço, dia, hora, profissional, local (nome, se houver), preço se houver, e "Seu horário fica reservado até a <loja> confirmar." Telefone da loja. **Não** mostra telefone/e-mail do cliente; pode mostrar só o primeiro nome.
- Link "Fazer outro agendamento" para `/{slug}`.

### Testes obrigatórios (backend)
- Fluxo completo sem JS (TestClient seguindo links e formulário): pedido criado `pendente`, origem `site`, auditoria com origem `site`.
- SIT-08 (módulo Serviços desligado) e módulo Locais ligado (local escolhido e mostrado sem link).
- Loja suspensa/cancelada/inexistente → 404 em todas as páginas do fluxo.
- Parâmetros inválidos/de outra loja nunca dão 500.
- Horário ocupado entre o passo 3 e o envio → 303 para o passo 2 com aviso.
- Erro de validação → 200 com campos preservados e mensagens.
- Honeypot e Origin de outro site → nada gravado.
- Código do passo 4 adulterado/expirado/de outra loja → 404.
- DIR-003: nenhuma página do fluxo contém `/painel`, `superadmin` nem `login`.
- Limites: as páginas do fluxo contam em `limite_site`; o envio conta em `limite_site_pedido`.
- Escapamento: nome de loja/serviço com `<script>` aparece escapado.

## 5. Contrato de tela (templates Jinja do back-end)
Não há tela React (frontend-ui e frontend-dev não participam; o site é do back-end, GER-01/SIT-09).

- Templates em `backend/app/templates/site/` herdando um `base` do site; a página 404 e a página de erro continuam funcionando.
- **Tokens por tipo de loja** (`clinica`, `barbearia`, `escola`) em variáveis CSS: cor do cabeçalho, cor de destaque, superfícies e texto, com versão escura (`prefers-color-scheme`). Clínica segue a referência (verde-petróleo); barbearia e escola com paletas próprias e contraste AA.
- Layout mobile first: em 360 px nada estoura na horizontal (exceto a faixa de dias, que rola), alvos de toque ≥ 44 px, texto ≥ 16 px nos campos (evita zoom no iOS).
- Acessibilidade: indicador de passos com `aria-current="step"`, dia escolhido com `aria-current`, rótulos em todos os campos, mensagens de erro ligadas por `aria-describedby`, foco visível, idioma `pt-BR`.
- JS opcional e pequeno (inline ou arquivo servido pelo back-end): troca de profissional sem clicar em "Atualizar", rolar a faixa até o dia marcado, desabilitar o botão de envio após o clique. Sem JS tudo funciona.
- Estados: carregando não se aplica (servidor); vazio (sem serviços / sem horários), erro de validação, horário ocupado, limite atingido, loja sem logo, nome longo, muitos serviços, um serviço só.

## 6. Critérios de aceite
- [ ] Em `localhost:5173/clinica-sorriso`, o cliente escolhe "Limpeza", vê os dias com a quantidade de horários, escolhe um horário, preenche os dados e vê "Pedido enviado!".
- [ ] O pedido aparece no painel da loja como pendente (Agendamentos/Agenda), com origem site, e a loja consegue aceitar.
- [ ] "Qualquer profissional" mostra quem vai atender em cada horário; escolher um profissional filtra os horários.
- [ ] Funciona com o JavaScript desligado.
- [ ] No celular (360 px) o fluxo é usável sem zoom e sem rolagem horizontal da página.
- [ ] Dois pedidos no mesmo horário: o segundo volta para a escolha de horário com aviso.
- [ ] Barbearia e escola têm cores próprias.
- [ ] Nenhuma página do site leva ao painel (DIR-003).
- [ ] Loja suspensa mostra 404; parâmetros estranhos na URL nunca mostram erro do servidor.

## 7. Fora do escopo
- Área do cliente (ver/cancelar os próprios agendamentos) — ponto em aberto "cliente precisa de acesso próprio".
- Notificações por WhatsApp/e-mail.
- Captcha (SIT-10 segue com limites + honeypot).
- Página própria por tipo com conteúdo diferente (por enquanto muda só a identidade visual e os textos curtos).

## 8. Decisões e perguntas
- O código do passo 4 expira em 24 h (HMAC com o segredo do JWT, preso à loja).
- **Divergências do backend aceitas pelo coordenador (2026-10-04):**
  - Passo 4 **não mostra nome nenhum** (o nome cadastrado de um telefone já existente vazaria, SIT-07). O texto acompanha a situação do agendamento (pendente / já confirmado / cancelado).
  - Parâmetro `aviso` (códigos fixos `ocupado`, `servico`, `horario`, sem eco do que o usuário digitou) para levar a mensagem depois de um redirecionamento.
  - Status: envio de outro site → 403; limite de pedidos por IP → 429 com o formulário; limite de pendentes por telefone e conflito de banco → 409 com o formulário.
  - Honeypot → 303 para uma confirmação genérica com código assinado por outra chave (sem gravar nada).
  - Envio repetido (mesmo telefone, profissional e início, pendente, últimos 10 min) leva à confirmação do pedido já gravado (duplo clique sem JS). Depois da rodada 1 (S2): só conta como repetição o formulário inteiro igual (nome, sobrenome, e-mail e observações) de um cliente criado pelo próprio pedido, e só depois do limite de pedidos; telefone de cliente já cadastrado volta à escolha de horário com "ocupado".
  - "Trocar horário" volta ao passo 2 com "qualquer profissional".
  - Cabeçalho sem o e-mail da loja (a página provisória mostrava).
  - Sem o módulo Serviços, o indicador tem três passos.
  - Passo 3 e envio não limitam `inicio` à janela de 31 dias: vale a mesma regra da API (o horário precisa estar oferecido).
- Provisório: textos por tipo — Clínica "Agende sua consulta online, em poucos passos."; Barbearia "Marque seu horário online, em poucos passos."; Escola "Agende sua aula online, em poucos passos."

## 9. Histórico de revisão
- **2026-10-04 · rodada 1 · APROVADO**, sem achados bloqueantes ou importantes (768 testes; fuzz de ~1.350 requisições sem 5xx; CSRF, corrida, fusos, escapamento e open redirect conferidos; API `/api/site` idêntica após a extração). Sugestões aplicadas pelo backend a pedido do coordenador (776 testes):
  - S1: envio simultâneo no limite de pendentes por telefone leva à confirmação do pedido gravado.
  - S2: repetição exige formulário inteiro igual, cliente criado pelo próprio pedido, e vem depois do limite de pedidos (não revela pedido alheio).
  - S3: campo-armadilha renomeado (`zx_conferencia`), `display:none`, `autocomplete="off"` (autopreenchimento não descarta pedido real).
  - Menor: botão de envio reabilitado ao voltar pelo histórico (`pageshow`).
  - S4 (coordenador): texto da SIT-12 corrigido (confirmação sem nome do cliente).
- **Rodada 2 (conferência das correções): pendente** — interrompida pelo fim da sessão em 2026-10-04.
