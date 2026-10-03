# Agendamento multi-loja

SaaS de agendamento para clínicas, barbearias e escolas: painel da loja e painel SUPERADMIN em React (`frontend/`), API em FastAPI + PostgreSQL (`backend/`), site do consumidor futuro renderizado pelo back-end. Regras de negócio e banco: `estrutura.md`. Como rodar: `README.md` e `backend/README.md`.

## Time de agentes

`coordenador` (regras e fluxo), `backend`, `frontend-ui`, `frontend-dev`, `revisor`, em `.claude/agents/`. Funcionalidade nova segue a skill `nova-funcionalidade`, na conversa principal.

## Diretrizes permanentes (sempre valem)

Ordens do usuário que valem para sempre ficam em `.claude/diretrizes/`. Siga a skill `diretrizes`:
- **Antes de qualquer tarefa:** confira o índice abaixo e leia o arquivo completo das diretrizes que tocam a tarefa.
- **Quando o usuário der uma ordem que vale além da tarefa atual** ("em todas as telas…", "sempre…", "nunca mais…", "padronize…", "a partir de agora…"): registre-a como diretriz **antes** de executar e planeje a aplicação no código que já existe.
- Ordem do usuário é diretriz, não memória privada de agente.

@.claude/diretrizes/INDICE.md
