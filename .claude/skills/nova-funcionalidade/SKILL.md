---
name: nova-funcionalidade
description: Fluxo completo para implementar uma funcionalidade nova neste projeto - o coordenador especifica, chama backend e frontend-ui em paralelo, depois o frontend-dev integra e o revisor aprova ou devolve para correção, em ciclo até aprovar. Use quando o usuário pedir uma funcionalidade, tela, rota ou mudança que envolva back-end e/ou front-end.
argument-hint: <descrição da funcionalidade>
---

# Fluxo de nova funcionalidade

Você é o **coordenador** (agente `coordenador`; se não estiver rodando como ele, siga as instruções de `.claude/agents/coordenador.md` como se fossem suas). Este fluxo **precisa rodar na conversa principal**: subagentes não conseguem chamar outros subagentes. Se você é um subagente e não tem a ferramenta Agent, faça só a etapa 1 (especificação) e devolva o plano das etapas seguintes para a conversa principal executar.

Pedido: $ARGUMENTS

```
           ┌──────────────┐
           │ 1 Coordenador│  especificação + contrato (docs/funcionalidades/<slug>.md)
           └──────┬───────┘
          ┌───────┴────────┐        em paralelo (mesma mensagem, duas chamadas Agent)
   ┌──────▼─────┐   ┌──────▼──────┐
   │ 2 backend  │   │2 frontend-ui│
   └──────┬─────┘   └──────┬──────┘
          └───────┬────────┘        espera os dois
           ┌──────▼───────┐
           │3 frontend-dev│  liga as telas à API
           └──────┬───────┘
           ┌──────▼───────┐   REPROVADO: achados vão para o dono (backend / frontend-ui / frontend-dev)
           │  4 revisor   │──────────────► 5 correção ──► volta para 4 (máx. 3 rodadas)
           └──────┬───────┘
                  │ APROVADO
           ┌──────▼───────┐
           │ 6 Entrega    │  commit na branch, relatório ao usuário
           └──────────────┘
```

## 0. Preparação

1. `git status`: árvore limpa? Se houver mudanças que não são suas, pare e pergunte.
2. Crie a branch a partir da `main` atualizada: `git checkout -b feat/<slug>`. **Só o coordenador mexe em branch e commit.** Os outros agentes trabalham na branch atual e não fazem `checkout`, `commit`, `stash`, `reset` nem `push`.
3. Crie a lista de tarefas (TodoWrite, se disponível) com as etapas abaixo.

## 1. Especificar (coordenador)

1. Confira as **diretrizes permanentes** (`.claude/diretrizes/INDICE.md`) que tocam a funcionalidade e leia o arquivo de cada uma. Se o próprio pedido contém uma ordem permanente ("em todas as telas…", "padronize…"), registre-a primeiro (skill `diretrizes`) e inclua a aplicação no código existente no escopo da especificação.
2. Leia as regras da área (skill `regras-do-sistema` e a referência da área), o `estrutura.md` nas seções tocadas e o código existente relacionado (rotas, serviços, telas, hooks). Delegue buscas amplas ao agente `Explore` para não encher o contexto.
3. Escreva `docs/funcionalidades/<slug>.md` com o modelo da skill `especificar-funcionalidade` e acrescente a linha dela no índice `docs/funcionalidades/README.md` (mantenha o status atualizado ao longo do fluxo).
4. **Pontos em aberto e ambiguidades:** se a funcionalidade depende de uma decisão que é do usuário (regra de negócio nova, item de `em-aberto.md`, troca de comportamento existente), **pergunte agora** (AskUserQuestion), com uma recomendação. Não pergunte o que dá para decidir pelas regras ou pelo código.
5. Funcionalidade só de back-end ou só de front-end: pule os agentes que não se aplicam (e diga isso no relatório). Mudança só visual sem dados novos: `frontend-ui` → `revisor`. Rota nova sem tela: `backend` → `revisor`.

