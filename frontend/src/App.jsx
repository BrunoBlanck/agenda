import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import CarregandoPagina from './components/base/CarregandoPagina.jsx'
import { usePainelPath } from './layout/caminhos.js'

// Cada área (e cada tela) em um pedaço próprio: quem usa o painel da loja não baixa o SUPERADMIN, e vice-versa
const AreaLoja = lazy(() => import('./layout/AreaLoja.jsx'))
const NaoEncontrada = lazy(() => import('./layout/NaoEncontrada.jsx'))
const AppLayout = lazy(() => import('./layout/AppLayout.jsx'))
const Login = lazy(() => import('./pages/Login.jsx'))
const AcessoSuporte = lazy(() => import('./pages/AcessoSuporte.jsx'))
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

// Redirecionamento dentro do painel da loja da URL (/:slug/painel + resto)
function IrNoPainel({ resto }) {
  const caminho = usePainelPath()
  return <Navigate to={caminho(resto)} replace />
}

function NaoEncontradaNoPainel() {
  const caminho = usePainelPath()
  return <NaoEncontrada inicio={caminho()} />
}

// Mapa de URLs (GER-29): /:slug/painel = painel da loja, /superadmin = plataforma. O resto (/, /:slug do site,
// /api) é do back-end; se chegar aqui, é "Página não encontrada", sem redirecionar.
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
        <Route path=":slug/painel" element={<AreaLoja />}>
          <Route path="login" element={<Login />} />
          {/* Entrada do "Acessar loja" do SUPERADMIN (token entregue no sessionStorage da aba): fora do layout, como o login */}
          <Route path="suporte" element={<AcessoSuporte />} />
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
          <Route path="configuracoes/agendamentos" element={<IrNoPainel resto="/configuracoes/perfis" />} />
          <Route path="configuracoes/perfis" element={<PerfisAcesso />} />
          <Route path="*" element={<NaoEncontradaNoPainel />} />
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
          <Route path="*" element={<NaoEncontrada inicio="/superadmin" />} />
          </Route>
        </Route>
        <Route path="*" element={<NaoEncontrada />} />
      </Routes>
    </Suspense>
  )
}
