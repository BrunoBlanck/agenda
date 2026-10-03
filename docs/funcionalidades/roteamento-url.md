# Roteamento por URL (loja no endereço) e deploy com nginx

- **Slug:** roteamento-url · **Branch:** feat/roteamento-url · **Status:** aprovada
- **Área:** painel da loja · SUPERADMIN · site do consumidor · infraestrutura
- **Pedido original:** cada loja identificada pela URL: `IP/<loja>` abre o site do cliente, `IP/<loja>/painel` abre o painel da loja sem precisar digitar a loja, `IP/superadmin` abre o superadmin. Em produção um nginx roteia: tudo que for `superadmin` ou tiver `/painel` vai para o build do front, o resto para o back-end. Funcionar igual em dev e em prod.

## 1. Objetivo
O funcionário entra no painel pelo endereço da própria loja (`/clinica-sorriso/painel`) e só digita e-mail e senha. O consumidor abre `/clinica-sorriso`. O superadmin abre `/superadmin`. O mesmo mapa de URLs vale em dev (Vite) e em produção (nginx na frente do build e da API).

## 2. Regras de negócio
| Código | Regra | Onde é garantida |
|---|---|---|
| GER-29 (nova) | Mapa de URLs: `/{slug}` e `/{slug}/...` (menos `painel`) = site do consumidor (back-end); `/{slug}/painel` e `/{slug}/painel/...` = painel da loja (SPA); `/superadmin` e `/superadmin/...` = SUPERADMIN (SPA); `/api/...` = API; `/_app/...` = arquivos do build do front; `/` e o resto = back-end (404) | nginx (`deploy/nginx`) + Vite dev/preview (`vite.config.js`) + rotas do React + rotas HTML do back-end |
| PLA-16 (nova) | Slugs reservados (não podem ser slug de loja): `superadmin`, `api`, `painel`, `site`, `docs`, `redoc`, `openapi`, `admin`, `login`, `static`, `assets`, `app`, `www`, `saude`, `health` | validação do schema (422) + CHECK no banco |
| SIT-11 (nova, provisória) | Até o site real do back-end existir, `GET /{slug}` devolve uma página HTML simples com nome, logo e contato da loja e "Agendamento online em breve". Loja inexistente/excluída/suspensa/cancelada: página 404 (mesma regra do SIT-01) | rota HTML do back-end |
| GER-05 | O `loja_id` continua vindo **só do token**. O slug da URL do painel serve para o front (rota, login, chave da sessão), nunca para escolher a loja na API | front + API (sem mudança na API da loja) |
| ACE-02 | Login do painel identifica a loja pelo slug: agora o slug vem da URL, não de um campo | tela de login |
| SIT-01 | Site: loja inexistente, excluída, suspensa ou cancelada = 404 | rota HTML e `/api/site` |

**Diretrizes aplicáveis:** `DIR-001` (painel lateral, só se alguma tela nova abrir registro — não deve abrir), `DIR-002` (identidade visual: tela de login e páginas "não encontrada" do painel usam só tokens).

Acesso: nenhuma mudança de permissão. Módulos: nenhum efeito.

## 3. Banco
- Migração Alembic nova: `CHECK (slug NOT IN (<lista do PLA-16>))` em `lojas` (nome `ck_lojas_slug_reservado`). Antes de criar, a migração confere se alguma loja (inclusive excluída) usa um slug reservado; se usar, falha com mensagem clara dizendo qual loja trocar (não renomeia sozinha).
- A lista de reservados fica num lugar só no código Python (ex.: `app/schemas/comum.py` ou `app/services/slugs.py`) e a migração usa a lista literal (migração não importa código da aplicação).

## 4. Contrato da API

### API JSON
**Nenhuma rota JSON nova nem alterada**, exceto a validação do slug:

- `POST /api/superadmin/lojas` e `PUT /api/superadmin/lojas/{id}` (campo `slug`): slug reservado → **422**, `erros: [{campo: "slug", mensagem: "Este endereço é reservado pelo sistema. Escolha outro."}]`.
- `POST /api/loja/auth/login` continua recebendo `slug` no corpo (o front passa a mandar o slug da URL). Sem mudança.
- `GET /api/site/{slug}` continua igual; a tela de login do painel passa a usá-lo para mostrar nome e logo da loja.

