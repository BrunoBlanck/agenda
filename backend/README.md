# Back-end (API)

API do sistema de agendamento multi-loja: FastAPI + PostgreSQL 16 + SQLAlchemy 2 + Alembic.
O modelo do banco segue o [`estrutura.md`](../estrutura.md).

> **Status:** schema completo, seed, login (funcionário e superadmin), permissões e as rotas das três
> áreas: **painel da loja** (`/api/loja/...`), **SUPERADMIN** (`/api/superadmin/...`) e **site do
> consumidor** (`/api/site/{slug}/...`). O front-end ainda usa os dados de exemplo e não está ligado à
> API (ver "O que o front precisa adaptar").

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

## Endpoints

A lista completa, com os campos de entrada e saída, está em http://localhost:8000/docs (OpenAPI).
Envie o token em `Authorization: Bearer <token>`. Token de superadmin não vale nas rotas da loja,
e vice-versa (401). Loja suspensa ou cancelada recebe 403.

| Área | Rotas (`/api/loja/...`) | Recurso exigido |
|---|---|---|
| Acesso | `POST auth/login`, `GET eu`, `GET recursos` | — |
| Início | `GET inicio` (cada bloco conforme o acesso) | — |
| Clientes | `GET/POST clientes`, `GET/PUT/DELETE clientes/{id}`, `GET clientes/{id}/historico` | `clientes` |
| Funcionários | `GET/POST funcionarios`, `GET/PUT funcionarios/{id}`, `GET/POST cargos`, `PUT/DELETE cargos/{id}` | `funcionarios` |
| Perfis | `GET/POST perfis`, `GET/PUT/DELETE perfis/{id}`, `PUT perfis/{id}/acessos` | `perfis_acesso` (lista também com `config_agendamentos` ou `funcionarios`) |
| Jornada e bloqueios | `GET horarios`, `POST perfis/{id}/horarios`, `DELETE horarios/{id}`, `GET/POST bloqueios`, `DELETE bloqueios/{id}` | `config_agendamentos` |
| Serviços | `GET/POST servicos`, `GET/PUT/DELETE servicos/{id}` (com profissionais, locais e materiais) | `servicos` |
| Locais | `GET/POST locais`, `GET/PUT locais/{id}`, `GET/PUT locais/rotulos` | `locais` |
| Materiais | `GET/POST materiais`, `GET/PUT/DELETE materiais/{id}`, `GET/POST materiais/{id}/movimentacoes`, `GET/POST categorias-material`, `PUT/DELETE categorias-material/{id}` | `materiais` |
| Agendamentos | `GET/POST agendamentos`, `GET/PUT/DELETE agendamentos/{id}`, `POST agendamentos/{id}/status`, `POST .../aceitar`, `POST .../recusar`, `PUT .../materiais` | `agenda_propria` / `agenda_equipe` |
| Apoio ao formulário | `GET apoio/agendamento`, `GET apoio/disponibilidade` | escrita na agenda |
| Agenda | `GET agenda?inicio=&fim=&funcionario_id=` (semana, mês ou dia) | `agenda_propria` / `agenda_equipe` |
| Controle de Tempo | `GET ponto`, `GET ponto/aberto`, `POST ponto/registrar`, `POST ponto`, `PUT ponto/{id}` | `ponto_proprio` / `ponto_equipe` |
| Configurações | `GET/PUT configuracoes/loja`, `DELETE configuracoes/loja/logo` | `config_loja` |

Saúde: `GET /api/saude`.

### SUPERADMIN (`/api/superadmin/...`, só com token de superadmin)

| Área | Rotas |
|---|---|
| Acesso | `POST auth/login`, `GET eu` |
| Visão geral | `GET visao-geral` (lojas por situação e tipo, funcionários, receita, módulos, últimas ações) |
| Lojas | `GET/POST lojas`, `GET lojas/opcoes`, `GET/PUT/DELETE lojas/{id}`, `POST lojas/{id}/status` |
| Módulos da loja | `GET lojas/{id}/modulos`, `PATCH lojas/{id}/modulos/{codigo}` (habilitado, observacao, expira_em) |
| Funcionários (suporte) | `GET lojas/{id}/perfis`, `GET/POST lojas/{id}/funcionarios`, `PUT lojas/{id}/funcionarios/{fid}`, `POST .../redefinir-senha` |
| Planos | `GET/POST planos`, `GET/PUT/DELETE planos/{id}` |
| Usuários admin | `GET/POST usuarios`, `GET/PUT/DELETE usuarios/{id}` |
| Auditoria | `GET auditoria?loja=<id ou plataforma>&tabela=&periodo=&inicio=&fim=&quem=`, `GET auditoria/pessoas`, `GET auditoria/tabelas` |

- O superadmin escolhe a loja pela URL. Nas tabelas da loja, o que ele grava fica com
  `atualizado_por` NULL e a auditoria guarda o `superadmin_id` (origem `superadmin`).
- Sem envio de e-mail ainda: criar loja, funcionário ou usuário admin sem `senha`, e redefinir senha
  sem `senha`, geram uma **senha provisória**, devolvida uma única vez em `senha_provisoria`.
