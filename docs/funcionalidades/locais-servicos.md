# Vincular serviços pela tela de Locais

- **Slug:** locais-servicos · **Branch:** feat/locais-servicos · **Status:** aprovada
- **Área:** painel da loja
- **Pedido original:** "Na tela de Locais eu não consigo associar um local a um serviço em específico. Preciso conseguir." Hoje a coluna "Serviços vinculados" é só leitura; o vínculo só é editado na tela de Serviços.

## 1. Objetivo
Quem cuida dos locais (normalmente o Administrador) abre um local e escolhe quais serviços acontecem nele, sem precisar abrir serviço por serviço. Uso esporádico: ao cadastrar um local novo ou reorganizar a loja.

## 2. Regras de negócio
| Código | Regra | Onde é garantida |
|---|---|---|
| SER-03 | Vínculos serviço↔local (`servico_locais`) são os mesmos editados na tela de Serviços; agora também na de Locais (LOC-06) | serviço/rota |
| SER-04 / AGE-12 | Serviço **sem nenhum** local vinculado aceita qualquer local ativo. Serviço com vínculos só usa os locais vinculados | serviço de agendamento (sem mudança) |
| LOC-06 (nova) | Na tela de Locais, quem tem **escrita em Locais** escolhe os serviços vinculados ao local (só com o módulo **Serviços** ativo). O vínculo **restringe o serviço, não o local**: um serviço sem nenhum vínculo continua podendo usar este local. Vincular um serviço que hoje aceita qualquer local faz ele passar a usar só os locais marcados; tirar o último local de um serviço faz ele voltar a aceitar qualquer local. Agendamentos já marcados não mudam (AGE-12 é conferida ao criar/editar) | rota (`PUT /locais/{id}`) + aviso na tela |
| LOC-02 | Local não é excluído, só inativado. Local inativo também pode ter os vínculos editados | rota |
| GER (isolamento) | `servico_ids` só aceita serviços da própria loja (não excluídos) | rota (422) + FK composta |

**Decisão do usuário (2026-10-04):** mantida a regra atual (vínculo restringe só o serviço). A alternativa "local exclusivo" (local com lista própria recusa serviços fora dela) foi recusada.

**Diretrizes aplicáveis:** `DIR-001` (painel lateral: o campo entra no painel lateral de edição do local que já existe), `DIR-002` (identidade visual, só tokens).

**Acesso:**
- Listar/ver locais: leitura em `locais` (sem mudança).
- Salvar vínculos: escrita em `locais`. Não exige acesso a Serviços (simétrico a `GET /servicos/opcoes`, que deixa quem edita serviços escolher locais sem acesso a Locais).
- Opções de serviços para o campo: escrita em `locais`.
- **Módulo Serviços desligado:** o campo não aparece, `servico_ids` é ignorado na API e as opções vêm `null`. Módulo Locais desligado: a tela inteira já é bloqueada (sem mudança).

## 3. Banco
Nenhuma alteração. Usa `servico_locais` (2.20) com os triggers existentes (exclusão lógica, restauração ao religar e auditoria automática).

## 4. Contrato da API

### `PUT /api/loja/locais/{local_id}` e `POST /api/loja/locais` (alterados)
- **Permissão:** `exigir("locais", "escrita")` (sem mudança)
- **Entrada:** os campos atuais (`nome`, `tipo`, `link_padrao`, `descricao`, `ativo`) mais:
  | Campo | Tipo | Obrigatório | Null | Regra |
  |---|---|---|---|---|
  | `servico_ids` | lista de `uuid` | não | sim | **Ausente ou `null` = não mexe nos vínculos** (compatível com quem não envia). Lista (pode ser vazia) = o local fica vinculado exatamente a esses serviços (`sincronizar_vinculos` com fixo `local_id`). Ids repetidos são deduplicados. Ignorado com o módulo Serviços desligado. Aceita serviço ativo ou inativo, desde que da loja e não excluído |
- **Saída 200/201:** `LocalSaida` atual. O campo `servicos` passa a trazer também `ativo`:
  ```json
  { "id": "uuid", "nome": "Consultório 1", "tipo": "presencial", "link_padrao": null, "descricao": "...", "ativo": true,
    "servicos": [ { "id": "uuid", "nome": "Limpeza", "ativo": true } ],
    "proximos_agendamentos": 3,
    "criado_em": "datetime", "atualizado_em": "datetime", "atualizado_por": "uuid|null", "atualizado_por_nome": "string|null" }
  ```
  `servicos` = vínculos não excluídos de serviços não excluídos, ordenados por nome; lista vazia com o módulo Serviços desligado. Campos que podem vir `null`: `link_padrao`, `descricao`, `atualizado_por`, `atualizado_por_nome`.
  > Observação: o `atualizado_em`/`atualizado_por` do local só muda se um campo do próprio local mudar; mudança só de vínculo fica na auditoria (`servico_locais`).
