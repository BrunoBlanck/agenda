import { Outlet } from 'react-router-dom'
import { SessaoLojaProvider } from '../data/sessao/sessoes.js'

// Raiz de /painel: a sessão do funcionário vale para o login e para o painel
export default function AreaLoja() {
  return (
    <SessaoLojaProvider>
      <Outlet />
    </SessaoLojaProvider>
  )
}
