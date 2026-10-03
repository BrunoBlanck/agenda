import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import CarregandoPagina from './components/base/CarregandoPagina.jsx'

// Cada área (e cada tela) em um pedaço próprio: quem usa o painel da loja não baixa o SUPERADMIN, e vice-versa
const SiteLoja = lazy(() => import('./site/SiteLoja.jsx'))
const AreaLoja = lazy(() => import('./layout/AreaLoja.jsx'))
const AppLayout = lazy(() => import('./layout/AppLayout.jsx'))
const Login = lazy(() => import('./pages/Login.jsx'))
const Dashboard = lazy(() => import('./pages/Dashboard.jsx'))
const Agenda = lazy(() => import('./pages/Agenda.jsx'))
const Agendamentos = lazy(() => import('./pages/Agendamentos.jsx'))
const Clientes = lazy(() => import('./pages/Clientes.jsx'))
const Funcionarios = lazy(() => import('./pages/Funcionarios.jsx'))
const Servicos = lazy(() => import('./pages/Servicos.jsx'))
const Locais = lazy(() => import('./pages/Locais.jsx'))
const Materiais = lazy(() => import('./pages/Materiais.jsx'))
const ControleTempo = lazy(() => import('./pages/ControleTempo.jsx'))
const ConfigLoja = lazy(() => import('./pages/ConfigLoja.jsx'))
const PerfisAcesso = lazy(() => import('./pages/PerfisAcesso.jsx'))
const AreaSuperadmin = lazy(() => import('./superadmin/AreaSuperadmin.jsx'))
const LoginSuperadmin = lazy(() => import('./superadmin/pages/Login.jsx'))
const SuperadminLayout = lazy(() => import('./superadmin/SuperadminLayout.jsx'))
const VisaoGeral = lazy(() => import('./superadmin/pages/VisaoGeral.jsx'))
const Lojas = lazy(() => import('./superadmin/pages/Lojas.jsx'))
const LojaDetalhe = lazy(() => import('./superadmin/pages/LojaDetalhe.jsx'))
const Planos = lazy(() => import('./superadmin/pages/Planos.jsx'))
const Usuarios = lazy(() => import('./superadmin/pages/Usuarios.jsx'))
const Auditoria = lazy(() => import('./superadmin/pages/Auditoria.jsx'))

export default function App() {
  return (
    // As telas têm o próprio carregamento dentro do layout; este só cobre a primeira carga da área
    <Suspense
      fallback={
        <div className="carregando-area">
          <CarregandoPagina />
        </div>
      }
    >
      <Routes>
        <Route index element={<Navigate to="/painel" replace />} />
        {/* Protótipo do site do consumidor final (será renderizado pelo back-end) */}
        <Route path="site/:slug" element={<SiteLoja />} />
        <Route path="painel" element={<AreaLoja />}>
          <Route path="login" element={<Login />} />
          <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="agenda" element={<Agenda />} />
          <Route path="agendamentos" element={<Agendamentos />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="funcionarios" element={<Funcionarios />} />
          <Route path="servicos" element={<Servicos />} />
          <Route path="locais" element={<Locais />} />
          <Route path="materiais" element={<Materiais />} />
          <Route path="controle-tempo" element={<ControleTempo />} />
          <Route path="configuracoes/loja" element={<ConfigLoja />} />
          {/* Horários e bloqueios agora ficam dentro dos perfis */}
          <Route path="configuracoes/agendamentos" element={<Navigate to="/painel/configuracoes/perfis" replace />} />
          <Route path="configuracoes/perfis" element={<PerfisAcesso />} />
          </Route>
        </Route>
        <Route path="superadmin" element={<AreaSuperadmin />}>
          <Route path="login" element={<LoginSuperadmin />} />
          <Route element={<SuperadminLayout />}>
          <Route index element={<VisaoGeral />} />
          <Route path="lojas" element={<Lojas />} />
          <Route path="lojas/:id" element={<LojaDetalhe />} />
          <Route path="planos" element={<Planos />} />
          <Route path="usuarios" element={<Usuarios />} />
          <Route path="auditoria" element={<Auditoria />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/painel" replace />} />
      </Routes>
    </Suspense>
  )
}