- **Erros:**
  | Status | Quando | `detail` |
  |---|---|---|
  | 401 | sem token | Faça login para continuar. |
  | 403 | sem escrita em Locais / módulo Locais desligado | mensagens atuais de `exigir()` |
  | 404 | local de outra loja ou inexistente | Local não encontrado. |
  | 409 | nome repetido | mensagem atual (`locais_nome_uk`) |
  | 422 | algum `servico_ids` de outra loja, inexistente ou excluído | `{"detail": "Serviço não encontrado."}` **sem `erros[]`** (padrão do projeto para 422 de regra); o front aponta para o campo `servicoIds` com `apontarCampo` (`/serviço/i`), como em `api/servicos.js` |
  | 422 | mais de 200 ids | Itens demais (máximo de 200). (campo `servico_ids`) |
  | 422 | uuid malformado / outros campos | Verifique os dados informados. (+ `erros[]`) |

### `GET /api/loja/locais/opcoes` (nova; declarar antes de `/{local_id}`)
- **Permissão:** `exigir("locais", "escrita")`
- **Saída 200:**
  ```json
  { "servicos": [ { "id": "uuid", "nome": "Limpeza", "ativo": true, "locais_vinculados": 1 } ] }
  ```
  - `servicos`: todos os serviços **não excluídos** da loja (ativos e inativos), ordenados por nome. `null` = módulo Serviços desligado.
  - `locais_vinculados` (`int`, ≥ 0): quantos locais **não excluídos** estão vinculados ao serviço hoje (inclusive o local que está sendo editado, se for o caso). `0` = o serviço aceita qualquer local (SER-04). Serve para o aviso da tela.
- **Erros:** 401, 403 (sem escrita em Locais / módulo desligado).

### Testes obrigatórios (backend)
- Vincular, desvincular e religar (restaura a linha; auditoria registra `restaurar`).
- `servico_ids` ausente/`null` não altera vínculos; `[]` remove todos.
- Serviço da loja B em `servico_ids` → 422 e nada gravado; local da loja B → 404.
- Leitura em Locais não grava (403); `opcoes` com só leitura → 403.
- Módulo Serviços desligado: `servico_ids` ignorado e `opcoes.servicos` = `null`.
- Depois de vincular pelo local, `GET /servicos/{id}` mostra o local, e as regras de agendamento (AGE-12) passam a valer: serviço que estava sem vínculo agora recusa outro local; serviço que perdeu o último vínculo volta a aceitar qualquer local.
- `locais_vinculados` correto (conta só vínculos e locais não excluídos).

## 5. Contrato de tela

### Telas e componentes
Tela `Locais` (`frontend/src/pages/Locais.jsx`, rota `/<slug>/painel/locais`), painel lateral de edição/criação que já existe (`CadastroTabela` → `PainelFormulario`). Novo campo depois de "Descrição"/"Link fixo" e antes de "Ativo", só quando `moduloAtivo('servicos')`:

```
 Serviços que acontecem aqui
 [ Limpeza ×  Clareamento × ............ ▾ ]   (Select múltiplo, busca por nome; inativos com "(inativo)")
 Serviço sem nenhum consultório marcado pode usar qualquer um, inclusive este.

 ⚠ Clareamento hoje aceita qualquer consultório. Ao salvar, passa a usar só os consultórios marcados para ele.
 ⚠ Limpeza só usa este consultório. Ao tirar, volta a aceitar qualquer consultório.
```
- Os textos usam o rótulo da loja (`rotulosLocal(loja)`: "consultório", "sala"...).
- Aviso "passa a usar só os marcados": serviço **adicionado** no formulário cujo `locaisVinculados === 0`.
- Aviso "volta a aceitar qualquer": serviço **removido** no formulário que estava vinculado a este local e cujo `locaisVinculados === 1`.
- Avisos são informativos (tom de alerta suave, tokens), não bloqueiam salvar.
- Somente leitura: o campo aparece desabilitado com os serviços atuais (como os outros campos).
- Coluna "Serviços vinculados" da tabela: sem mudança de formato; serviço inativo aparece com "(inativo)".

### Hooks de dados (fronteira entre frontend-ui e frontend-dev)
| Hook (em `frontend/src/data/`) | Retorna | Ações |
|---|---|---|
| `useLocais()` (existente) | igual hoje; cada item ganha `servicoIds: uuid[]` e `servicos: {id, nome, ativo}[]` | `salvar(valores, registro)` passa a enviar `servicoIds` (quando presente em `valores`) |
| `useOpcoesLocal({ ativo })` (novo, em `useLocais.js`) | `{ servicos: OpcaoServico[] \| null, carregando, erro, recarregar }` — só busca quando `ativo` (painel aberto, módulo Serviços ligado e escrita em Locais) | — |

