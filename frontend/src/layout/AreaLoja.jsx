import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { SessaoLojaProvider } from '../data/sessao/sessoes.js'
import { slugValido } from '../utils/formatos.js'
import { useSlugLoja } from './caminhos.js'
import NaoEncontrada from './NaoEncontrada.jsx'

// Raiz de /:slug/painel: a sessão do funcionário (uma por loja) vale para o login e para o painel
export default function AreaLoja() {
  const { slug: slugDaUrl } = useParams()
  const slug = useSlugLoja()
  const { pathname, search, hash } = useLocation()

  if (!slugValido(slug)) return <NaoEncontrada />
  // Endereço com maiúsculas: troca pelo mesmo endereço em minúsculas (menu e sessão comparam o slug exato)
  if (slugDaUrl !== slug) {
    return <Navigate replace to={`${pathname.replace(/^\/[^/]+/, `/${slug}`)}${search}${hash}`} />
  }

  return (
    // key: trocar de loja na mesma aba começa uma sessão nova, sem estado da anterior
    <SessaoLojaProvider key={slug} slug={slug}>
      <Outlet />
    </SessaoLojaProvider>
  )
}
