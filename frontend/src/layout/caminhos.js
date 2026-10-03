import { useParams } from 'react-router-dom'

// Único lugar que sabe montar o endereço do painel da loja (GER-29): /{slug}/painel/...
// O slug da URL só identifica a loja para o front (rota, login, sessão); a API usa o token (GER-05).

/** '/clinica-sorriso/painel' + resto ('/agenda', '/login', '' para o início). */
export const caminhoPainel = (slug, resto = '') => `/${slug}/painel${resto}`

/** Site do consumidor da loja (página do back-end, fora da SPA). */
export const caminhoSite = (slug) => `/${slug}`

/** Slug da URL atual, em minúsculas ('' fora de /:slug/painel). */
export function useSlugLoja() {
  const { slug } = useParams()
  return (slug ?? '').toLowerCase()
}

/** Função que monta caminhos do painel da loja da URL: caminho('/agenda') => '/clinica-sorriso/painel/agenda'. */
export function usePainelPath() {
  const slug = useSlugLoja()
  return (resto = '') => caminhoPainel(slug, resto)
}
