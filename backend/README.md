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
| Acesso do cliente ao site | `GET clientes/codigos-site`, `GET/DELETE clientes/{id}/conta-site` (ver "Conta do cliente no site") | escrita em `clientes` |
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
| Configurações | `GET/PUT configuracoes/loja`, `PUT/DELETE configuracoes/loja/logo` (ver "Logo da loja"), `GET/PUT configuracoes/site` (ver "Cores do site"), `GET/PUT configuracoes/notificacoes`, `POST configuracoes/notificacoes/testar-email` (ver "Notificações") | `config_loja` |
| Notificações (sino) | `GET notificacoes`, `GET notificacoes/resumo`, `POST notificacoes/visualizar` (só as do próprio funcionário) | — (só login) |

Saúde: `GET /api/saude`. Arquivos públicos: `GET /api/arquivos/logos/{loja_id}/{nome}` (sem login).

### SUPERADMIN (`/api/superadmin/...`, só com token de superadmin)

| Área | Rotas |
|---|---|
| Acesso | `POST auth/login`, `GET eu` |
| Visão geral | `GET visao-geral` (lojas por situação e tipo, funcionários, receita, módulos, `modulos_expirando`, últimas ações) |
| Lojas | `GET/POST lojas`, `GET lojas/opcoes`, `GET/PUT/DELETE lojas/{id}`, `POST lojas/{id}/status`, `PUT/DELETE lojas/{id}/logo`, `GET/PUT lojas/{id}/site` (cores do site, como na loja) |
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
são os arquivos do build; `/api/...`, `/<slug>`, `/static/site/...` e o resto chegam aqui (nenhuma
mudança no nginx nem no Vite foi necessária). Jinja2 com autoescape, templates em `app/templates/`,
fora do OpenAPI, registradas depois de todos os routers `/api` e da documentação:

- `app/routers/paginas.py`: `/`, `/painel`, arquivos do site, `/{slug}/` e o 404 do resto;
- `app/routers/site/paginas.py`: o site do consumidor (SIT-12), com as regras de
  `app/services/agendamento_site.py` (as mesmas da API `/api/site/{slug}`);
- `app/routers/html.py`: ambiente Jinja, cabeçalhos, CSP e `RespostaPronta` (interrompe a página com
  um 404, 429 ou redirecionamento; tratador registrado em `app/main.py`).

| Rota | Resposta |
|---|---|
| `GET /` | 404 HTML "Página não encontrada" |
| `GET /painel`, `/painel/...` | 404 HTML com a orientação de usar `/nome-da-loja/painel` |
| `GET /{slug}` | Passo 1: serviços (sem o módulo Serviços, já o passo 2 do "Atendimento", SIT-08) |
| `GET /{slug}/agendar?servico=&profissional=&dia=` | Passo 2: profissional, faixa de 31 dias a partir de hoje (fuso da loja) e horários do dia |
| `GET /{slug}/agendar/dados?servico=&profissional=&inicio=&local=` | Passo 3: resumo e formulário (`inicio` = `AAAA-MM-DDTHH:MM±HH:MM`) |
| `POST /{slug}/agendar` | Envia o pedido (`application/x-www-form-urlencoded`); 303 para o passo 4 |
| `GET /{slug}/agendar/pronto?c=<código>` | Passo 4: confirmação (código assinado, 24 h, preso à loja) |
| `GET/POST /{slug}/conta/entrar`, `POST /{slug}/conta/sair`, `GET/POST /{slug}/conta/criar`, `.../conta/codigo?t=`, `.../conta/senha?v=`, `GET /{slug}/conta?pagina=` | Conta do cliente (ver "Conta do cliente no site") |
| `GET/POST /{slug}/conta/agendamentos/{id}/cancelar`, `GET .../remarcar?profissional=&dia=`, `GET/POST .../remarcar/confirmar?profissional=&inicio=&local=` | Cancelar e remarcar pela conta (SIT-23, SIT-24) |
| `GET /static/site/site.css`, `site.js` | CSS e JS do site (lista fechada; com `?v=<versão>` vai com cache de 1 ano) |
| `GET /{slug}/` | 308 para `/{slug}` (slug inválido ou reservado: 404) |
| `/{slug}/...` (outros) | 404 HTML |

