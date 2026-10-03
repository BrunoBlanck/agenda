# Deploy (produção)

Um servidor Linux (ex.: Oracle Cloud, x86 ou ARM) com **nginx** na frente de dois serviços:

| Caminho | Quem responde |
|---|---|
| `/_app/...` | arquivos do build do front (`/var/www/agenda`), cache longo |
| `/superadmin`, `/superadmin/...` | SPA do front (`index.html`) |
| `/<slug>/painel`, `/<slug>/painel/...` | SPA do front (`index.html`) |
| `/api/...` | API (uvicorn em `127.0.0.1:8000`) |
| `/<slug>` e todo o resto | back-end: página da loja, 404 de `/` e `/painel` |

O mesmo mapa vale em desenvolvimento (o Vite em `localhost:5173` imita o nginx). A configuração do
nginx está em [`nginx/agenda.conf`](nginx/agenda.conf).

## 1. Banco e API

1. PostgreSQL 16 (gerenciado ou no próprio servidor). Crie o banco e o usuário dono do schema.
2. Configure as variáveis de ambiente do back-end como no [`backend/.env.example`](../backend/.env.example):
   `AMBIENTE=producao`, `DATABASE_OWNER_URL`, `DATABASE_URL`, `JWT_SECRET` (aleatório, longo),
   `CORS_ORIGENS` (o endereço público, ex.: `["https://agenda.exemplo.com"]`), `ARQUIVOS_DIR`.
3. Prepare o banco (uma vez, e a cada versão nova para as migrações):

   ```bash
   cd backend
   uv sync --frozen --no-dev
   uv run python -m scripts.criar_papel_app
   uv run alembic upgrade head
   ```

4. Suba a API **só no endereço local** (o nginx é a única porta de entrada). Duas opções:

   **a) Docker** (imagem do `backend/Dockerfile`, já com `--proxy-headers`):

   ```bash
   docker build -t agenda-backend backend/
   docker run -d --name agenda-api --restart unless-stopped --network host \
     --env-file /etc/agenda/backend.env \
     -e UVICORN_HOST=127.0.0.1 -e UVICORN_PORT=8000 -e FORWARDED_ALLOW_IPS=127.0.0.1 \
     -v agenda-arquivos:/app/arquivos \
     agenda-backend
   ```

   Com `--network host` o nginx do servidor fala com a API por `127.0.0.1` e o padrão
   `FORWARDED_ALLOW_IPS=127.0.0.1` já serve. Se preferir publicar a porta
   (`-p 127.0.0.1:8000:8000`, sem `--network host`), a conexão chega ao contêiner vinda do gateway
   da rede do Docker (ex.: `172.17.0.1`): use `-e UVICORN_HOST=0.0.0.0` e
   `-e FORWARDED_ALLOW_IPS=172.17.0.1` (confira com `docker network inspect bridge`).

   **b) Direto no servidor** (systemd), a partir de `backend/`:

   ```bash
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
   ```

   (`FORWARDED_ALLOW_IPS` sem valor = `127.0.0.1,::1`, que é o nginx na mesma máquina.)

### Por que `--proxy-headers` e `FORWARDED_ALLOW_IPS`

A auditoria e o limite de requisições (login e site) usam o IP do cliente. Atrás do nginx, a conexão
que chega ao uvicorn é do próprio nginx; com `--proxy-headers`, o uvicorn passa a usar o
`X-Forwarded-For` e o `X-Forwarded-Proto` **somente** quando a conexão vem de um IP listado em
`FORWARDED_ALLOW_IPS` (separados por vírgula). O nginx **sobrescreve** o `X-Forwarded-For` com o IP
de quem se conectou, então o cliente não consegue forjar o próprio IP.

- `FORWARDED_ALLOW_IPS` errado (IP do proxy fora da lista): todos os clientes viram o IP do nginx e
  dividem o mesmo limite de requisições (o site e o login passam a dar 429 para todo mundo).
- Nunca use `FORWARDED_ALLOW_IPS=*` com a API exposta: qualquer um forjaria o IP.
- Confira: faça uma requisição pelo endereço público e veja o IP no log de acesso do uvicorn
  (`docker logs agenda-api`) ou na auditoria do SUPERADMIN. Deve ser o seu IP, não `127.0.0.1`.

## 2. Front-end

O build usa `base: '/_app/'` (`frontend/vite.config.js`), então o `index.html` aponta para
`/_app/assets/...`.

```bash
cd frontend
npm ci
npm run build
sudo mkdir -p /var/www/agenda
sudo rsync -a --delete dist/ /var/www/agenda/
```

Os arquivos de `assets/` têm hash no nome e ficam em cache por 1 ano (`immutable`); os demais arquivos
de `/_app/` (favicon e outros de `public/`, sem hash) ficam com cache de 1 hora; o `index.html` é servido
sempre com `Cache-Control: no-cache`, então uma versão nova aparece no próximo carregamento.

## 3. nginx

```bash
sudo apt install nginx            # ou dnf install nginx
sudo cp deploy/nginx/agenda.conf /etc/nginx/conf.d/agenda.conf
sudo rm -f /etc/nginx/sites-enabled/default   # o agenda.conf já é o default_server da porta 80
sudo nginx -t && sudo systemctl reload nginx
```

Para validar a configuração sem instalar o nginx (ex.: no Windows, com Docker):

```bash
docker run --rm -v "$PWD/deploy/nginx:/etc/nginx/conf.d:ro" nginx:stable-alpine nginx -t
```

Libere a porta 80 (e 443, quando houver HTTPS) no firewall do servidor e na lista de segurança da
nuvem. A porta 8000 **não** deve ficar aberta.

### Conferir o roteamento

```bash
curl -I http://SEU_IP/superadmin                 # 200, index.html do front (no-cache)
curl -I http://SEU_IP/clinica-sorriso/painel     # 200, index.html do front
curl -I http://SEU_IP/clinica-sorriso            # 200, página da loja (back-end, com CSP)
curl -I http://SEU_IP/                           # 404 do back-end (HTML)
curl    http://SEU_IP/api/saude                  # {"status":"ok"}
```

## 4. HTTPS (próximo passo)

Com um domínio apontando para o servidor:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d agenda.exemplo.com
```

O certbot acrescenta o `listen 443 ssl` e o redirecionamento de HTTP para HTTPS no `agenda.conf`.
O `X-Forwarded-Proto` passa a ser `https` sozinho (`$scheme`). Atualize `CORS_ORIGENS` para o
endereço `https://` e reinicie a API.

## Atualizar uma versão

1. `git pull` no servidor.
2. Back-end: `uv run alembic upgrade head` e reinicie a API (ou `docker build` + recriar o contêiner).
3. Front-end: `npm ci && npm run build` e o `rsync` acima.
4. Mudou o `agenda.conf`? `sudo nginx -t && sudo systemctl reload nginx`.
