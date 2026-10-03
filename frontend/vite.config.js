import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      // Em desenvolvimento a API fica atrás do próprio Vite (/api): mesma origem, sem CORS
      proxy: {
        '/api': { target: env.API_PROXY_ALVO || 'http://localhost:8000', changeOrigin: true },
      },
    },
    build: {
      rolldownOptions: {
        output: {
          // React e o roteador mudam pouco: num pedaço próprio, ficam em cache entre as versões do sistema
          codeSplitting: {
            groups: [{ name: 'react', test: /node_modules[\/](react|react-dom|scheduler|react-router|react-router-dom)[\/]/ }],
          },
        },
      },
    },
  }
})
