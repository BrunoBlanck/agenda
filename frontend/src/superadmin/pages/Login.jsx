import { ConfigProvider } from 'antd'
import { Navigate, useLocation } from 'react-router-dom'
import TelaLogin from '../../layout/TelaLogin.jsx'
import { useSessaoSuperadmin } from '../../data/sessao/sessoes.js'
import { temaPlataforma } from '../../tema.js'

// Login do superadmin (equipe da plataforma)
export default function Login() {
  const sessao = useSessaoSuperadmin()
  const { state } = useLocation()

  if (sessao.estado === 'logado') return <Navigate to={state?.de ?? '/superadmin'} replace />

  return (
    <ConfigProvider theme={temaPlataforma}>
      <TelaLogin
        area="Plataforma (SUPERADMIN)"
        titulo="Entrar"
        descricao="Acesso restrito à equipe da plataforma."
        motivo={sessao.motivo}
        aoEntrar={sessao.entrar}
      />
    </ConfigProvider>
  )
}
