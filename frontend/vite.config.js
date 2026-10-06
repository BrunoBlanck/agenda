import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Mapa de URLs (GER-29), o mesmo do nginx de produção (deploy/nginx/agenda.conf):
//   /_app/...                               arquivos do front (base do Vite)
//   /superadmin, /superadmin/...            SPA (index.html)
//   /{slug}/painel, /{slug}/painel/...      SPA (index.html)
//   /api/... e todo o resto (/, /{slug})    back-end (API, site da loja, 404)
// Em dev (`npm run dev`) e no preview do build (`npm run preview`) o Vite imita o nginx num endereço só.
const BASE = '/_app/'
// /api/painel nunca é o painel (no nginx, `location ^~ /api/` vem antes do regex do painel)
const DA_API = /^\/api(?:\/|$)/
// Mesmo regex do nginx: slug no formato do sistema (minúsculas, números e hífens)
const DO_APP = /^\/(?:superadmin|[a-z0-9]+(?:-[a-z0-9]+)*\/painel)(?:\/|$)/

const caminhoDe = (url = '/') => url.split('?')[0]

// Endereço do SPA: entrega o index.html do app sem redirecionar (o navegador continua no endereço original)
function rotasDoApp(middlewares) {
  middlewares.use((req, _res, next) => {
    const caminho = caminhoDe(req.url)
    if ((req.method === 'GET' || req.method === 'HEAD') && !DA_API.test(caminho) && DO_APP.test(caminho)) {
      req.url = `${BASE}index.html`
    }
    next()
  })
}

const imitarNginx = () => ({
  name: 'imitar-nginx',
  // Sem devolver função: o middleware entra antes do proxy e dos internos do Vite
  configureServer: (server) => rotasDoApp(server.middlewares),
  configurePreviewServer: (server) => rotasDoApp(server.middlewares),
})

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Tudo o que não é /_app/ (e não foi reescrito para o index.html acima) vai para o back-end.
  // changeOrigin false: o back-end recebe o Host do navegador, como atrás do nginx (Host $host).
  const proxy = {
    [`^/(?!${BASE.slice(1, -1)}(?:/|$))`]: { target: env.API_PROXY_ALVO || 'http://localhost:8000', changeOrigin: false },
  }
  // Porta do `npm run dev` e do `npm run preview` (PORTA_DEV no .env.local; padrão 5173)
  const port = Number(env.PORTA_DEV) || 5173
  return {
    base: BASE,
    // Sem o fallback de SPA do Vite: só os endereços do app (acima) recebem o index.html; um arquivo que
    // não existe em /_app/ dá 404, como no nginx
    appType: 'mpa',
    plugins: [react(), imitarNginx()],
    server: { proxy, port, strictPort: true },
    preview: { proxy, port, strictPort: true },
    build: {
      rolldownOptions: {
        output: {
          // React e o roteador mudam pouco: num pedaço próprio, ficam em cache entre as versões do sistema
          codeSplitting: {
            groups: [{ name: 'react', test: /node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/ }],
          },
        },
      },
    },
  }
})
