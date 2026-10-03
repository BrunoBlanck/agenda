# Front-end (painel da loja e SUPERADMIN)

React 19 + Vite + Ant Design 6. Como rodar, rotas e estrutura: [`README.md`](../README.md) da raiz.

- A API precisa estar no ar ([`backend/README.md`](../backend/README.md)). Em desenvolvimento, `/api` é
  encaminhado pelo Vite para `API_PROXY_ALVO` (padrão `http://localhost:8000`); em produção, defina
  `VITE_API_URL` (ver `.env.example`).
- Integração com a API: skill [`integracao-api`](../.claude/skills/integracao-api/SKILL.md) e `src/data/api/`.
- `npm run dev`, `npm run build`, `npm run lint`.
