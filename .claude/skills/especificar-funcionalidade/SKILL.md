---
name: especificar-funcionalidade
description: Modelo e regras da especificação de funcionalidade (docs/funcionalidades/<slug>.md) com o contrato da API e o contrato de tela, que permitem backend e frontend-ui trabalharem em paralelo e o frontend-dev integrar sem adivinhar. Use ao escrever, ler ou atualizar uma especificação.
user-invocable: false
---

# Especificação de funcionalidade

Toda funcionalidade nova nasce de um arquivo `docs/funcionalidades/<slug>.md`, escrito pelo **coordenador** antes de qualquer código. É o **contrato** entre os agentes:

- o **backend** implementa exatamente o **contrato da API**;
- o **frontend-ui** monta as telas consumindo exatamente o **contrato de tela** (com dados provisórios no formato combinado);
- o **frontend-dev** liga um ao outro: implementa os hooks do contrato de tela chamando as rotas do contrato da API;
- o **revisor** confere o resultado contra os **critérios de aceite**.

Se um agente descobre que o contrato está errado ou incompleto, ele **não muda o contrato por conta própria**: implementa o que dá, e relata a divergência no relatório final para o coordenador decidir. Divergência silenciosa entre back e front é o defeito mais caro deste fluxo.

## Regras para escrever

- Regras citadas pelo código do catálogo (`AGE-07`, skill `regras-do-sistema`). Regra nova recebe código novo e entra no catálogo e no `estrutura.md` no mesmo trabalho.
- Campos da API em `snake_case` português (como o banco). Campos de tela em `camelCase` (como o JS existente). A conversão é só na camada `frontend/src/data/api/` (frontend-dev).
- Tipos explícitos em todo campo: `uuid`, `string(max)`, `int`, `decimal(10,2)` (número no JSON), `bool`, `date` (`AAAA-MM-DD`), `datetime` (ISO 8601 com fuso da loja), `time` (`HH:MM`), enum com os valores, lista, objeto. Diga sempre se o campo **pode ser `null`** ou **pode faltar**.
- Para cada rota, liste **todos** os erros possíveis com status e mensagem em português. O front precisa saber o que mostrar.
- Ponto em aberto (ver `regras-do-sistema/referencias/em-aberto.md`): não decida; registre a decisão provisória e a pergunta ao usuário.
- Fatias pequenas. Uma especificação que precisa de mais de ~8 rotas ou ~3 telas provavelmente são duas funcionalidades.

## Modelo

Copie e preencha. Seções que não se aplicam ficam com "Não se aplica" (não apague: o revisor confere que foram pensadas).

````markdown
# <Nome da funcionalidade>

- **Slug:** <slug> · **Branch:** feat/<slug> · **Status:** especificada | em desenvolvimento | em revisão (rodada N) | aprovada
- **Área:** painel da loja | SUPERADMIN | site do consumidor
- **Pedido original:** <texto do usuário, resumido>

## 1. Objetivo
Quem usa, o que precisa concluir e com que frequência (3 linhas).

## 2. Regras de negócio
| Código | Regra | Onde é garantida (banco / serviço / rota / tela) |
|---|---|---|
| AGE-07 | Sem conflito de horário do profissional | banco (EXCLUDE) + 409 na rota |
| XXX-NN (nova) | ... | ... |

**Diretrizes aplicáveis** (ordens permanentes do usuário, `.claude/diretrizes/INDICE.md`): `DIR-001` (painel lateral), ... — ou "Nenhuma no escopo". Cada agente lê o arquivo completo delas.

Acesso: recurso e nível exigido por ação (ex.: listar = leitura em `clientes`; salvar = escrita). Módulos que afetam o comportamento e o que muda com cada um desligado.

## 3. Banco
Tabelas/colunas novas ou alteradas (com tipos, NULL, índices, CHECK, triggers). "Nenhuma alteração" se for o caso. Toda tabela nova segue as regras transversais (GER-04, GER-08 a GER-12).

## 4. Contrato da API
Para cada rota:

### `POST /api/loja/<recurso>`
- **Permissão:** `exigir("<recurso>", "escrita")`
- **Entrada:**
  | Campo | Tipo | Obrigatório | Null | Regra |
  |---|---|---|---|---|
- **Saída 201:**
  ```json
  { "id": "uuid", "...": "...", "criado_em": "datetime", "atualizado_em": "datetime", "atualizado_por": "uuid|null", "atualizado_por_nome": "string|null" }
  ```
  Campos que podem vir `null`: <lista>.
- **Erros:**
  | Status | Quando | `detail` |
  |---|---|---|
  | 401 | sem token | Faça login para continuar. |
  | 403 | sem escrita | Você só tem permissão de leitura aqui. |
  | 404 | id de outra loja ou inexistente | <Recurso> não encontrado. |
  | 409 | ... | ... |
  | 422 | campo inválido | Verifique os dados informados. (+ `erros[]`) |
- Listas: paginação (`pagina`, `por_pagina`, `{itens, total, pagina, por_pagina}`), filtros e ordenação padrão.

## 5. Contrato de tela
### Telas e componentes
Rota no front, tela nova ou alterada, componentes base que serão usados (`Pagina`, `CadastroTabela`, `PainelFormulario`...), esboço ASCII.

### Hooks de dados (fronteira entre frontend-ui e frontend-dev)
| Hook (em `frontend/src/data/`) | Retorna | Ações |
|---|---|---|
| `useClientes(filtros)` | `{ itens: Cliente[], total, carregando, erro }` | `salvar(dados) → Promise<Cliente>`, `excluir(id) → Promise<void>` |

Formato dos objetos na tela (camelCase), com o mapeamento para a API:
| Tela | API | Tipo na tela | Pode ser null |
|---|---|---|---|
| `nomeCompleto` | `nome` + `sobrenome` | string | não |

Erros das ações: o hook rejeita com `{ status, mensagem, campos: { [campoTela]: mensagem } }` (padrão da skill `integracao-api`).

### Estados obrigatórios
Carregando, vazio, erro, sem permissão (leitura), módulo desligado, dado longo, um item, muitos itens — o que cada um mostra nesta tela.

## 6. Critérios de aceite
Lista verificável, em linguagem de usuário, cobrindo caminho feliz, regras, permissões, isolamento entre lojas e casos-limite. Ex.:
- [ ] Recepção cria um agendamento num horário livre e ele aparece na agenda da semana.
- [ ] Profissional (só Minha agenda) não vê agendamentos de outros, nem pela API (`GET /agendamentos/{id}` de outro = 404).
- [ ] Loja A não lê nem altera dados da loja B (teste automatizado).
- [ ] Horário ocupado devolve 409 e a tela mostra a mensagem ao lado do campo de horário.

## 7. Fora do escopo
O que fica para depois e por quê.

## 8. Decisões e perguntas
Decisões provisórias tomadas e perguntas pendentes ao usuário.

## 9. Histórico de revisão
(o coordenador acrescenta uma entrada por rodada: data, veredito, achados e quem corrigiu)
````
