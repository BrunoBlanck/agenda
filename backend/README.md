# Back-end (API)

API do sistema de agendamento multi-loja: FastAPI + PostgreSQL 16 + SQLAlchemy 2 + Alembic.
O modelo do banco segue o [`estrutura.md`](../estrutura.md).

> **Status:** schema completo, seed, login (funcionário e superadmin), permissões e as rotas das três
> áreas: **painel da loja** (`/api/loja/...`), **SUPERADMIN** (`/api/superadmin/...`) e **site do
> consumidor** (`/api/site/{slug}/...`). O front-end (painel da loja e SUPERADMIN) está **ligado à API**
> (ver "Integração com o front").

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
agendamentos, ponto). Os CPFs dos clientes são fictícios, mas com dígito verificador válido; rodar o seed
de novo corrige o CPF inválido (ou vazio) dos clientes do seed gravados por versões antigas. Os
funcionários do seed não têm CPF. O seed se recusa a rodar com `AMBIENTE=producao`.

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
e vice-versa (401). Loja suspensa ou cancelada recebe 403 (menos na sessão de suporte, abaixo).
`GET eu` traz `sessao: {suporte, expira_em}` (`expira_em` = vencimento do token, no fuso da loja).

| Área | Rotas (`/api/loja/...`) | Recurso exigido |
|---|---|---|
| Acesso | `POST auth/login`, `GET eu`, `GET recursos` | — |
| Início | `GET inicio` (cada bloco conforme o acesso) | — |
| Clientes | `GET/POST clientes`, `GET/PUT/DELETE clientes/{id}`, `GET clientes/{id}/historico` | `clientes` |
| Funcionários | `GET/POST funcionarios`, `GET/PUT funcionarios/{id}`, `GET/POST cargos`, `PUT/DELETE cargos/{id}` | `funcionarios` |
| Perfis | `GET/POST perfis`, `GET/PUT/DELETE perfis/{id}`, `PUT perfis/{id}/acessos` | `perfis_acesso` (lista também com `config_agendamentos` ou `funcionarios`) |
| Catálogo de recursos | `GET recursos` (`codigo`, `nome`, `leitura`, `escrita`, `descricao`, `modulo`, `modulo_ativo`, `ordem`) | — (só login) |
| Jornada e bloqueios | `GET horarios`, `POST perfis/{id}/horarios`, `DELETE horarios/{id}`, `GET/POST bloqueios`, `DELETE bloqueios/{id}` | `config_agendamentos` |
| Serviços | `GET/POST servicos`, `GET/PUT/DELETE servicos/{id}` (com profissionais, locais e materiais), `GET servicos/opcoes` (profissionais, locais e materiais ativos para o formulário; escrita) | `servicos` |
| Locais | `GET/POST locais`, `GET/PUT locais/{id}`, `GET/PUT locais/rotulos` | `locais` |
| Materiais | `GET/POST materiais`, `GET/PUT/DELETE materiais/{id}`, `GET/POST materiais/{id}/movimentacoes`, `GET/POST categorias-material`, `PUT/DELETE categorias-material/{id}` | `materiais` |
| Agendamentos | `GET/POST agendamentos`, `GET/PUT/DELETE agendamentos/{id}`, `POST agendamentos/{id}/status`, `POST .../aceitar`, `POST .../recusar`, `PUT .../materiais` | `agenda_propria` / `agenda_equipe` |
| Apoio ao formulário | `GET apoio/agendamento`, `GET apoio/clientes?busca=`, `GET apoio/disponibilidade` | escrita na agenda |
| Filtros da agenda | `GET apoio/filtros-agenda` (`so_propria`, profissionais e locais, inclusive inativos) | leitura na agenda |
| Agenda | `GET agenda?inicio=&fim=&funcionario_id=` (semana, mês ou dia) | `agenda_propria` / `agenda_equipe` |
| Controle de Tempo | `GET ponto`, `GET ponto/aberto`, `POST ponto/registrar` (`{"acao": "entrada"\|"saida"}`), `POST ponto`, `PUT ponto/{id}`, `GET ponto/funcionarios` (lista de apoio, com inativos; leitura em `ponto_equipe`) | `ponto_proprio` / `ponto_equipe` |
| Configurações | `GET/PUT configuracoes/loja`, `PUT/DELETE configuracoes/loja/logo` (ver "Logo da loja") | `config_loja` |