Todas as páginas aceitam `GET` e `HEAD` (o envio, só `POST`). Loja inexistente, excluída, suspensa ou
cancelada, slug inválido ou reservado: 404 HTML "Loja não encontrada" em todas as páginas do fluxo.

- **Parâmetros:** lidos à mão, nunca 422 em JSON nem 500. Serviço ausente, inválido, inativo ou de
  outra loja: 303 para `/{slug}` (`?aviso=servico` quando veio um serviço). Profissional inválido no
  passo 2: mostra "qualquer profissional" com aviso. Dia fora da faixa: marca o primeiro dia com
  horários. Horário inválido: 303 ao passo 2 do dia (`aviso=horario`); horário que não está mais livre:
  303 ao passo 2 do dia com `aviso=ocupado`. `aviso` é um código com texto fixo (nada é refletido).
- **Envio:** `Origin`/`Referer` de outro host (ou `Origin: null`) = 403 HTML, nada gravado. Campo
  escondido `zx_conferencia` (`display: none`, nome que nenhum autopreenchimento reconhece) preenchido
  (robô) = 303 para uma confirmação genérica, nada gravado. O limite de pedidos por IP é conferido antes
  de tudo.
  Validação igual a `SolicitacaoEntrada`: erro = 200 com o formulário, os valores e as mensagens
  (resumo no topo). Limite de pedidos por IP (`LIMITE_SITE_PEDIDOS_*`) = 429 com o formulário; limite de
  pendentes por telefone = 409 com o formulário. O pedido roda num savepoint: a recusa do banco (corrida,
  23P01) volta ao passo 2 com `aviso=ocupado`. O mesmo formulário enviado de novo, inteiro válido e
  igual (telefone, profissional, início, nome, sobrenome e e-mail sem diferenciar maiúsculas,
  observações; cliente cadastrado por aquele pedido; pendente, últimos 10 min), leva à confirmação do
  pedido já gravado (LOG-07), inclusive quando o segundo envio simultâneo cai no limite de pendentes.
  Telefone de cliente que já era da loja nunca conta como repetição (SIT-07).
- **Confirmação:** mostra serviço, dia, hora, profissional, local (nome), preço e a situação; nada do
  cliente (nem o nome cadastrado, SIT-07). Código adulterado, expirado ou de outra loja: 404.
- **Cabeçalhos:** `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  same-origin`, `X-Frame-Options: DENY`. CSP do site: `default-src 'none'; img-src 'self'; style-src
  'self'; script-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` (sem estilo
  ou script embutido). Loja com cores próprias: `style-src 'self' 'nonce-<novo a cada resposta>'`, só
  para o `<style>` das cores (ver "Cores do site"); nunca `unsafe-inline`. Páginas de erro:
  `style-src 'unsafe-inline'`, `form-action 'none'`, sem script.
  `noindex` do passo 2 em diante (a página inicial da loja pode ser indexada).
- **Limites:** todas as páginas contam no limite por IP do site (`LIMITE_SITE_POR_IP`, o mesmo da API);
  passou: 429 HTML com `Retry-After`. Endereço inválido ou reservado responde 404 sem consultar o banco
  e sem contar.
- **Visual:** tokens por tipo de loja em `app/static/site/site.css` (`.tipo-clinica`, `.tipo-barbearia`,
  `.tipo-escola`, com versão escura), mobile first, e as cores escolhidas pela loja por cima (abaixo). Sem JavaScript tudo funciona; `site.js` só troca o
  profissional sem clicar em "Atualizar", rola a faixa até o dia marcado, desabilita o envio depois do
  clique e leva o foco ao resumo dos erros.
- `/api` e `/api/...` nunca caem nessas rotas: o que não existe na API continua 404 em JSON.

