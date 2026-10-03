# Acessar loja pelo SUPERADMIN

- **Slug:** acessar-loja · **Branch:** feat/acessar-loja (a partir de feat/roteamento-url) · **Status:** aprovada
- **Área:** SUPERADMIN + painel da loja
- **Pedido original:** "No super admin tem que ter um botão na página de cadastro de loja, 'Acessar loja', que gera um token e já abre a loja para acessar como admin daquela loja."

## 1. Objetivo
O superadmin, no detalhe de uma loja, clica em **Acessar loja** e uma nova aba abre o painel daquela loja (`/{slug}/painel`) já logado como o Administrador da loja, sem digitar senha. Uso de suporte, algumas vezes por dia.

## 2. Regras de negócio
| Código | Regra | Onde é garantida |
|---|---|---|
| PLA-17 (nova) | **Acessar loja:** o superadmin gera uma sessão do painel da loja como o **Administrador da loja** = funcionário **ativo** cujo perfil é o Administrador padrão (`perfis.padrao = true` e `acesso_total = true`), o mais antigo (`criado_em`, depois `id`). Tudo que for feito na sessão fica registrado **como esse Administrador** (decisão do usuário, 2026-10-03), igual a um login dele | serviço + rota superadmin |
| PLA-18 (nova) | A sessão de "Acessar loja" dura **1 hora** (fixo, não usa `JWT_EXPIRA_MINUTOS`) e não é renovada; venceu, o painel cai no login normal | token |
| PLA-19 (nova) | "Acessar loja" funciona com a loja **ativa, suspensa ou cancelada** (o suporte confere/arruma antes de reativar). Os funcionários da loja continuam bloqueados pela GER-25. Loja **excluída**: 404 | rota + `obter_contexto_loja` |
| PLA-14 | O ato de gerar o acesso entra na auditoria **da loja** como ação do **superadmin** (`registrar_acao`, origem `superadmin`), com o detalhe `{"acao": "acessar_loja", "como_funcionario": "<nome>", "nome": "<nome>"}` (`nome` só para o rótulo; `campos_alterados` = `acao`, `como_funcionario`). Sem token no detalhe | rota |
| GER-05 | `loja_id` continua vindo só do token | token |
| ACE-20 | Sempre há um Administrador ativo; se mesmo assim não houver, 409 | serviço |
| DIR-003 | O site do consumidor não ganha nenhum caminho para o painel | — |

**Diretrizes aplicáveis:** `DIR-001` (nada de modal: confirmação, se houver, segue o padrão do projeto — ver 5), `DIR-002` (botão e aviso nos tokens), `DIR-003` (nenhuma mudança no site).

Acesso: rota exige token de superadmin ativo (`ContextoSuperadminDep`). No painel, a sessão tem o acesso do perfil do Administrador (total, respeitando módulos desligados — GER-23).

## 3. Banco
Nenhuma tabela ou coluna nova. Não atualiza `ultimo_login_em` do Administrador (não foi ele quem entrou).

## 4. Contrato da API

### `POST /api/superadmin/lojas/{loja_id}/acesso`
- **Permissão:** superadmin logado.
- **Entrada:** nenhuma (corpo vazio `{}` aceito).
- **Saída 201:**
  ```json
  { "token": "string", "expira_em": "datetime (fuso da loja)", "slug": "clinica-sorriso", "funcionario_nome": "Ana Souza" }
  ```
  Nenhum campo `null`.
- **Erros:**
  | Status | Quando | `detail` |
  |---|---|---|
  | 401 | sem token / token inválido / superadmin inativo | Faça login para continuar. (mensagens atuais) |
  | 404 | loja inexistente ou excluída | Loja não encontrada. |
  | 409 | loja sem Administrador ativo | Esta loja não tem um Administrador ativo para acessar. |
  | 422 | `loja_id` não é uuid | Verifique os dados informados. |