Formato na tela (camelCase) ↔ API:
| Tela | API | Tipo na tela | Pode ser null |
|---|---|---|---|
| `local.servicoIds` | `servicos[].id` | `string[]` | não (vazio) |
| `local.servicos[].ativo` | `servicos[].ativo` | bool | não (padrão `true`) |
| valores do form `servicoIds` | `servico_ids` | `string[]` | ausente = não envia o campo |
| `opcao.id` / `opcao.nome` / `opcao.ativo` | idem | string / string / bool | não |
| `opcao.locaisVinculados` | `locais_vinculados` | int | não (padrão 0) |
| `opcoes.servicos` | `servicos` | lista | **sim** (`null` = módulo Serviços desligado → esconde o campo) |

Erros das ações: o hook rejeita com `{ status, mensagem, campos: { [campoTela]: mensagem } }` (skill `integracao-api`); 422 de `servico_ids` vai para o campo `servicoIds`.

### Estados obrigatórios
- **Carregando opções:** Select com `loading` e desabilitado; o resto do formulário funciona.
- **Erro nas opções:** mensagem curta abaixo do campo com "Tentar de novo"; o formulário ainda salva os outros campos **sem enviar `servicoIds`** (não apaga vínculos por falta de opções).
- **Nenhum serviço cadastrado:** Select vazio com "Nenhum serviço cadastrado".
- **Sem permissão (leitura):** campo desabilitado mostrando os vínculos atuais; `useOpcoesLocal` não busca (403).
- **Módulo Serviços desligado:** campo e coluna escondidos.
- **Muitos serviços / nomes longos:** Select com busca e tags que quebram linha sem estourar a largura do painel.
- **Serviço vinculado que não está nas opções** (ex.: excluído no meio do caminho): mostra o nome vindo do local e não quebra.

## 6. Critérios de aceite
- [ ] Administrador abre "Consultório 1", marca "Clareamento", salva, e a coluna "Serviços vinculados" mostra "Clareamento, Limpeza".
- [ ] Ao abrir "Clareamento" na tela de Serviços, o "Consultório 1" aparece nos locais dele.
- [ ] Marcar um serviço que hoje aceita qualquer local mostra o aviso antes de salvar; depois de salvar, um agendamento desse serviço em outro local é recusado (AGE-12).
- [ ] Tirar o único local de um serviço mostra o aviso; depois de salvar, o serviço aceita qualquer local.
- [ ] Serviço sem vínculo continua podendo ser agendado no "Consultório 1".
- [ ] Recepção/perfil só com leitura em Locais vê os serviços mas não altera (campo desabilitado; API 403).
- [ ] Com o módulo Serviços desligado, o campo não aparece e salvar o local não mexe nos vínculos.
- [ ] Erro ao carregar as opções não apaga os vínculos ao salvar o local.
- [ ] Loja A não vincula serviço da loja B (422) nem edita local da loja B (404) — teste automatizado.
- [ ] Desvincular e vincular de novo restaura a linha e aparece na auditoria.
- [ ] Nada quebra com lista de serviços vazia, `null` ou nomes longos.

## 7. Fora do escopo
- "Local exclusivo" (local que recusa serviços fora da lista) — recusado pelo usuário em 2026-10-04.
- Editar profissionais/materiais pela tela de Locais.
- Mudanças no site do consumidor (a disponibilidade já usa AGE-12; nada muda).

## 8. Decisões e perguntas
- Permissão para editar o vínculo pela tela de Locais: só escrita em Locais (simetria com `GET /servicos/opcoes`). Provisória; trocar para "Locais + Serviços" é uma linha na rota.
- Serviços inativos aparecem nas opções (marcados "(inativo)") para que salvar o local não apague vínculos que já existem com eles.

## 9. Histórico de revisão
- **2026-10-04 · rodada 1 · APROVADO.** Sem achados bloqueantes ou importantes. backend: ruff ok, 712 testes; frontend: lint (0 erros) e build ok; tela conferida no navegador. Sugestões não aplicadas:
  - S1 (backend): `PUT /servicos/{id}` não trava; salvar o mesmo par serviço/local pelas duas telas no mesmo instante pode dar 409 "Já existe um cadastro com esses dados." (dados corretos; tentar de novo funciona). Correção futura: `ON CONFLICT` em `sincronizar_vinculos` ou mensagem "tente de novo" para a PK de `servico_locais`.
  - S2 (frontend-ui): `comServicoIds` e o embrulho de `carregarRegistro` em `Locais.jsx` ficaram redundantes.
  - S3 (backend/frontend-dev): o 422 "Serviço não encontrado." não diz qual serviço (só acontece se um serviço for excluído com o painel aberto).