### Cores do site (SIT-13 a SIT-15, PLA-20)

`GET/PUT /api/loja/configuracoes/site` (leitura/escrita em `config_loja`) e
`GET/PUT /api/superadmin/lojas/{id}/site` (404 "Loja não encontrada." para inexistente ou excluída).
Entrada `{"cor_topo": "#RRGGBB" | null, "cor_destaque": "#RRGGBB" | null}` (as duas chaves
obrigatórias; `null` ou texto vazio = cor padrão do tipo; maiúsculas e espaços em volta aceitos, grava
`#rrggbb`). Saída: as duas cores, `padrao` (`{cor_topo, cor_destaque}` do tipo da loja), `tipo` e o
controle (`atualizado_por`/`_nome` = funcionário; nulos quando foi o superadmin, que fica na auditoria).

- Formato inválido: 422 no campo, "Informe a cor no formato #RRGGBB."; texto branco com contraste
  abaixo de 4,5:1 (WCAG): 422 no campo, "Cor muito clara: o texto branco fica difícil de ler. Escolha
  uma cor mais escura.". O banco tem o CHECK de formato (`ck_loja_configuracoes_cor_site_*`).
- Paleta padrão num lugar só: `app/services/cores_site.py` (`PALETAS`), com os mesmos valores do
  `site.css` (teste em `tests/test_cores_site.py`).
- Site: com alguma cor escolhida, as páginas do fluxo levam `<body class="tipo-x cores-da-loja">` e um
  `<style nonce>` com as variáveis (`--cor-topo`, `--cor-destaque`, `--cor-destaque-texto`,
  `--cor-destaque-suave`), reescritas a partir do hex validado. No modo escuro o topo continua o
  escolhido e o destaque é clareado (misturado com branco) até 4,5:1 sobre a superfície escura do
  tipo, com texto escuro. Sem cores escolhidas, HTML e CSP são os de sempre. A API pública
  (`/api/site/{slug}`) não muda.
- Por que nonce e não um CSS por loja: as páginas já são `no-store` (o nonce novo a cada resposta não
  custa cache), não abre outra rota pública com consulta ao banco nem uma requisição a mais por página,
  e a cor nova vale na hora (sem versão de arquivo para invalidar).

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

### Conta do cliente no site (SIT-16 a SIT-22, CLI-06)

Especificação: [`docs/funcionalidades/conta-cliente.md`](../docs/funcionalidades/conta-cliente.md)
(Fase A: conta, código, entrar, Minha conta, agendar com a conta e a seção do painel; Fase B: cancelar e
remarcar). Regras em `app/services/conta_cliente.py` e `app/services/conta_agendamentos.py`; páginas em
`app/routers/site/conta.py` e `app/routers/site/conta_agendamentos.py`; cookie e `voltar` em
`app/routers/site/sessao.py`. Tabelas `cliente_contas` e `cliente_codigos` (migração 0007).

- **Conta por telefone** (SIT-16): uma por (loja, telefone só com dígitos). Enxerga os agendamentos de
  todos os clientes da loja com aquele telefone (comparação por dígitos na hora: trocar o telefone de um
  cliente no painel muda de conta os agendamentos dele).
- **Criar conta e esqueci a senha** (SIT-17, SIT-18): `/conta/criar` (telefone) → `/conta/codigo?t=`
  (código de 6 dígitos, 15 min; com um pendente válido, pedir de novo devolve o mesmo, sem gerar
  outro nem invalidar; erros: 5 por código e IP, 20 no total) → `/conta/senha?v=`
  (senha; nome e sobrenome só se não houver cliente com o telefone, que é cadastrado com canal `site`).
  `t` e `v` são o id do código assinado (HMAC, preso à loja e ao passo, 15 min); `v` é de uso único (o
  código é consumido ao salvar a senha). Antes do código certo nenhuma página diz se o telefone tem
  cadastro ou conta. Envio do código por provedor trocável (`EnvioCodigo`); o atual, `painel`, só grava
  e a loja vê o código no painel.
