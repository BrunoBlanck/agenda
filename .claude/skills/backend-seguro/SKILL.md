---
name: backend-seguro
description: Padrões obrigatórios do back-end Python (FastAPI + SQLAlchemy 2 + PostgreSQL) deste projeto - segurança (OWASP API Top 10 2023 / ASVS 5), correção lógica, performance e código limpo - em forma de checklist. Use ao escrever ou revisar código em backend/.
user-invocable: false
---

# Back-end seguro, correto e rápido

Checklist usado por dois agentes: o **backend** aplica ao escrever, o **revisor** confere item por item. Cada item tem código (`SEG-03`) para ser citado nas revisões. Base: OWASP API Security Top 10 (2023), OWASP ASVS 5.0, RFC 8725 (JWT) e as regras do projeto (skill `regras-do-sistema`).

**APIs mudam.** Antes de usar uma API do FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pyjwt ou pwdlib que você não confirmou no código deste projeto, consulte a documentação atual (Context7: `resolve-library-id` → `query-docs`, se disponível; senão a documentação oficial). Não escreva de memória.

## 1. Segurança

### Autorização (API1 BOLA, API3, API5 BFLA)
- **SEG-01** Toda rota da loja depende de `exigir(recurso, nivel)` (`app/auth/dependencias.py`). Rota nova sem ela é defeito bloqueante. Ação de escrita exige `escrita`; leitura exige `leitura`.
- **SEG-02** Todo acesso a registro por id filtra **`loja_id` do token** na mesma consulta (`where(Model.loja_id == ctx.loja_id, Model.id == id)`), nunca busca por id e confere depois. Outra loja = **404**.
- **SEG-03** Regras de visibilidade além do recurso (AGE-22: só Minha agenda vê só os próprios) aplicadas **na consulta**, também em listas, contagens, buscas e rotas de detalhe/histórico.
- **SEG-04** **Sem atribuição em massa:** schemas de entrada com `model_config = ConfigDict(extra='forbid')` e só os campos editáveis. Nunca aceitar `loja_id`, `id`, `criado_por`, `atualizado_*`, `excluido_*`, `status` (fora das rotas de status), `acesso_total`, `senha_hash` do corpo. Nunca `Model(**dados)` com o dicionário cru da requisição.
- **SEG-05** **Sem escalada:** quem atribui perfil/nível não pode conceder mais do que tem (ACE-19); o último Administrador nunca é removido (ACE-20). Teste para os dois.
- **SEG-06** Respostas só com os campos necessários (schemas de saída explícitos, `response_model`). Nunca `senha_hash`, nunca dados de outra loja, nunca dados de cliente no site público (API3 exposição excessiva).

### Autenticação e sessão (API2)
- **SEG-07** JWT: algoritmo fixo na verificação (`algorithms=[...]`, nunca o do cabeçalho), `exp` curto, `iat`, tipo do usuário validado (funcionário ≠ superadmin), segredo forte só do `.env`. A cada requisição, reconferir usuário ativo e loja ativa (ACE-04).
- **SEG-08** Login: mesma mensagem e tempo parecido para e-mail inexistente e senha errada (sem enumeração de contas); Argon2 via `pwdlib`; senha mínima 8; nunca logar senha ou token.
- **SEG-09** Rotas públicas e de login precisam de **limite de requisições** (pendente no projeto, SIT-10/ABE-23). Rota pública nova sem isso: registrar como risco no relatório.

### Entrada e injeção (API8, API10)
- **SEG-10** Validar **tudo** com Pydantic: tamanhos máximos iguais aos do banco, enums, faixas (`ge`/`gt`), formatos (e-mail, CPF/CNPJ com dígito, telefone, `#rrggbb`), datas coerentes (`fim > inicio`), listas com tamanho máximo, ids como `UUID`.
- **SEG-11** SQL só por SQLAlchemy com parâmetros. Texto dinâmico em SQL (`text()`, `op.execute`, `set_config`) **sempre** com parâmetros ligados; nada de f-string com valor do usuário. Ordenação/filtro dinâmico por lista branca de colunas.
- **SEG-12** **Limites contra abuso de recurso (API4):** `por_pagina` com máximo (ex.: 100); intervalos de datas com máximo (ex.: 31 dias no site, 1 ano em relatórios); buscas textuais com tamanho mínimo/máximo; uploads com tamanho máximo verificado antes de ler tudo.
- **SEG-13** Upload (logo): validar tipo pelo conteúdo (assinatura do arquivo), não pela extensão; **SVG sanitizado** ou recusado (script embutido = XSS); nome gerado pelo servidor; caminho por loja; nunca montar caminho com texto do usuário.
- **SEG-14** Nada de buscar URL informada pelo usuário no servidor sem lista branca (SSRF, API7).