- Loja só é excluída (exclusão lógica) depois de cancelada; o `slug` fica livre de novo.
- Auditoria: `periodo` = `hoje`, `7d`, `30d` (padrão), `90d`, `ano` ou `intervalo` (com `inicio` e
  `fim`), nos dias do fuso da loja; `quem` = `f:<id>`, `s:<id>`, `site` ou `sistema` (valores de
  `auditoria/pessoas`). Cada item traz `quem` com o nome resolvido, `rotulo` do registro e
  `mudancas` (campo, antes, depois); a troca de senha aparece como `senha: •••••• → redefinida`.

### Site do consumidor (`/api/site/{slug}/...`, público)

| Rota | O que faz |
|---|---|
| `GET /api/site/{slug}` | Dados públicos da loja (contato, endereço, tipo, `usa_servicos`, `usa_locais`) |
| `GET servicos` | Serviços ativos com os profissionais habilitados (sem o módulo Serviços: "Atendimento", 30 min) |
| `GET locais?servico_id=` | Locais ativos (id, nome, tipo; sem link) |
| `GET horarios?servico_id=&funcionario_id=&inicio=&fim=` | Horários livres por dia (até 31 dias), com o profissional e o local reservados |
| `POST agendamentos` | Pedido do cliente: vira agendamento `pendente`, `origem = site` |

- Loja inexistente, excluída, suspensa ou cancelada: **404** em todas as rotas.
- Horários livres seguem as regras do painel (jornada, bloqueios, ocupação, local permitido e livre)
  com 60 min de antecedência e passos de 30 min. O pedido só é aceito num horário oferecido; o banco
  recusa a corrida entre dois pedidos (409).
- O cliente é identificado pelo telefone (mesma loja): se já existe, ganha o canal `site` e o cadastro
  não muda; senão é criado. A resposta não traz dados do cadastro existente.
- **Sem proteção contra abuso ainda** (rate limit, captcha): ver próximos passos.

### O que o front precisa adaptar

- **Ids** são uuid; os campos seguem o banco em `snake_case` (`preco_mensal`, `nome_fantasia`,
  `plano_id`...). Datas vêm com o fuso da loja.
- **Lojas (SUPERADMIN):** lista paginada (`itens`, `total`); `GET lojas/opcoes` para os selects.
  `modulos` na criação é a lista de códigos. Funcionário usa `perfil_id` (de `GET lojas/{id}/perfis`),
  não o nome do perfil. Módulos via `PATCH` com só o campo alterado. Mostrar `senha_provisoria` quando
  vier (o texto "recebe um e-mail para definir a senha" ainda não vale).
- **Redefinir senha** troca a senha na hora (informada ou provisória), em vez de "enviar link".
- **Auditoria:** a busca e o filtro de pessoa vêm do servidor (paginados); usar `mudancas` em vez de
  comparar `antes`/`depois` no navegador (as colunas são as do banco, ex.: `inicio` em vez de
  `data`/`hora`). A operação `restaurar` também pode aparecer.
- **Site:** loja suspensa responde 404 (o front hoje mostra "Agendamento online indisponível" a
  partir de `status`); os horários vêm prontos de `GET horarios` (não calcular no navegador); o pedido
  manda `funcionario_id`, `inicio` e opcionalmente `local_id` do horário escolhido.

Convenções das rotas da loja:

- **Isolamento:** tudo usa o `loja_id` do token; recurso de outra loja responde **404**.
- **Permissões:** `exigir(recurso, nivel)` em toda rota; módulo desligado responde 403 até para o
  Administrador. Leitura não escreve (403 "Você só tem permissão de leitura aqui.").
- **Datas:** `inicio`, `fim`, `entrada`... sem fuso são lidos no fuso da loja; a resposta vem com o
  fuso da loja (ex.: `2030-01-07T09:00:00-03:00`). Filtros por dia (`inicio`/`fim` como `date`)
  usam o dia da loja.
- **Listas que crescem** (clientes, agendamentos, histórico, movimentações) são paginadas:
  `?pagina=1&por_pagina=20` → `{itens, total, pagina, por_pagina}`.
- **Dinheiro e quantidades** saem como número no JSON.
- **Última alteração:** as respostas trazem `criado_em`, `atualizado_em`, `atualizado_por` e
  `atualizado_por_nome` (componente `UltimaAlteracao` do front).
- **Erros** em português: `{"detail": "..."}`; validação (422) traz também `erros: [{campo, mensagem}]`.

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
- **Regras de negócio** que não cabem na rota ficam em `app/services/` (agendamentos, jornada e
  bloqueios, estoque, serviços).

### Tabela nova

Na migração: colunas de controle (`CONTROLE_LOJA`/`CONTROLE_PLATAFORMA`), índices únicos parciais e
`tabela_loja(...)` (ou `ligar_triggers(...)` na plataforma) e `fks_controle_loja(...)`. Os testes de
`tests/test_migracoes.py` falham se a tabela ficar sem triggers, RLS ou FKs de controle.

## Docker

O `Dockerfile` gera uma imagem simples da API (x86 e ARM), configurada só por variáveis de ambiente:

```bash
docker build -t agenda-backend .
```