### Rotas HTML do back-end (novas, fora de `/api`)
Registradas **depois** de todos os routers `/api` (e de `/docs`/`/openapi.json` em dev), para não capturar nada deles. Respostas `text/html; charset=utf-8`, renderizadas com Jinja2 (autoescape ligado), templates em `backend/app/templates/`. Sem JS. CSS inline pequeno. Cabeçalhos: `Content-Security-Policy` restritiva (`default-src 'none'; img-src 'self'; style-src 'unsafe-inline'`; ajustar se usar a fonte do Google), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`. Sem rate limit novo além do que já existe para o site (pode reutilizar `limite_site`).

| Rota | Resposta |
|---|---|
| `GET /` | 404 HTML "Página não encontrada" (sem revelar lojas, sem link para o superadmin) |
| `GET /painel` e `GET /painel/{resto:path}` | 404 HTML com orientação: "Acesse o painel pelo endereço da sua loja, por exemplo `/nome-da-loja/painel`." |
| `GET /{slug}` | slug válido, não reservado, loja ativa → 200 página provisória (SIT-11): logo (se houver, `logo_url`), `nome_fantasia` ou `nome`, telefone/WhatsApp/e-mail/endereço se públicos (os mesmos campos que `LojaPublica` já expõe), texto "Agendamento online em breve". Caso contrário → 404 HTML "Loja não encontrada" |
| `GET /{slug}/` | 308 para `/{slug}` |
| `GET /{slug}/{resto:path}` (resto ≠ `painel...`) | 404 HTML (futuras páginas do site) |
| `HEAD` das mesmas | igual ao GET sem corpo |

O handler de 404 HTML só vale para essas rotas; erros em `/api/...` continuam JSON como hoje.

### Infra (back-end é dono)
- `deploy/nginx/agenda.conf`: server block de produção (ver seção 5.3 para as regras exatas).
- `deploy/README.md`: passo a passo do deploy (build do front copiado para `/var/www/agenda`, API em `127.0.0.1:8000`, `FORWARDED_ALLOW_IPS`, reload do nginx, HTTPS futuro com certbot).
- `backend/Dockerfile`: uvicorn com `--proxy-headers`; IPs confiáveis por `FORWARDED_ALLOW_IPS` (variável que o uvicorn já lê; padrão `127.0.0.1`). Documentar em `backend/.env.example`/README.

## 5. Contrato de tela

### 5.1 Rotas do React (`frontend/src/App.jsx`)
```
/:slug/painel            → AreaLoja (SessaoLojaProvider por slug)
/:slug/painel/login      → Login (sem campo "Endereço da loja")
/:slug/painel/agenda ... → mesmas telas de hoje, só com o prefixo /:slug
/:slug/painel/configuracoes/agendamentos → redireciona para /:slug/painel/configuracoes/perfis
/superadmin/...          → sem mudança
*                        → tela "Página não encontrada" (componente base EstadoVazio, tokens), sem redirecionar
```
- `site/:slug` e a pasta `frontend/src/site/` (protótipo) **saem**; `frontend/src/data/api/site.js` fica só com o que a tela de login usar (`buscarLojaPublica`) — o resto sai junto com o protótipo. O site passa a ser do back-end (SIT-11); o protótipo fica no histórico do git como referência.
- `index` (`/`) não existe mais no React (em dev/prod `/` vai para o back-end).
- `slug` da URL é normalizado para minúsculas; se não casar com `^[a-z0-9]+(?:-[a-z0-9]+)*$`, mostra "Página não encontrada".

### 5.2 Telas alteradas
- **Todas as navegações do painel** (`navegacao.jsx`, `AppLayout.jsx`, `Dashboard.jsx`, `Login.jsx`, `ExigirSessao`, redirects) passam a montar o caminho com o slug. Criar um helper único (ex.: `usePainelPath()` → `(resto) => '/' + slug + '/painel' + resto`) em `frontend/src/layout/` e usar em todo lugar; nenhum `'/painel...'` literal sobra. O menu destaca o item ativo com as mesmas chaves já prefixadas.
- **Login da loja** (`pages/Login.jsx` + `layout/TelaLogin.jsx`): remove o campo do slug e a lembrança `agenda.ultimaLoja`. Mostra no topo o nome (e a logo, se houver) da loja vindos de `useLojaPublica(slug)`. Carregando: o cabeçalho mostra o slug enquanto carrega (sem travar o formulário). Erro/404: mostra o slug como nome e **mantém o formulário** (loja suspensa também dá 404 no endpoint público, e o login é que diz o motivo certo).
- **Botão "Site da loja"** em `AppLayout.jsx`: `<a href={'/' + slug} target="_blank" rel="noopener">` (link de página inteira, não rota do React).
- **SUPERADMIN, detalhe da loja** (`superadmin/pages/LojaDetalhe.jsx`): dois links no cabeçalho/dados gerais: "Abrir painel" → `/{slug}/painel` e "Abrir site" → `/{slug}`, ambos `<a target="_blank" rel="noopener">`. Na lista de lojas, o slug pode aparecer como texto `/{slug}` (opcional, se couber sem poluir).
- **Formulário de loja no SUPERADMIN**: o erro 422 de slug reservado aparece no campo slug (já é o tratamento padrão de `erros[]`). Texto de ajuda do campo passa a dizer "Endereço: /<slug> (site) e /<slug>/painel (painel)".

### 5.3 Servidor de dev e nginx (frontend-dev: Vite; backend: nginx)
Vite (`frontend/vite.config.js`):
- `base: '/_app/'` (build e dev). Os arquivos do build passam a ser servidos em `/_app/...`; `_app` nunca é slug (o regex do slug não aceita `_`).
- **Dev e preview imitam o nginx** num endereço só (`localhost:5173`):
  - `/_app/...` → Vite;
  - `/superadmin`, `/superadmin/...`, `/{slug}/painel`, `/{slug}/painel/...` → `index.html` do app (plugin com middleware que reescreve a URL para o index; o endereço no navegador continua o original);
  - **todo o resto** (inclui `/api`, `/`, `/{slug}`) → proxy para `API_PROXY_ALVO` (padrão `http://localhost:8000`).
