import { api, urlDaApi } from './cliente.js'

// Site do consumidor (público, sem token): /api/site/{slug}/...
// Loja inexistente, suspensa ou cancelada responde 404 (SIT-01). Hoje o front só usa os dados públicos da
// loja no cabeçalho do login do painel; o site em si é página do back-end (SIT-11).

/**
 * GET /api/site/{slug}: nome e logo públicos da loja.
 * nome_fantasia já vem preenchido com o nome da loja quando ela não tem nome fantasia; logo_url pode ser null.
 */
export const buscarLojaPublica = (slug, sinal) =>
  api.site.get(`/${encodeURIComponent(slug ?? '')}`, { sinal }).then((d) => ({
    nome: (typeof d?.nome_fantasia === 'string' && d.nome_fantasia.trim()) || d?.nome || null,
    logoUrl: urlDaApi(d?.logo_url),
  }))
