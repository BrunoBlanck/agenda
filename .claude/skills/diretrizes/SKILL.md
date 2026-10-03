---
name: diretrizes
description: Sistema de memória do time de agentes - como registrar, aplicar, verificar e revogar diretrizes permanentes (ordens do usuário que valem para sempre, como "em todas as telas X faça Y", "padronize Z no back-end", "a partir de agora sempre/nunca..."), e o que vai em cada camada de memória. Use sempre que o usuário der uma ordem que deve valer além da tarefa atual, ou antes de começar qualquer tarefa para conferir as diretrizes ativas.
---

# Diretrizes permanentes e camadas de memória

## As camadas de memória do projeto

| Camada | Onde | O que guarda | Quem escreve | Quem lê |
|---|---|---|---|---|
| **1. Diretrizes permanentes** | `.claude/diretrizes/` (`INDICE.md` + um arquivo por diretriz) | **Ordens do usuário** que valem para sempre: padronizações, "em todas as telas…", "sempre/nunca…" | quem recebeu a ordem (de preferência o coordenador) | **todos**, em toda tarefa; o revisor cobra |
| 2. Regras de negócio | `estrutura.md` + skill `regras-do-sistema` | Como o negócio funciona (agendamento, acesso, estoque…) | coordenador | todos |
| 3. Padrões técnicos | skills `backend-seguro`, `padroes-ui`, `integracao-api` | Boas práticas de base (segurança, UI, integração) | coordenador, quando o usuário pede ou uma diretriz vira padrão | quem constrói e o revisor |
| 4. Histórico da funcionalidade | `docs/funcionalidades/<slug>.md` | Contrato e rodadas de revisão daquela entrega | coordenador | agentes daquela entrega |
| 5. Memória privada do agente | `.claude/agent-memory/<agente>/` | Aprendizados do próprio agente: armadilhas confirmadas, como rodar algo, o que foi tentado e rejeitado | o próprio agente | só ele |

**Regra de ouro:** se veio do usuário como ordem e vale para o futuro, é **camada 1**, não memória privada. A memória privada é só do agente que a escreveu e o revisor não a cobra; uma diretriz é de todos e é verificada a cada revisão.

O `INDICE.md` é carregado em toda sessão (importado pelo `CLAUDE.md` da raiz) e esta skill é pré-carregada em todos os agentes. Um hook (`.claude/hooks/lembrar-diretriz.mjs`) avisa quando uma mensagem do usuário parece uma ordem permanente.

## Quando é uma diretriz

Sinais: "em todas as telas / rotas / formulários / tabelas", "sempre", "nunca mais", "a partir de agora", "daqui pra frente", "padronize", "todo X deve…", "toda vez que…", ou uma correção que o usuário claramente não quer repetir ("não faça mais isso").

Não é diretriz: um ajuste pontual numa tela só, uma regra de negócio (vai para a camada 2), uma preferência de como conversar.

**Na dúvida, pergunte** em uma linha: "Isso vale só para esta tela ou para todas daqui em diante?"

## Registrar (antes de executar a ordem)

1. **Confira se já existe** uma diretriz parecida no `INDICE.md`. Se existe, **atualize** ou **substitua** (a antiga vira `substituída por DIR-00N`), nunca crie uma duplicada ou contraditória.
2. **Conflito** com uma diretriz ativa, com uma regra de negócio ou com um padrão de segurança (`backend-seguro`): não registre; mostre o conflito ao usuário e pergunte qual vale.
3. Crie `.claude/diretrizes/DIR-NNN-<slug>.md` com o próximo número livre (nunca reaproveite um número):

```markdown
---
id: DIR-NNN
titulo: <curto>
status: ativa            # ativa | aplicação pendente | substituída por DIR-NNN | revogada
escopo: [backend | frontend-ui | frontend-dev | revisor | coordenador]   # quem precisa seguir
onde: <globs ou descrição: frontend/src/pages/**, "todas as telas de cadastro", backend/app/routers/loja/**>
criada_em: AAAA-MM-DD
substitui: — | DIR-NNN
---

## Ordem do usuário
<as palavras do usuário, resumidas fielmente, com a data>

## Regra
<o que fazer, objetivo e verificável; o que é proibido; com exemplo curto se ajudar>

## Exceções
<onde não se aplica, ou "Nenhuma">

## Como verificar
<comando grep/teste ou checagem objetiva que o revisor roda para confirmar>

## Aplicação no código existente
- [ ] <arquivo/tela/rota 1>
- [ ] <arquivo/tela/rota 2>
```

4. Acrescente a linha no `INDICE.md` (ID, escopo, diretriz em uma frase, status, link). O índice fica curto: o detalhe mora no arquivo.
5. Se a diretriz muda um padrão técnico de base, atualize também o item da skill correspondente (`padroes-ui`, `backend-seguro`, `integracao-api`) citando o ID da diretriz.
6. Diga ao usuário, em uma linha, que a ordem foi registrada como `DIR-NNN` e vai valer daqui em diante.

## Aplicar no que já existe

"Em todas as telas X" vale também para as telas que **já existem**. Ao registrar:

1. Levante tudo o que está no escopo (Grep/Glob, ou o agente `Explore`) e preencha a lista "Aplicação no código existente".
2. Status `aplicação pendente` até a lista fechar; `ativa` quando todos os itens estiverem marcados.
3. Conduza a aplicação como uma funcionalidade (skill `nova-funcionalidade`): o dono do escopo aplica, o revisor confere com o "Como verificar". Lista grande vira lotes; cada lote marca os itens feitos.

## Seguir (todo agente, em toda tarefa)

1. No início: leia o `INDICE.md`, selecione as diretrizes **ativas** ou **aplicação pendente** cujo `escopo` inclui você e cujo `onde` toca a tarefa, e **leia o arquivo completo** de cada uma.
2. Ao construir: cumpra cada uma. Se uma diretriz impede a tarefa ou parece errada para o caso, **não a ignore em silêncio**: siga-a e relate, ou pare e pergunte.
3. No relatório final: liste as diretrizes aplicadas (`DIR-001 ✔`) e qualquer exceção.

## Verificar (revisor)

Para cada diretriz no escopo do diff: rode o "Como verificar". Violação é achado **bloqueante** (é uma ordem explícita do usuário), com o ID da diretriz no lugar do código do checklist.

## Revogar ou mudar

Só por ordem do usuário. Mude o status para `revogada` (ou `substituída por DIR-NNN`), registre a data e o motivo no arquivo, e atualize o índice. Não apague o arquivo: o histórico explica por que o código está como está.