- Resultado: em dev tudo funciona em `http://localhost:5173` igual a produção; a API continua acessível direto em `:8000` se precisar.
- `BrowserRouter` sem `basename` (as rotas ficam na raiz; o `base` só muda o endereço dos arquivos).

nginx (`deploy/nginx/agenda.conf`, mesma regra):
```nginx
location ^~ /_app/ { alias /var/www/agenda/; expires 1y; add_header Cache-Control "public, immutable"; }   # index.html não fica aqui com cache
location = /superadmin                    { root /var/www/agenda; try_files /index.html =404; add_header Cache-Control "no-cache"; }
location ^~ /superadmin/                  { root /var/www/agenda; try_files /index.html =404; add_header Cache-Control "no-cache"; }
location ~ ^/[a-z0-9]+(-[a-z0-9]+)*/painel(/|$) { root /var/www/agenda; try_files /index.html =404; add_header Cache-Control "no-cache"; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; X-Real-IP; X-Forwarded-For $remote_addr (sobrescreve, não acrescenta); X-Forwarded-Proto $scheme; }
```
Mais: `client_max_body_size 3m`, `server_tokens off`, gzip para js/css/json/html, cabeçalhos `X-Content-Type-Options nosniff`, `Referrer-Policy same-origin`, `X-Frame-Options DENY` nas rotas do app. Cuidado: `add_header` dentro de `location` anula os do `server` — repetir onde precisar (ou `include` de um snippet).

### 5.4 Hooks de dados
| Hook | Retorna | Ações |
|---|---|---|
| `useSlugLoja()` (em `frontend/src/layout/` ou `data/`) | `string` (slug da URL, minúsculo) | — |
| `useLojaPublica(slug)` (em `frontend/src/data/`) | `{ loja: { nome, logoUrl } \| null, carregando, erro }` | — |
| `useSessaoLoja()` | igual hoje | `entrar({ email, senha })` — **sem `slug`**; a sessão já sabe o slug |

| Tela | API (`GET /api/site/{slug}`) | Tipo | Null |
|---|---|---|---|
| `nome` | `nome_fantasia` ou `nome` | string | não |
| `logoUrl` | `logo_url` (via `urlDaApi`) | string | sim |

Sessão por loja (frontend-dev): `SessaoLojaProvider` recebe o slug; token guardado com chave `agenda.sessao.loja.<slug>` (sessionStorage), então duas lojas em abas diferentes não se misturam. Depois de `GET /api/loja/eu`, se `eu.loja.slug` ≠ slug da URL → limpa o token dessa chave e vai para o login dessa URL. Ao sair, limpa só a chave daquela loja. A chave antiga `agenda.sessao.loja` e `agenda.ultimaLoja` são ignoradas/removidas.

### Estados obrigatórios
- Login: carregando dados públicos (mostra o slug), loja com logo, sem logo, nome longo (quebra sem estourar), endpoint público com erro/404 (formulário continua).
- Rota inexistente no React: "Página não encontrada" com link para nada externo (só texto), nos tokens.
- Sessão de outra loja: volta ao login da loja da URL.