## 2. Construir em paralelo (backend + frontend-ui)

Numa **única mensagem**, duas chamadas da ferramenta Agent (`subagent_type: "backend"` e `"frontend-ui"`). Cada prompt contém:

- os IDs das diretrizes permanentes que tocam o trabalho dele (ele lê os arquivos);
- caminho da especificação e as seções que o agente deve seguir (backend: 2, 3, 4 e 6; frontend-ui: 2, 5 e 6);
- a branch atual e o lembrete de **não** mexer em git;
- o limite de pastas: backend só em `backend/` (e `estrutura.md`/`README.md` quando a especificação pedir); frontend-ui só em `frontend/src/pages`, `components`, `layout`, `superadmin`, CSS e nos **hooks provisórios** do contrato de tela em `frontend/src/data/` (com dados mock no formato combinado); **nunca** em `frontend/src/data/api/`;
- o que entregar no relatório final (o do próprio agente) e "liste qualquer divergência do contrato em vez de mudar o contrato".

Os dois mexem em pastas diferentes da mesma árvore de trabalho; por isso o limite de pastas é obrigatório.

Quando os dois terminarem, leia os relatórios:
- falhou lint/teste/build ou ficou algo de fora? Devolva ao mesmo agente (SendMessage para o agente, se disponível; senão nova chamada com o contexto) antes de seguir;
- divergência do contrato? Decida, **atualize a especificação** e avise o outro lado se for afetado.

## 3. Integrar (frontend-dev)

Chame `subagent_type: "frontend-dev"` com: a especificação, os resumos dos relatórios do backend (rotas, campos, erros reais) e do frontend-ui (telas, hooks provisórios criados), e a instrução de implementar os hooks do contrato chamando a API, sem mudar a assinatura nem o layout das telas.

## 4. Revisar (revisor)

Chame `subagent_type: "revisor"` com: a especificação (com as diretrizes aplicáveis), `git diff main...HEAD` + arquivos novos (`git status`) como escopo, e o número da rodada. Na rodada 2 em diante, inclua os achados da rodada anterior e o que cada agente disse ter corrigido.

O revisor devolve **APROVADO** ou **REPROVADO** com achados, cada um com dono (`backend`, `frontend-ui` ou `frontend-dev`), gravidade e cenário.

## 5. Corrigir (se REPROVADO)

1. Registre a rodada na seção 9 da especificação (data, veredito, achados).
2. Agrupe os achados **bloqueantes e importantes** por dono. Sugestões não bloqueiam: anote para o relatório final.
3. Chame os donos com os achados deles (backend e frontend-ui em paralelo se os dois tiverem achados; frontend-dev depois deles, se também tiver ou se a correção de um deles mudou o contrato).
4. Volte à etapa 4 com a rodada seguinte.
5. **Limite: 3 rodadas.** Se a terceira ainda reprovar, ou se um achado depende de decisão de negócio, pare e leve ao usuário: o que falta, por quê, e as opções.

Achado contestado (o agente dono discorda com argumento): você decide com base nas regras; se for regra de negócio, pergunte ao usuário.

## 6. Entregar (APROVADO)

1. Atualize a especificação (status `aprovada`, histórico) e, se a funcionalidade criou ou mudou regras, o `estrutura.md` e o catálogo `regras-do-sistema` (ver "Manutenção" na skill).
2. Commits na branch `feat/<slug>`, separados por área quando fizer sentido (back, front, docs), mensagens em português no estilo do histórico ("Adiciona ...", "Liga a tela X à API"). **Sem push e sem PR**, a menos que o usuário peça.
3. Relatório ao usuário, curto:
   - o que foi entregue (rotas, telas, regras novas);
   - rodadas de revisão e o que foi corrigido;
   - resultado de testes, lint e build de cada lado (com franqueza sobre o que não rodou);
   - decisões provisórias e perguntas pendentes;
   - sugestões do revisor não aplicadas;
   - próximo passo (ex.: "posso abrir o PR").