Saúde: `GET /api/saude`. Arquivos públicos: `GET /api/arquivos/logos/{loja_id}/{nome}` (sem login).

### SUPERADMIN (`/api/superadmin/...`, só com token de superadmin)

| Área | Rotas |
|---|---|
| Acesso | `POST auth/login`, `GET eu` |
| Visão geral | `GET visao-geral` (lojas por situação e tipo, funcionários, receita, módulos, `modulos_expirando`, últimas ações) |
| Lojas | `GET/POST lojas`, `GET lojas/opcoes`, `GET/PUT/DELETE lojas/{id}`, `POST lojas/{id}/status`, `PUT/DELETE lojas/{id}/logo` |
| Módulos da loja | `GET lojas/{id}/modulos`, `PATCH lojas/{id}/modulos/{codigo}` (habilitado, observacao, expira_em) |
| Funcionários (suporte) | `GET lojas/{id}/perfis`, `GET/POST lojas/{id}/funcionarios`, `PUT lojas/{id}/funcionarios/{fid}`, `POST .../redefinir-senha` |
| Acessar loja | `POST lojas/{id}/acesso` (token de funcionário do Administrador da loja, 1 hora) |
| Planos | `GET/POST planos`, `GET/PUT/DELETE planos/{id}` |
| Usuários admin | `GET/POST usuarios`, `GET/PUT/DELETE usuarios/{id}` |
| Auditoria | `GET auditoria?loja=<id ou plataforma>&tabela=&periodo=&inicio=&fim=&quem=`, `GET auditoria/pessoas`, `GET auditoria/tabelas` |

- O superadmin escolhe a loja pela URL. Nas tabelas da loja, o que ele grava fica com
  `atualizado_por` NULL e a auditoria guarda o `superadmin_id` (origem `superadmin`).
- Sem envio de e-mail ainda: criar loja, funcionário ou usuário admin sem `senha`, e redefinir senha
  sem `senha`, geram uma **senha provisória**, devolvida uma única vez em `senha_provisoria`.
- Loja só é excluída (exclusão lógica) depois de cancelada; o `slug` fica livre de novo.
- **Acessar loja** (PLA-17 a 19, `app/services/suporte.py`): token do tipo `funcionario` do
  Administrador da loja (perfil padrão com acesso total, ativo, o mais antigo), com a claim
  `suporte: true` e validade fixa de 1 hora (`VALIDADE_SUPORTE`, não usa `JWT_EXPIRA_MINUTOS`). Com a
  claim, `obter_contexto_loja` só dispensa a loja ativa (vale suspensa ou cancelada); o resto é igual
  e o que for feito fica como o Administrador. Gerar o acesso grava `registrar_acao` na auditoria da
  loja como ação do superadmin (`{"acao": "acessar_loja", "como_funcionario": ...}`), sem o token, e
  não mexe em `ultimo_login_em`. Não há revogação: o token vale até vencer.
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
| `GET horarios?servico_id=&funcionario_id=&local_id=&inicio=&fim=` | Horários livres por dia (até 31 dias), com o profissional e o local reservados (`local_id` opcional: só horários com aquele local livre) |
| `POST agendamentos` | Pedido do cliente: vira agendamento `pendente`, `origem = site` |

- Loja inexistente, excluída, suspensa ou cancelada: **404** em todas as rotas.
- Horários livres seguem as regras do painel (jornada, bloqueios, ocupação, local permitido e livre)
  com 60 min de antecedência e passos de 30 min. O pedido só é aceito num horário oferecido; o banco
  recusa a corrida entre dois pedidos (409).
- O cliente é identificado pelo telefone (mesma loja): se já existe, ganha o canal `site` e o cadastro
  não muda; senão é criado. A resposta não traz dados do cadastro existente.
- **Proteção contra abuso** (ver "Limite de requisições"): limite por IP em todas as rotas do site, limite
  de pedidos por IP em cada loja (429 com `Retry-After`) e no máximo `SITE_PENDENTES_POR_TELEFONE`
  pedidos aguardando aceite por telefone (409). Captcha ainda não existe.