- **Entrar** (SIT-19): telefone (com ou sem máscara) + senha; erro único "Telefone ou senha incorretos.";
  `limite_login` por IP e bloqueio progressivo `BloqueioLogin('site', slug, telefone)` por IP (429 com o
  formulário). Senha de 8 a 128 caracteres, diferente do telefone (Argon2). Entrar grava
  `ultimo_acesso_em` fora do histórico (como o login do painel).
- **Sessão** (SIT-20): cookie `sessao_cliente`, `HttpOnly`, `SameSite=Lax`, `Path=/{slug}`, `Secure`
  fora de `AMBIENTE=desenvolvimento`, validade `SITE_SESSAO_DIAS` (30). O valor é um JWT do tipo
  `cliente` (conta, loja, versão) assinado com uma chave derivada do `JWT_SECRET` e audiência própria:
  nunca vale nas rotas `/api/loja` e `/api/superadmin` (401), e um token do painel nunca vale como
  sessão. Trocar a senha ou o painel remover o acesso incrementa `sessao_versao` e derruba todas as
  sessões. Cookie que não vale mais: a página que exige conta manda para `/conta/entrar?aviso=sessao` e
  apaga o cookie.
- **Minha conta** (SIT-21): "Próximos" (`pendente`/`agendado`/`confirmado` que não terminaram, até 50)
  e "Histórico" (20 por página, `?pagina=`). Serviço (ou "Atendimento"), dia, hora, profissional, local
  (só o nome), preço e situação; nunca o motivo de cancelamento/recusa. Sem sessão: 303 para
  `/conta/entrar?voltar=...`.
- **Agendar com a conta** (SIT-22): o passo 3 só pede Observações ("Agendando como <nome>") e leva o
  campo oculto `conta=1`; o pedido usa o telefone da conta e o cliente mais antigo com ele, com os mesmos
  limites. Sessão vencida no envio: volta ao passo 3 completo com aviso. Sem conta: o fluxo de sempre,
  com "Já tem conta? Entrar" voltando ao mesmo passo; o passo 4 convida a criar a senha (ou, na conta,
  "Ver meus agendamentos"). O cabeçalho de todas as páginas da loja mostra "Entrar" ou "Minha conta".
- **Cancelar e remarcar** (SIT-23, SIT-24, AGE-25): nos "Próximos" de Minha conta, "Remarcar" e
  "Cancelar" aparecem enquanto o agendamento está `pendente`/`agendado`/`confirmado` e falta pelo menos
  a antecedência da loja (CFG-05, `loja_configuracoes.antecedencia_cliente_minutos`, padrão 120 min); depois
  disso, "Para alterar, fale com a loja: <telefone>".
  Páginas em `/{slug}/conta/agendamentos/{id}/...`, todas com sessão (sem ela, 303 para entrar voltando à
  mesma página). Agendamento de outro telefone, de outra loja, de cliente excluído, inexistente ou
  excluído: 404. Situação final ou fora do prazo da loja: 409 "Este agendamento não pode mais ser alterado pelo
  site. Fale com a loja: <telefone>.". Os `POST` travam a linha (`FOR UPDATE`, a mesma trava do painel) e
  conferem dono, situação e prazo de novo.
  - **Cancelar:** `GET` mostra o resumo e "Cancelar este agendamento?"; `POST` vira `cancelado` na hora
    (sem aceite), motivo "Cancelado pelo cliente pelo site.", 303 para `/conta?aviso=cancelado`. O mesmo
    envio de novo (já cancelado pelo site) volta a Minha conta sem alterar nada.
  - **Remarcar:** a escolha é o passo 2 (`escolha_de_horario` de `app/routers/site/paginas.py`, faixa de
    31 dias, filtro de profissional) com a duração atual (`fim - inicio`) e o próprio agendamento fora da
    ocupação (`Agenda(..., ignorar=id)`, `dias_livres`/`horario_oferecido(..., duracao=, ignorar=)`). A
    confirmação mostra "De … Para …"; o `POST` muda profissional, início, fim e local (escolhido pelo
    servidor como no pedido; sem o módulo Locais, o local sai) e volta a `pendente`, mantendo serviço e
    preço; 303 para `/conta?aviso=remarcado`. Horário que não é mais oferecido, local ocupado ou corrida
    recusada pelo banco (23P01, num savepoint): 303 de volta à escolha com `aviso=ocupado`; parâmetro
    ilegível, profissional que não faz o serviço ou local de outro serviço: `aviso=horario`; o mesmo
    horário de agora (mesmo profissional e início): `aviso=mesmo`. Com o módulo Serviços, serviço inativo
    ou removido, ninguém ativo habilitado ou nenhum local possível: 409 "Para remarcar este horário, fale
    com a loja: <telefone>." com o link para cancelar. Sem o módulo Serviços: os profissionais do SIT-08.
  - **AGE-25:** `agendado`/`confirmado` → `pendente` e `pendente` → `pendente` só por aqui
    (`TRANSICOES_DO_CLIENTE`); o `TRANSICOES` do painel não muda (o painel continua sem voltar nada a
    `pendente`). Auditoria com origem `site` e `atualizado_por` NULL.