## 6. Critérios de aceite
- [ ] `http://localhost:5173/clinica-sorriso/painel` sem sessão abre o login com o nome da loja; entra só com e-mail e senha; cai no início do painel em `/clinica-sorriso/painel`.
- [ ] Todos os itens do menu, botões do início e redirects ficam debaixo de `/clinica-sorriso/painel/...`; F5 em qualquer tela do painel recarrega a mesma tela (dev e build).
- [ ] Logado na loja A, abrir `/loja-b/painel` em outra aba pede login da loja B; a aba da loja A continua logada na A.
- [ ] Token da loja A colocado à mão na chave da loja B → após `/eu`, a sessão é limpa e vai para o login da B.
- [ ] `http://localhost:5173/clinica-sorriso` (dev, via proxy) e `http://localhost:8000/clinica-sorriso` mostram a página provisória da loja; loja suspensa ou inexistente → 404 HTML.
- [ ] `/`, `/painel`, `/clinica-sorriso/xyz` → 404 HTML do back-end; `/painel` traz a orientação.
- [ ] `/superadmin` funciona como hoje; detalhe da loja tem "Abrir painel" e "Abrir site" com os endereços certos.
- [ ] Criar/editar loja com slug `superadmin`, `api`, `painel` etc. → 422 no campo slug; o CHECK do banco também recusa (teste).
- [ ] `npm run build` gera `index.html` referenciando `/_app/assets/...`; `npm run preview` segue as mesmas regras do dev.
- [ ] `deploy/nginx/agenda.conf` passa em `nginx -t` (se houver nginx/docker disponível para testar; senão, revisão manual) e implementa exatamente a seção 5.3.
- [ ] Atrás do proxy, `ip_da_requisicao` enxerga o IP do cliente (uvicorn com `--proxy-headers` e `FORWARDED_ALLOW_IPS`), documentado.
- [ ] Nenhum `'/painel'` literal sobra no front fora do helper; nenhum `/site/` do protótipo sobra.
- [ ] Testes do back-end: rotas HTML (200, 404, 308, reservado, loja suspensa, não captura `/api/...` nem `/docs`), slug reservado (422 e CHECK). `pytest`, lint e build do front passando.

## 7. Fora do escopo
- O site do consumidor de verdade (modelos por tipo de loja, fluxo de agendamento em HTML). Próxima funcionalidade.
- HTTPS/domínio (o `deploy/README.md` só indica o caminho com certbot).
- Subdomínio por loja (`loja.dominio.com`).

## 8. Decisões e perguntas
Decisões tomadas pelo coordenador (o usuário pediu para implementar sem responder às perguntas da discussão; foram usadas as recomendações):
- `/{slug}` = página provisória do back-end (SIT-11); o protótipo React do site sai.
- `/` = 404 simples (não expõe o superadmin).
- `/painel` sem slug = 404 com orientação.
- Dev em um endereço só (Vite imitando o nginx), em vez de dois — mais próximo de produção.
- **Slug reservado no front (divergência do frontend-ui):** o React casaria `/superadmin/painel` com `:slug/painel`. `slugValido` (`frontend/src/utils/formatos.js`) passa a recusar também a lista do PLA-16 (cópia, com comentário apontando para a lista do back-end) → "Página não encontrada".
- **nginx:** `location ^~ /api/` explícito para o proxy, para que `/api/painel` nunca case com o regex do painel.
- **Rota `*` dentro das áreas:** aceito o "não encontrada" também dentro do painel e do SUPERADMIN (mantém o menu).
- Branch criada a partir de `chore/agentes-fluxo-trabalho` (e não da `main`), porque a `main` ainda não tem o commit "Comunicação entre frontend e backend implementada".

## 9. Histórico de revisão
- **2026-10-03 · rodada 1 · APROVADO.** pytest 667 ok, ruff ok, lint/build do front ok, `nginx -t` ok, nginx e Vite (dev/preview) testados de ponta a ponta, sessão por loja testada no navegador. Antes da revisão o coordenador pediu ao backend cache longo só em `/_app/assets/`. Sugestões não aplicadas: S1 `Cache-Control immutable` também no 404 de `/_app/assets/` (`always`); S2 padrão `UVICORN_HOST=0.0.0.0` na imagem; S3 proxy do Vite repassa `X-Forwarded-For` do cliente em dev; S4 endereço com maiúsculas dá 404 (redirect em `AreaLoja` nunca roda); S5 página provisória fora da identidade visual; S6 erro 500/405 em JSON nas rotas HTML.