### Páginas HTML (fora de `/api`)

Mapa de URLs (GER-29), igual no nginx de produção ([`deploy/nginx/agenda.conf`](../deploy/nginx/agenda.conf))
e no servidor de dev do front: `/superadmin...` e `/<slug>/painel...` são do front (SPA); `/_app/...`
são os arquivos do build; `/api/...`, `/<slug>` e o resto chegam aqui. As páginas ficam em
`app/routers/paginas.py` (Jinja2 com autoescape, templates em `app/templates/`), registradas depois de
todos os routers `/api` e da documentação, e fora do OpenAPI.

| Rota (GET e HEAD) | Resposta |
|---|---|
| `/` | 404 HTML "Página não encontrada" |
| `/painel`, `/painel/...` | 404 HTML com a orientação de usar `/nome-da-loja/painel` |
| `/{slug}` | 200, página provisória da loja (SIT-11: logo, nome, telefone, e-mail, endereço, "Agendamento online em breve"); loja inexistente, excluída, suspensa ou cancelada, slug inválido ou reservado: 404 HTML "Loja não encontrada" |
| `/{slug}/` | 308 para `/{slug}` (slug inválido ou reservado: 404) |
| `/{slug}/...` | 404 HTML (futuras páginas do site) |

- Só os dados que `GET /api/site/{slug}` já expõe (`LojaPublica`); a regra de visibilidade é a mesma
  (`app/services/site.py`, usada pelas duas).
