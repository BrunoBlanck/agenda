import { Routes, Route } from 'react-router-dom'
import AppLayout from './layout/AppLayout.jsx'
import SiteLoja from './site/SiteLoja.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Agenda from './pages/Agenda.jsx'
import Agendamentos from './pages/Agendamentos.jsx'
import Clientes from './pages/Clientes.jsx'
import Funcionarios from './pages/Funcionarios.jsx'
import Servicos from './pages/Servicos.jsx'
import Locais from './pages/Locais.jsx'
import Materiais from './pages/Materiais.jsx'
import ControleTempo from './pages/ControleTempo.jsx'
import ConfigLoja from './pages/ConfigLoja.jsx'
import ConfigAgendamentos from './pages/ConfigAgendamentos.jsx'
import PerfisAcesso from './pages/PerfisAcesso.jsx'
import SuperadminLayout from './superadmin/SuperadminLayout.jsx'
import VisaoGeral from './superadmin/pages/VisaoGeral.jsx'
import Lojas from './superadmin/pages/Lojas.jsx'
import LojaDetalhe from './superadmin/pages/LojaDetalhe.jsx'
import Tipos from './superadmin/pages/Tipos.jsx'
import Planos from './superadmin/pages/Planos.jsx'
import Catalogo from './superadmin/pages/Catalogo.jsx'
import Usuarios from './superadmin/pages/Usuarios.jsx'
import Auditoria from './superadmin/pages/Auditoria.jsx'

export default function App() {
  return (
    <Routes>
      {/* Site do consumidor final (exemplo) */}
      <Route index element={<SiteLoja />} />
      {/* Painel da loja */}
      <Route path="painel" element={<AppLayout />}>
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
        <Route path="configuracoes/agendamentos" element={<ConfigAgendamentos />} />
        <Route path="configuracoes/perfis" element={<PerfisAcesso />} />
      </Route>
      {/* Prévia do painel SUPERADMIN (ainda sem login) */}
      <Route path="superadmin" element={<SuperadminLayout />}>
        <Route index element={<VisaoGeral />} />
        <Route path="lojas" element={<Lojas />} />
        <Route path="lojas/:id" element={<LojaDetalhe />} />
        <Route path="tipos" element={<Tipos />} />
        <Route path="planos" element={<Planos />} />
        <Route path="catalogo" element={<Catalogo />} />
        <Route path="usuarios" element={<Usuarios />} />
        <Route path="auditoria" element={<Auditoria />} />
      </Route>
    </Routes>
  )
}