- **Travas e conflitos:** tudo que mexe em códigos ou na conta de um telefone trava primeiro o telefone
  (advisory lock) e só depois as linhas (`FOR UPDATE`); o Argon2 é calculado antes das travas. Erro de
  banco numa página HTML (ex.: impasse 40P01) responde a página de erro em HTML (`app/erros.py`), nunca
  JSON. Telefone, código, página e datas da URL só aceitam dígitos ASCII (0-9).
- **Segurança das páginas:** todo `POST` confere `mesma_origem` (403 HTML); `voltar` só aceita páginas
  do próprio site (regex fechada: `/{slug}`, `/agendar[/dados|/pronto]`, `/conta` e as páginas da Fase
  B; nunca `//`, esquema, barra invertida, outro slug nem as páginas de entrar/criar); `noindex`;
  limite por IP do site; loja indisponível = 404. DIR-003: nenhum template fala em painel ou login.
- **Painel** (CLI-06, escrita em `clientes`; leitura = 403 "Você só tem permissão de leitura aqui."):
  - `GET /api/loja/clientes/codigos-site` → `[{telefone, codigo, expira_em, criado_em, clientes:
    [{id, nome}]}]`: códigos pendentes, mais novo primeiro, até 100; `clientes` = cadastros com o
    telefone (`nome` = nome + sobrenome; vazia sem cadastro).
  - `GET /api/loja/clientes/{id}/conta-site` → `{possui_conta, criada_em, ultimo_acesso_em,
    codigo_pendente: {codigo, expira_em} | null}` pelo telefone atual do cliente.
  - `DELETE /api/loja/clientes/{id}/conta-site` → 204 (exclusão lógica da conta, versão +1, códigos do
    telefone invalidados). 404 "Cliente não encontrado." (outra loja, inexistente ou excluído) ou
    "Este cliente não tem acesso ao site.".
- **Auditoria:** `senha_hash` e `cliente_codigos.codigo` nunca vão para `antes`/`depois`.

### Notificações (NOT-01 a NOT-08, CFG-05, CFG-06, SIT-25)

Especificação: [`docs/funcionalidades/notificacoes.md`](../docs/funcionalidades/notificacoes.md). Tabela
`notificacoes` e colunas novas de `loja_configuracoes` (migração 0008). Regras em
`app/services/notificacoes.py` (criação, sino do painel, lembretes), `app/services/tarefa_notificacoes.py`
(ciclo da tarefa), `app/services/envio_email.py` (SMTP), `app/services/config_notificacoes.py` e
`app/services/avisos_conta.py` (sino do site).