- Cabeçalhos: `Content-Security-Policy: default-src 'none'; img-src 'self'; style-src 'unsafe-inline';
  base-uri 'none'; form-action 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, `Cache-Control: no-cache`. Sem JavaScript.
- `/{slug}` conta no mesmo limite por IP do site (`LIMITE_SITE_POR_IP`); passou: 429 HTML com
  `Retry-After`. Endereço inválido ou reservado responde 404 sem consultar o banco e sem contar.
- `/api` e `/api/...` nunca caem nessas rotas: o que não existe na API continua 404 em JSON.

### Slugs reservados (PLA-16)

`superadmin`, `api`, `painel`, `site`, `docs`, `redoc`, `openapi`, `admin`, `login`, `static`, `assets`,
`app`, `www`, `saude`, `health` não podem ser slug de loja (lista em `app/services/slugs.py`).
`POST /api/superadmin/lojas` e `PUT /api/superadmin/lojas/{id}`: 422 com
`erros: [{campo: "slug", mensagem: "Este endereço é reservado pelo sistema. Escolha outro."}]`. O banco
também recusa (`ck_lojas_slug_reservado`, migração 0005; a migração para se alguma loja, mesmo
excluída, já usar um desses endereços).

### Logo da loja

| Rota | Permissão | Entrada | Saída |
|---|---|---|---|
| `PUT /api/loja/configuracoes/loja/logo` | escrita em `config_loja` | `multipart/form-data`, campo **`arquivo`** | 200, os dados da loja (mesmo formato de `GET configuracoes/loja`) com o novo `logo_url` |
| `DELETE /api/loja/configuracoes/loja/logo` | escrita em `config_loja` | — | 204 (apaga o arquivo; sem logo também é 204) |
| `PUT /api/superadmin/lojas/{id}/logo` | superadmin | `multipart/form-data`, campo **`arquivo`** | 200, o detalhe da loja (`LojaDetalhe`) |
| `DELETE /api/superadmin/lojas/{id}/logo` | superadmin | — | 204 |
| `GET` (ou `HEAD`) `/api/arquivos/logos/{loja_id}/{nome}` | pública | — | a imagem, com `Content-Type` certo e cache longo (`immutable`); 404 "Arquivo não encontrado." se a loja não estiver ativa (suspensa, cancelada ou excluída) |

- `logo_url` é um caminho na mesma origem da API: `/api/arquivos/logos/<loja_id>/<32 hex>.<png|jpg|webp>`.
  Basta usá-lo no `src` da imagem (em desenvolvimento passa pelo proxy `/api` do Vite; com `VITE_API_URL`
  apontando para outra origem, prefixe com ela). O nome muda a cada envio, então o navegador nunca mostra a
  logo antiga do cache.
- Só **PNG, JPEG e WebP**, conferidos pelos bytes do arquivo (a extensão, o nome e o content-type enviados
  não contam). SVG, GIF ou qualquer outro: 422 "Formato não aceito. Envie uma imagem PNG, JPEG ou WebP.".
  Sem o campo `arquivo`: 422 com `erros: [{campo: "arquivo", mensagem: "Campo obrigatório."}]`.
- Até **2 MB** (`LOGO_TAMANHO_MAXIMO`): acima disso, 413 "A imagem deve ter no máximo 2 MB.". Corpo muito
  maior (em qualquer rota, acima do limite + 64 KB): 413 "O envio passou do tamanho máximo permitido.", sem
  ler o corpo inteiro (`LimiteDoCorpo`, em `app/limites.py`).
- Os arquivos ficam no disco em `ARQUIVOS_DIR` (padrão `backend/arquivos/`, fora do git; no Docker,
  `/app/arquivos`, que deve ser um volume). Nome aleatório gerado pelo servidor, uma pasta por loja. A logo
  anterior é apagada depois do commit; se a transação for desfeita, o arquivo novo é apagado e a anterior
  continua.
- Erros: 401 sem login, 403 sem escrita ("Você só tem permissão de leitura aqui."), 404 loja inexistente
  (superadmin) ou arquivo inexistente/nome inválido (rota pública), 413, 422.

### Integração com o front

O painel da loja e o SUPERADMIN já usam a API (camada `frontend/src/data/api/`). Convenções:

- **Ids** são uuid; os campos seguem o banco em `snake_case` (`preco_mensal`, `nome_fantasia`,
  `plano_id`...).
- **Datas e horas** de todas as rotas da loja (inclusive `criado_em`, `atualizado_em`, `ultimo_login_em`,
  movimentações, histórico e o `expira_em` do login) saem **no fuso da loja** (ex.: `-03:00`), nunca em UTC.
  O SUPERADMIN usa o fuso da loja no que é de uma loja e `America/Sao_Paulo` no que é da plataforma.
- **Lojas (SUPERADMIN):** lista paginada (`itens`, `total`); `GET lojas/opcoes` para os selects.
  `modulos` na criação é a lista de códigos. Funcionário usa `perfil_id` (de `GET lojas/{id}/perfis`),
  não o nome do perfil. Módulos via `PATCH` com só o campo alterado. `senha_provisoria` aparece quando
  vier (ainda não há envio de e-mail); **redefinir senha** troca a senha na hora.
- **Auditoria:** busca e filtro de pessoa no servidor (paginados); `mudancas` pronto (colunas do banco,
  ex.: `inicio` em vez de `data`/`hora`); a operação `restaurar` também aparece. O **login não aparece**
  no histórico (ver "Como o banco protege os dados").
- **Site:** loja suspensa responde 404; os horários vêm prontos de `GET horarios`; o pedido manda
  `funcionario_id`, `inicio` e opcionalmente `local_id` do horário escolhido.

Rotas e campos criados durante a integração:

- `GET apoio/filtros-agenda`: profissionais (`id`, `nome`, `cor_agenda`, `ativo`) e locais (`id`, `nome`,
  `tipo`, `ativo`; nulo sem o módulo Locais) para os filtros da agenda e da lista de agendamentos, com
  `so_propria`. Leitura na agenda basta; quem só tem Minha agenda recebe só ele mesmo.
- `GET servicos/opcoes`: profissionais, locais e materiais **ativos** para o formulário de serviço, sem
  exigir acesso a Funcionários, Locais ou Materiais (escrita em `servicos`; locais e materiais nulos com o
  módulo desligado).
- `GET ponto/funcionarios`: funcionários (`id`, `nome`, `cor_agenda`, `ativo`) para o Ponto da equipe,
  sem exigir acesso a Funcionários (leitura em `ponto_equipe`).
- `GET /api/site/{slug}/horarios?local_id=`: só horários com aquele local livre (422 "Local não
  encontrado para este serviço." se o local não atende o serviço).
- `GET inicio`: `equipe_em_servico` (quem está em serviço: `registro_id`, `funcionario_id`, `nome`,
  `cor_agenda`, `entrada`), além de `funcionarios_em_servico`.
- `GET apoio/agendamento`: `materiais` ativos (`id`, `nome`, `unidade`; nulo sem o módulo Materiais), para
  ajustar o que foi usado no atendimento. Os clientes vêm de `GET apoio/clientes`.
- `GET /api/superadmin/visao-geral`: `modulos_expirando` (módulos ligados em lojas ativas com prazo vencido
  ou vencendo em 30 dias: `loja_id`, `loja_nome`, `codigo`, `nome`, `expira_em` no fuso da loja, `vencido`).
- Logo: `PUT/DELETE configuracoes/loja/logo` e `PUT/DELETE /api/superadmin/lojas/{id}/logo` (ver "Logo da
  loja").

### Mudanças de contrato (integração)

- **Datas de controle no fuso da loja** (antes `criado_em`, `atualizado_em`, `ultimo_login_em`... saíam
  em UTC, com `Z`). O instante é o mesmo; só o offset muda. Quem converte qualquer offset para a hora da
  loja não precisa mudar nada.
- **`GET recursos`** traz `leitura` e `escrita` separados (o texto antigo continua em `descricao`).
- **`GET/PUT configuracoes/loja`** seguem o contrato do `Controle`: `criado_em`, `atualizado_em`,
  `atualizado_por` (uuid do funcionário ou `null`) e `atualizado_por_nome`. Alteração feita pelo superadmin
  (ou pelo sistema) vem com os dois nulos, como nas demais rotas da loja (GER-13). Antes vinha
  `atualizado_por` = `"funcionario"`/`"superadmin"` e o nome do superadmin.

### Mudanças de contrato (rodada 2 da revisão da integração)

- **`GET agendamentos?ordem=asc|desc`** (opcional, padrão `asc`): ordem pelo `inicio`. `desc` traz os mais
  recentes na página 1 (desempate pelo `id`, também decrescente). Outro valor: 422 com
  `erros: [{campo: "ordem", mensagem: "Opção inválida."}]`.
- **`GET apoio/clientes?busca=`** busca só por **nome/sobrenome e telefone** (com ou sem máscara). CPF e
  e-mail não casam mais (quem só agenda não descobre se um documento é cliente). `GET clientes` continua
  buscando também por CPF e e-mail.
- **Nascimento do cliente** (`POST/PUT clientes`): "no futuro" usa o dia de hoje **no fuso da loja**. 422
  com `erros: [{campo: "data_nascimento", mensagem: "Data de nascimento inválida (não pode ser no futuro
  nem antes de 1900)."}]`.
- **Logo** (`GET/HEAD /api/arquivos/logos/...`): 404 "Arquivo não encontrado." quando a loja está
  suspensa, cancelada ou excluída (sem dizer o motivo). O SUPERADMIN também não vê a logo dessas lojas.
- **Lojas (SUPERADMIN)**, `POST lojas` e `PUT lojas/{id}`: fuso que o Postgres não conhece dá 422 com
  `erros: [{campo: "fuso_horario", mensagem: "Fuso horário inválido (ex.: America/Sao_Paulo)."}]`.
- **Excluir serviço x marcar agendamento ao mesmo tempo:** um espera o outro. Ou a exclusão é recusada
  (409, já documentado), ou o agendamento recebe 422 "Serviço não encontrado.".

### Mudanças de contrato (correções da revisão de segurança)

Já aplicadas no front:

- **`GET apoio/agendamento` não traz mais `clientes`.** O formulário busca em
  `GET apoio/clientes?busca=<texto>&pagina=&por_pagina=` (mínimo de 2 caracteres; nome ou telefone,
  com ou sem máscara; não busca por CPF nem e-mail; só ativos) → `{itens: [{id, nome, sobrenome, telefone}], total, pagina, por_pagina}`.
  Termo curto: 422 "Digite pelo menos 2 caracteres para buscar.". Liberada para quem tem escrita na agenda.
- **`POST ponto/registrar` exige corpo** `{"acao": "entrada" | "saida", "funcionario_id"?: uuid}`. Ação que
  não bate com a situação atual: 409 "A entrada já foi registrada. Para encerrar, registre a saída." ou
  "Não há entrada em aberto. Registre a entrada primeiro.". `POST ponto` e `PUT ponto/{id}` com período
  sobreposto a outro registro do funcionário: 409 "Este funcionário já tem um registro de ponto nesse período.".
- **CPF e telefone** (clientes e funcionários; telefone também no suporte do superadmin) aceitam com ou
  sem máscara e saem sempre como `000.000.000-00` e `(11) 98888-1111`. CPF com dígito errado: 422
  "CPF inválido."; telefone sem DDD: 422 "Informe o telefone com DDD (ex.: (11) 99999-9999).". Nascimento
  no futuro ou antes de 1900: 422. A busca de `GET clientes` acha telefone e CPF com ou sem máscara.
- **Datas** informadas (filtros `inicio`/`fim`, `inicio` do agendamento, bloqueios, ponto, prazo de módulo,
  site) só entre 2000 e 2100: fora disso, 422 "Informe uma data entre 2000 e 2100.". `pagina` até 10.000.
- **Limites de tamanho:** textos livres (observações, descrição, justificativa, motivo...) até 2.000
  caracteres ("Texto muito longo (máximo de 2000 caracteres)."); listas (`funcionario_ids`, `local_ids`,
  `materiais`, `acessos`, `modulos`) até 200 itens ("Itens demais (máximo de 200).").
- **Estoque:** uma movimentação (e a quantidade inicial) até 1.000.000; se o saldo passaria de
  99.999.999,99: 422 "Com esta movimentação o estoque passaria do limite permitido (99.999.999,99).".
- **Perfis e funcionários (ACE-19), 403:** "Você não pode conceder um nível de acesso maior que o seu.",
  "Você não pode alterar o seu próprio perfil de acesso.", "Você não pode atribuir um perfil com acesso
  maior que o seu.", "Você não pode trocar o seu próprio perfil de acesso.", "Você não pode trocar a senha
  de quem tem acesso maior que o seu.". O Administrador não tem essas restrições, exceto trocar o próprio perfil.
- **Serviços:** serviço ativo sem nenhum profissional ativo: 422 "Selecione ao menos um profissional ativo
  que realiza o serviço.". Excluir serviço com agendamentos ativos de agora em diante: 409.
- **Login e site, 429** com header `Retry-After` (segundos): "Muitas requisições. Aguarde um pouco e tente
  novamente." ou, no login bloqueado (conta naquele IP), "Muitas tentativas de login. Aguarde N minuto(s) e
  tente novamente.".
- **Qualquer rota que grava, 409** "Outra alteração foi feita ao mesmo tempo e esta não foi salva. Tente
  novamente." quando duas transações disputam as mesmas linhas (raro; basta repetir).
- **Site, pedido:** 409 "Já há pedidos deste telefone aguardando a confirmação da loja. Aguarde a resposta
  antes de pedir outro horário.".

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

## Limite de requisições

`app/limites.py` (decisão provisória para ABE-23; sem captcha). Valores no `.env` (padrões em
`app/config.py`; janelas em segundos):

| Proteção | Variáveis | Padrão |
|---|---|---|
| Login (loja + superadmin) por IP | `LIMITE_LOGIN_POR_IP`, `LIMITE_LOGIN_JANELA` | 20 / 60 s |
| Bloqueio da conta **naquele IP** após falhas seguidas | `LOGIN_FALHAS_PARA_BLOQUEAR`, `LOGIN_FALHAS_JANELA` | 5 falhas em 1 h |
| Duração do bloqueio (dobra a cada nova falha) | `LOGIN_BLOQUEIO_INICIAL`, `LOGIN_BLOQUEIO_MAXIMO` | 60 s até 15 min |
| Site, todas as rotas, por IP | `LIMITE_SITE_POR_IP`, `LIMITE_SITE_JANELA` | 120 / 60 s |
| Site, pedidos por IP em cada loja | `LIMITE_SITE_PEDIDOS_POR_IP`, `LIMITE_SITE_PEDIDOS_JANELA` | 10 / 1 h |
| Site, pedidos aguardando aceite por telefone em cada loja | `SITE_PENDENTES_POR_TELEFONE` | 3 |

- O estado fica no Postgres (schema `limites`, migração 0003): vale para todos os processos e réplicas.
  Cada contador grava numa conexão própria em autocommit (conta mesmo quando a requisição falha). As chaves
  são HMAC do IP/e-mail com o `JWT_SECRET` (nada legível na tabela).
- O bloqueio é por **conta + IP**: só o IP que errou fica bloqueado para aquela conta (nem a senha certa
  entra por ele). O dono, de outro IP, entra normalmente, e as falhas de um terceiro não renovam o bloqueio
  de ninguém além dele; muitos IPs atacando a mesma conta esbarram no limite global por IP. Vale também
  para e-mail que não existe (a resposta não revela se a conta existe). Acertar a senha zera as falhas
  daquele IP.
- Deadlock ou falha de serialização no banco (SQLSTATE 40P01/40001) respondem 409 "Outra alteração foi
  feita ao mesmo tempo e esta não foi salva. Tente novamente." (nada foi gravado).
- **IP:** é o mesmo da auditoria (`request.client.host`). Atrás de um proxy reverso, rode o uvicorn com
  `--proxy-headers` e o IP do proxy em `FORWARDED_ALLOW_IPS` (o `Dockerfile` já faz isso, padrão
  `127.0.0.1`; ver "Docker" e [`deploy/README.md`](../deploy/README.md)); senão todos os clientes contam
  como o IP do proxy.

## Como o banco protege os dados

- **Dois usuários no Postgres.** O dono do schema (`DATABASE_OWNER_URL`) roda as migrações. A API
  usa `agenda_app` (`DATABASE_URL`), sem privilégio de dono: para ele valem o RLS e o `REVOKE` de
  `UPDATE`/`DELETE` na `auditoria`.
- **Contexto da transação.** Cada requisição é uma transação; no início, `app/db.py`
  (`definir_contexto`) grava `app.funcionario_id`, `app.superadmin_id`, `app.loja_id`, `app.origem`,
  `app.ip` e `app.login` com `set_config(..., true)`. Os triggers e o RLS leem esses valores.
- **Fuso da loja.** Com uma loja no contexto, o `TimeZone` da transação vira o `fuso_horario` da loja:
  toda data/hora lida do banco chega ao Python (e à resposta) no fuso da loja, sem conversão rota a
  rota. Sem loja (superadmin, rotinas), UTC. Volta sozinho ao fim da transação. Fuso que o Postgres
  não conhece (dado antigo, base de fusos atualizada) não derruba a requisição: vale `America/Sao_Paulo`
  e o problema vai para o log (`app.db`). O superadmin só grava fuso que o Python e o Postgres conhecem.
- **Login fora do histórico** (migração 0004). O login marca a transação (`app.login`); nela, o UPDATE
  que só muda `ultimo_login_em` e `senha_hash` (novo hash da mesma senha, quando o Argon2 pede) não
  troca `atualizado_em`/`atualizado_por` nem grava auditoria. Qualquer outra coluna alterada junto é
  tratada normalmente, e a troca de senha de verdade (edição, redefinição) continua auditada.
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

As logos enviadas ficam em `/app/arquivos` (`ARQUIVOS_DIR`): monte um volume persistente nesse caminho
(ex.: `docker run -v agenda-arquivos:/app/arquivos ...`), senão elas somem ao recriar o contêiner.

**Atrás do nginx** (produção, [`deploy/README.md`](../deploy/README.md)): a imagem roda o uvicorn com
`--proxy-headers`, então o IP do cliente (auditoria e limite de requisições) vem do `X-Forwarded-For`,
mas **só** quando a conexão chega de um IP listado em `FORWARDED_ALLOW_IPS` (variável lida pelo
próprio uvicorn; padrão `127.0.0.1`, o nginx na mesma máquina com `--network host`). Endereço e porta
do uvicorn: `UVICORN_HOST` (padrão `0.0.0.0`) e `UVICORN_PORT` (padrão `8000`). Nunca use
`FORWARDED_ALLOW_IPS=*` com a API exposta.
