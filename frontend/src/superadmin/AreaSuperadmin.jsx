import { Outlet } from 'react-router-dom'
import { SessaoSuperadminProvider } from '../data/sessao/sessoes.js'

// Raiz de /superadmin: a sessão do superadmin vale para o login e para o painel da plataforma
export default function AreaSuperadmin() {
  return (
    <SessaoSuperadminProvider>
      <Outlet />
    </SessaoSuperadminProvider>
  )
}