- **Token:** JWT do tipo `funcionario` (mesmo formato do login: `sub` = id do Administrador, `loja_id`), mais a claim `suporte: true`, `exp` = agora + 60 min. Funciona em todas as rotas `/api/loja/...` como um token normal.
- **`obter_contexto_loja`:** com `suporte: true`, **não** chama `verificar_status_loja` (PLA-19); todo o resto igual (funcionário precisa existir, ser da loja e estar ativo; perfil; acesso). Contexto de auditoria igual ao de um login normal do funcionário (`origem = 'painel'`, `funcionario_id` = Administrador), conforme a decisão do usuário.
- **`GET /api/loja/eu`:** ganha `sessao: { "suporte": bool, "expira_em": "datetime|null" }` (`expira_em` = `exp` do token no fuso da loja; `suporte = false` em login normal). Campo novo, não quebra o front atual.

### Testes obrigatórios (backend)
Gera token (201) e ele acessa `/api/loja/eu` com `sessao.suporte = true`; escolhe o Administrador mais antigo ativo (ignora inativo e perfis não-Administrador); loja suspensa e cancelada: token funciona; login normal na loja suspensa continua 403; token normal de funcionário em loja suspensa continua 403; loja excluída 404; sem Administrador ativo 409; token expira em 60 min; auditoria da loja registra a ação do superadmin sem token; `ultimo_login_em` não muda; token de funcionário não acessa a rota (401); claim `suporte` forjada sem assinatura válida não passa (JWT inválido = 401).

## 5. Contrato de tela

### SUPERADMIN · detalhe da loja (`superadmin/pages/LojaDetalhe.jsx`)
- Botão **"Acessar loja"** (primário ou secundário, conforme o padrão dos cabeçalhos do projeto) ao lado dos links "Abrir site / Abrir painel" já existentes. Ícone de entrar (ex.: `LoginOutlined`).
- Clique: abre a aba **na hora do clique** (`window.open('about:blank', '_blank')`, para não ser barrado pelo bloqueador de pop-up), chama `gerarAcessoLoja(lojaId)`, e grava o token no `sessionStorage` **da aba nova** (mesma origem: `aba.sessionStorage.setItem('agenda.entrega.suporte', token)`), zera `aba.opener` e manda a aba para `/{slug}/painel/suporte` (`location.replace`, **sem token na URL**). Erro: fecha a aba aberta e mostra a mensagem com o tratamento padrão (`useTratarErro`). Carregando: botão com `loading`.
- Sem confirmação extra (é uma ação de leitura/entrada; fica auditada).
- Texto de ajuda curto abaixo/tooltip: "Abre o painel em outra aba como o Administrador da loja, por 1 hora."

### Painel · rota nova `/:slug/painel/suporte`
- Fora do `AppLayout` e do `ExigirSessao` (como o login). Lê a chave de entrega `agenda.entrega.suporte` do `sessionStorage` e **apaga na hora**; grava o token como sessão daquela loja (mesma chave `agenda.sessao.loja.<slug>`), recarrega a sessão e navega para o início do painel (`replace`).
- Sem chave de entrega, token recusado ou token que não é de suporte (`eu.sessao.suporte !== true`): vai para o login da loja (mensagem "O acesso de suporte não é válido ou venceu. Gere outro no SUPERADMIN." no login).
- Enquanto troca: `CarregandoPagina`.

### Painel · aviso de sessão de suporte
- Quando `sessao.suporte = true`: faixa discreta no topo do painel (dentro do `AppLayout`/`Casca`), nos tokens: "Acesso de suporte como **{nome do funcionário}** · termina às **HH:MM**". Sem botão de fechar. Quando vence, o fluxo normal de 401 leva ao login.

### Hooks / dados
| Onde | Assinatura | Dono |
|---|---|---|
| `frontend/src/data/api/plataforma.js` | `gerarAcessoLoja(lojaId) → Promise<{ token, expiraEm, slug, funcionarioNome }>` | frontend-dev |
| sessão da loja (`data/sessao/`) | `entrarComToken(token) → Promise<void>` (grava o token da loja da sessão e carrega `/eu`); `sessao.suporte: bool`, `sessao.expiraEm: string|null` (de `eu.sessao`) | frontend-dev |
| provisório para o frontend-ui | pode simular `gerarAcessoLoja` e `sessao.suporte/expiraEm` com mock no formato acima | frontend-ui |