### Configuração e dados (API8)
- **SEG-15** CORS só com as origens do `.env` (nunca `*` com credenciais). `/docs` e `/openapi.json` desligáveis em produção. Mensagens de erro sem stack trace, SQL ou nome de constraint.
- **SEG-16** Segredos só em variável de ambiente; `.env` fora do git; `.env.example` sem valor real.
- **SEG-17** Logs sem dados pessoais (CPF, telefone, e-mail de cliente), senha ou token. Logar o tipo do erro e ids técnicos.
- **SEG-18** Dependências: nova dependência só com motivo; versão travada no `uv.lock`. Quando possível, `uvx pip-audit` (ou equivalente) para vulnerabilidades conhecidas.

## 2. Correção lógica (o sistema não pode aceitar o que não faz sentido)

- **LOG-01** **Invariantes no banco** quando possível (`CHECK`, `UNIQUE` parcial, `EXCLUDE`, FK composta, trigger), e também validadas no serviço para devolver mensagem clara. O banco é a última barreira, não a única.
- **LOG-02** **Concorrência:** regra do tipo "verificar e depois gravar" (último administrador, último superadmin, horário livre, estoque) precisa de restrição no banco ou de `SELECT ... FOR UPDATE` na mesma transação. Violação de restrição vira 409 com mensagem em português (mapeada em `app/erros.py`).
- **LOG-03** **Máquina de estados:** transições só pelas permitidas (`TRANSICOES`, AGE-17). Qualquer outra = 409/422 com mensagem. Testar cada transição proibida relevante.
- **LOG-04** **Dinheiro e quantidades** com `Decimal` (nunca `float`), arredondamento explícito em 2 casas; nada negativo onde não faz sentido (preço, duração, quantidade de vínculo); sinais conforme MAT-03.
- **LOG-05** **Datas:** todo `datetime` com fuso (`timezone.utc` ou fuso da loja via `zoneinfo`); nunca `datetime.now()` sem fuso; "dia" sempre no fuso da loja (GER-15); `fim > inicio`; hora "agora" do servidor (GER-17). Cuidado com horário de verão e virada de dia.
- **LOG-06** **Atomicidade:** operação com vários passos (concluir agendamento + baixa de estoque; criar loja + perfis + módulos + admin) numa única transação; falha no meio desfaz tudo.
- **LOG-07** **Idempotência e repetição:** clicar duas vezes não pode criar dois registros nem dar duas baixas. Mudança de status repetida para o mesmo status é recusada ou ignorada de forma explícita.
- **LOG-08** Registros inativos/excluídos não entram em usos novos (cliente inativo, profissional inativo, local inativo, serviço inativo, plano inativo).
- **LOG-09** Toda regra do catálogo citada na especificação tem **teste** (caso válido e inválido). Toda rota da loja tem teste de **isolamento** (loja A não lê nem altera a loja B) e de **permissão** (nível insuficiente = 403; módulo desligado = 403).
- **LOG-10** Casos-limite nos testes: listas vazias, `null` nos opcionais, textos no tamanho máximo, fronteiras de horário (encostado no fim da jornada, encostado em outro agendamento), virada de dia/mês.

## 3. Performance

- **PER-01** Sem N+1: relacionamentos carregados com `selectinload`/`joinedload` ou consulta agregada; nunca consulta dentro de laço sobre resultados.
- **PER-02** Consultas de lista: paginação no banco (`limit/offset` ou chave), `count` separado e barato, só as colunas necessárias quando a lista é grande.
- **PER-03** Índice para todo filtro/ordenação frequente, começando por `loja_id` (ex.: `(loja_id, inicio)`). Índice novo vai na migração. Em dúvida, `EXPLAIN ANALYZE` com o seed.
- **PER-04** Trabalho pesado fora da requisição quando existir fila (ainda não há); até lá, não fazer chamadas externas lentas dentro da transação.
- **PER-05** Transações curtas: nada de esperar I/O externo com transação aberta.

## 4. Código limpo

- **LIM-01** Camadas: `routers/` recebe, valida (schemas) e devolve; regra de negócio em `services/`; modelos em `models/`; nada de SQL solto no router quando a regra é reutilizada.
- **LIM-02** Funções pequenas, nomes de domínio em português, tipagem completa (`Mapped[]`, anotações em funções públicas), sem código morto nem comentário óbvio.
- **LIM-03** Reaproveitar antes de criar: `app/services/comum.py`, `app/schemas/comum.py`, `app/auth/dependencias.py`, `migrations/auxiliares.py` (`tabela_loja`, `ligar_triggers`, `fks_controle_loja`).
- **LIM-04** Mensagens de erro em português, prontas para o usuário, e consistentes com as já existentes.
- **LIM-05** Migração reversível (`downgrade` funciona) e testada por `tests/test_migracoes.py`.
- **LIM-06** `uv run ruff check`, `uv run ruff format --check` e `uv run pytest` passando antes de entregar.
