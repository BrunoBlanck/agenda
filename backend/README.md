# Back-end (API)

API do sistema de agendamento multi-loja: FastAPI + PostgreSQL 16 + SQLAlchemy 2 + Alembic.
O modelo do banco segue o [`estrutura.md`](../estrutura.md).

> **Status (etapa 1 de 3):** schema completo, seed de desenvolvimento, login (funcionário e
> superadmin), permissões e `/api/loja/eu`. As rotas CRUD dos menus (etapa 2) e as rotas do
> SUPERADMIN e do site (etapa 3) ainda não existem.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python sozinho; testado com Python 3.14, mínimo 3.12)
- Docker Desktop (para o Postgres local)

Os comandos abaixo funcionam no PowerShell e no Git Bash, a partir da pasta `backend/`.

## Subir do zero

```bash
cd backend
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
# edite o .env e troque JWT_SECRET por um valor aleatório:
#   uv run python -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up -d            # Postgres 16 em localhost:5433 (POSTGRES_PORTA no .env)
uv sync                         # cria .venv com as dependências
uv run python -m scripts.criar_papel_app   # cria o usuário da aplicação (agenda_app)
uv run alembic upgrade head     # cria o schema
uv run python -m scripts.seed   # dados de exemplo do front (pode rodar de novo)
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000/api/saude
- Documentação interativa: http://localhost:8000/docs

Para apagar tudo e recomeçar: `docker compose down -v` e repita os passos.

## Usuários de desenvolvimento (criados pelo seed)

| Área | Loja (slug) | E-mail | Senha | Perfil |
|---|---|---|---|---|
| Superadmin | — | rafael@agendaplataforma.com | `superadmin123` | |
| Superadmin | — | camila@agendaplataforma.com | `superadmin123` | |
| Loja | clinica-sorriso | ana@clinica.com | `senha123` | Administrador |
| Loja | clinica-sorriso | carlos@clinica.com | `senha123` | Profissional |
| Loja | clinica-sorriso | juliana@clinica.com | `senha123` | Recepção |
| Loja | barbearia-navalha | marcos@navalha.com / diego@navalha.com | `senha123` | Administrador / Profissional |
| Loja | escola-harmonia | paula@ / lucas@ / beatriz@ / renata@harmonia.com | `senha123` | Adm. / Prof. / Prof. / Recepção |
| Loja (suspensa) | clinica-bem-estar | sergio@bemestar.com | `senha123` | login recusado (loja suspensa) |
| Loja (cancelada) | dom-corte | igor@domcorte.com | `senha123` | login recusado (inativo, loja cancelada) |

Só a Clínica Sorriso tem os dados completos do `mock.js` (clientes, serviços, locais, materiais,
agendamentos, ponto). O seed se recusa a rodar com `AMBIENTE=producao`.

## Testes e lint

```bash
uv run pytest                   # recria o banco agenda_test (TEST_DATABASE_NAME) a cada execução
uv run ruff check
uv run ruff format --check
```

Os testes usam o Postgres do docker compose (precisa estar no ar) e o mesmo usuário dono do
schema, que precisa ser superusuário para a limpeza entre testes (`session_replication_role`).

Migração reversível: `uv run alembic downgrade base` e `uv run alembic upgrade head`
(também testado em `tests/test_migracoes.py`, num banco separado).

## Endpoints desta etapa

| Método | Caminho | O que faz |
|---|---|---|
| GET | `/api/saude` | API e banco no ar |
| POST | `/api/loja/auth/login` | Login do funcionário: `{slug, email, senha}` → `{token, tipo_token, expira_em}` |
| GET | `/api/loja/eu` | Funcionário, perfil, loja (com rótulos de local), `modulos` e `acessos` efetivos |
| POST | `/api/superadmin/auth/login` | Login do superadmin: `{email, senha}` |
| GET | `/api/superadmin/eu` | Superadmin logado |

Envie o token em `Authorization: Bearer <token>`. Token de superadmin não vale nas rotas da loja,
e vice-versa (401). Loja suspensa ou cancelada recebe 403.

## Como o banco protege os dados

- **Dois usuários no Postgres.** O dono do schema (`DATABASE_OWNER_URL`) roda as migrações. A API
  usa `agenda_app` (`DATABASE_URL`), sem privilégio de dono: para ele valem o RLS e o `REVOKE` de
  `UPDATE`/`DELETE` na `auditoria`.
- **Contexto da transação.** Cada requisição é uma transação; no início, `app/db.py`
  (`definir_contexto`) grava `app.funcionario_id`, `app.superadmin_id`, `app.loja_id`, `app.origem`
  e `app.ip` com `set_config(..., true)`. Os triggers e o RLS leem esses valores.
- **Triggers em todas as tabelas** (`migrations/auxiliares.py`): preenchem `criado_em`,
  `atualizado_em`, `atualizado_por`, `excluido_em` e `excluido_por`; convertem `DELETE` em
  exclusão lógica; gravam a `auditoria` (inserir, alterar, excluir, restaurar, sem `senha_hash`).
- **Exclusão lógica.** O ORM esconde linhas excluídas em toda consulta (`app/db.py`); para vê-las,
  use `.execution_options(incluir_excluidos=True)`. Unicidade por índice único parcial.
- **Isolamento entre lojas.** FKs compostas `(loja_id, x_id)`, filtro pelo `loja_id` do token nas
  rotas e RLS como segunda camada.
- **Permissões.** `exigir(recurso, nivel)` (`app/auth/dependencias.py`) confere perfil, módulo
  ligado na loja e status da loja, igual a `frontend/src/data/useAcesso.js`.

### Tabela nova

Na migração: colunas de controle (`CONTROLE_LOJA`/`CONTROLE_PLATAFORMA`), índices únicos parciais e
`tabela_loja(...)` (ou `ligar_triggers(...)` na plataforma) e `fks_controle_loja(...)`. Os testes de
`tests/test_migracoes.py` falham se a tabela ficar sem triggers, RLS ou FKs de controle.

## Docker

O `Dockerfile` gera uma imagem simples da API (x86 e ARM), configurada só por variáveis de ambiente:

```bash
docker build -t agenda-backend .
```