- **Criação** na mesma transação do fato (se a mudança não grava, o aviso também não), com o texto
  congelado e horas no padrão do painel ("ter 14/10 às 9h30", fuso da loja). Cliente: `pedido_recebido`
  (pedido ou remarcação pelo site), `agendamento_criado` (painel), `confirmado`, `cancelado` (loja cancelou
  ou recusou; nunca o motivo), `horario_alterado` (loja mudou início, profissional ou local de um
  agendamento não final), `lembrete`. Loja (**só o profissional do agendamento**, se ativo): `novo_pedido`,
  `remarcacao_pedida`, `cancelado_pelo_cliente`. Concluir, não compareceu e reabrir não avisam.
- **Canais:** `status_site` 1/2; `status_email`/`status_whatsapp` 1 pendente, 2 enviado, 3 erro, 4 dado
  faltando. Sem e-mail no cadastro = 4; loja sem SMTP ativo = 3 ("O envio de e-mail da loja não está
  configurado."); WhatsApp sempre 4. O status só avança (trigger `notificacoes_status_avanca`).
- **Sino do painel** (qualquer funcionário logado, só as suas, sem recurso de acesso):
  `GET notificacoes?pagina=&por_pagina=` (máx. 50) → `{itens, total, pagina, por_pagina, nao_visualizadas}`,
  `GET notificacoes/resumo` → `{nao_visualizadas}`, `POST notificacoes/visualizar` `{ids: [1..100]}` →
  `{marcadas, nao_visualizadas}` (ids alheios ignorados; no acesso de suporte do SUPERADMIN nada é marcado).
- **Configurações › Avisos e e-mail** (`config_loja`): `GET/PUT configuracoes/notificacoes`
  (`antecedencia_cliente_minutos` 0..10080 e `email` {ativo, servidor, porta 25/465/587/2525, seguranca
  ssl/starttls, usuario, senha, remetente_email, remetente_nome}; `senha` ausente = mantém, `null` = apaga;
  a saída traz só `senha_definida`) e `POST configuracoes/notificacoes/testar-email` `{destino}` →
  `{enviado: true}` ou `{enviado: false, erro}` (409 sem SMTP ativo; 429 depois de 5 em 10 min por loja). A
  senha é cifrada com `CHAVE_CIFRA` (Fernet) e mascarada na auditoria; sem a chave, 422 em `email.senha`.
  Em `AMBIENTE=producao` o servidor precisa resolver só para endereços públicos (422 "Servidor não
  permitido."), conferido de novo na hora de conectar (a conexão vai para o IP conferido).
- **Tarefa de fundo** (`app/tarefas.py`, no `lifespan` da API; `NOTIFICACOES_TAREFA`, `NOTIFICACOES_INTERVALO`
  = 30 s): cria os lembretes (um por agendamento `agendado`/`confirmado` e início, quando faltar a
  antecedência da loja; 0 = sem lembrete) e envia os e-mails pendentes. Descobre as lojas com trabalho pela
  função `notificacoes_lojas_com_trabalho` (SECURITY DEFINER, só ids de lojas **ativas**; `EXECUTE` só para o
  papel da aplicação, não PUBLIC) e atende até 4 lojas em paralelo, cada uma com o contexto dela (origem
  `sistema`). Reserva com `FOR UPDATE SKIP LOCKED` (tentativa + 1 e `email_proxima_tentativa_em` = relógio
  **da hora da reserva** + 5 min, mais que o pior caso de uma loja), envia fora da transação e grava o
  resultado só se a linha ainda tiver a mesma reserva (tentativa e data): 2; falha temporária volta a 1 com
  espera de 1 e 5 min; na 3ª falha (ou falha definitiva: usuário/senha, remetente, destinatário ou servidor
  recusados, endereço com acento sem SMTPUTF8) fica 3 com a mensagem tratada. Cada envio tem **prazo total
  de 15 s** em todas as fases (DNS numa thread com espera limitada; o socket TCP é registrado antes do TLS e o
  TLS antes do handshake, e o vigia derruba todos com `shutdown` quando o prazo acaba; cada comando confere o
  prazo e lê com o tempo que sobrou; vale também para o "testar e-mail"); a primeira falha de conexão
  interrompe o lote da loja e cada loja tem 60 s de envio por ciclo: o que não foi tentado volta à fila sem
  gastar tentativa. O ciclo espera as lojas no máximo 20 s: a atrasada continua no pool fixo de 4 threads e
  fica fora dos ciclos seguintes até terminar; as outras seguem. Antes de enviar, encerra com 3 o lembrete cujo agendamento mudou (não está mais
  `agendado`/`confirmado`, outro início, excluído ou já começou: "Aviso vencido: o agendamento mudou.") e o
  aviso com mais de 24 h ou de agendamento que já começou ("Aviso vencido."). Vários processos ao mesmo tempo
  são seguros. Fora da API: `uv run python -m scripts.notificacoes [--uma-vez]`.
- **E-mail:** texto simples, remetente da loja, assunto "<título> · <loja>"; ao cliente, com `URL_PUBLICA`,
  o link `URL_PUBLICA/<slug>/conta` (nunca o painel, DIR-003). Nos testes (`AMBIENTE=teste`) o provedor é
  o falso (`EnvioFalso`), nada sai para a rede.
- **Site** (SIT-25): com sessão, o cabeçalho mostra "Avisos" com a contagem (`aria-label="Avisos, N não
  lidos"`; no celular só o sino e o número). `GET /{slug}/conta/avisos?pagina=` lista os avisos dos
  clientes do telefone da conta (20 por página), destaca os novos desta abertura ("Novo") e os marca como
  visualizados depois de montar a página (um `HEAD` não marca). Página estranha: a primeira.
- **Trocar servidor ou usuário do SMTP** com senha salva exige mandar `senha` de novo (422 em `email.senha`:
  "Informe a senha de novo ao trocar o servidor ou o usuário."): a senha salva nunca vai para outra conta.
  A consulta ao DNS do servidor (produção) só acontece para quem tem escrita em `config_loja` (conferida
  numa sessão curta, já fechada) e antes de abrir a transação da requisição.

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
| Site, entrar na conta do cliente | os valores do login por IP (`LIMITE_LOGIN_*`), num contador próprio (esgotar o do site não afeta o painel e vice-versa), e bloqueio por telefone + IP | acima |
| Site, pedidos de código: intervalo por telefone e IP (em cada loja) | `LIMITE_CODIGO_INTERVALO` | 1 a cada 60 s |
| Site, códigos **gerados** por telefone (em cada loja; pedido com um pendente válido devolve o mesmo e não conta) | `LIMITE_CODIGOS_POR_TELEFONE`, `LIMITE_CODIGOS_POR_TELEFONE_JANELA` | 5 / 1 h |
| Site, pedidos de código por IP | `LIMITE_CODIGOS_POR_IP`, `LIMITE_CODIGOS_POR_IP_JANELA` | 10 / 1 h |
| Site, erros no mesmo código por IP (o código segue valendo para os outros IPs; 20 erros no total esgotam o código) | `LIMITE_CODIGO_TENTATIVAS_POR_IP` | 5 |
| Site, validade da sessão do cliente (cookie) | `SITE_SESSAO_DIAS` | 30 dias |

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
- **Login fora do histórico** (migração 0004; 0007 inclui `ultimo_acesso_em` da conta do cliente). O
  login marca a transação (`app.login`); nela, o UPDATE que só muda `ultimo_login_em`
  (`ultimo_acesso_em`) e `senha_hash` (novo hash da mesma senha, quando o Argon2 pede) não
  troca `atualizado_em`/`atualizado_por` nem grava auditoria. Qualquer outra coluna alterada junto é
  tratada normalmente, e a troca de senha de verdade (edição, redefinição) continua auditada.
- **Triggers em todas as tabelas** (`migrations/auxiliares.py`): preenchem `criado_em`,
  `atualizado_em`, `atualizado_por`, `excluido_em` e `excluido_por`; convertem `DELETE` em
  exclusão lógica; gravam a `auditoria` (inserir, alterar, excluir, restaurar, sem `senha_hash` nem
  `cliente_codigos.codigo`).
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