| Tela | API | Tipo | Null |
|---|---|---|---|
| `expiraEm` | `expira_em` | string ISO | não (no acesso); sim em `eu.sessao` de login normal |
| `funcionarioNome` | `funcionario_nome` | string | não |
| `suporte` | `eu.sessao.suporte` | bool | não (padrão `false`) |

### Estados obrigatórios
Botão carregando; erro 404/409 (mensagem, aba fechada); bloqueador de pop-up que impede até o `about:blank` (mostra mensagem "Permita pop-ups deste site para acessar a loja."); rota `/suporte` sem token / token inválido / vencido; faixa com nome longo (quebra sem estourar em 390 px).

## 6. Critérios de aceite
- [ ] No detalhe da loja, "Acessar loja" abre outra aba direto no início de `/{slug}/painel`, logado como o Administrador, sem pedir senha.
- [ ] A URL final não contém o token (nem no histórico da aba).
- [ ] O painel mostra a faixa "Acesso de suporte como … · termina às …".
- [ ] Alterar um cliente nessa sessão aparece no histórico como feito pelo Administrador; a auditoria da loja tem a linha do superadmin "acessar_loja".
- [ ] Loja suspensa: "Acessar loja" funciona; o login normal dos funcionários dela continua bloqueado.
- [ ] Depois de 1 hora, a próxima ação leva ao login.
- [ ] A sessão aberta pelo suporte numa aba não derruba a sessão de outra loja em outra aba.
- [ ] Testes do back-end da seção 4 passando; lint e build do front passando.

## 7. Fora do escopo
- Encerrar a sessão de suporte remotamente (revogação de token) — JWT sem lista de revogação hoje.
- Escolher qual funcionário personificar.

## 8. Decisões e perguntas
Decisões do usuário (2026-10-03): fica registrado como o Administrador; sessão de 1 hora; loja suspensa/cancelada pode ser acessada.
Decisões do coordenador: entrega do token à aba nova pelo `sessionStorage` dela (chave `agenda.entrega.suporte`, gravada por quem abriu a aba `about:blank`, que é da mesma origem), **nunca na URL** — a primeira versão usava `#token=` e a revisão provou que a URL ia para o histórico global do navegador (rodada 1, A1); sem tabela nova; o ato de gerar o acesso continua auditado como do superadmin (PLA-14), para não perder o rastro de quem abriu a sessão.

Divergências do frontend-ui aceitas:
- Texto da faixa: "Acesso de suporte como **X**. Termina às **15h30**." (sem "·", UI-31; hora com `horaCurta`).
- **Segurança:** a aba aberta por `window.open` copia o `sessionStorage` da aba do SUPERADMIN. `entrarComToken` apaga, nessa aba, toda chave de sessão que não seja a da loja da URL (inclui `agenda.sessao.superadmin`).
- Erro de rede na rota `/suporte`: tela com "Tentar de novo" (não manda para o login dizendo que venceu).

- `entrarComToken` recusa token que não seja de suporte (`eu.sessao.suporte !== true`): evita login CSRF por link.
- Auditoria legível: o detalhe da ação inclui `nome` do Administrador (rótulo da linha) e o histórico mostra os campos como "Ação: Acessar loja" e "Como o funcionário".

## 9. Histórico de revisão
- **2026-10-03 · rodada 1 · REPROVADO.** A1 (bloqueante, frontend-dev + coordenador): token em `#token=` ficava no histórico global do navegador → entrega trocada para o `sessionStorage` da aba nova. Sugestões aceitas: recusar token que não seja de suporte em `entrarComToken`; rótulo/campos legíveis na auditoria (backend + frontend-dev). Não aplicada: `state.motivo` sobrevive ao F5 no login.
- **2026-10-03 · rodada 2 · APROVADO.** A1 resolvido (History do Chromium sem token em 59 navegações), recusa de token comum confere com as duas ordens da corrida, auditoria legível. pytest 701 ok, ruff ok, lint/build ok. Sugestões não aplicadas: ação de suporte aparece como "— → Acessar loja" no histórico; `state.motivo` sobrevive ao F5 no login.
