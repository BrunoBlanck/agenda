import { Routes, Route } from 'react-router-dom'
import AppLayout from './layout/AppLayout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Agenda from './pages/Agenda.jsx'
import Agendamentos from './pages/Agendamentos.jsx'
import Clientes from './pages/Clientes.jsx'
import Funcionarios from './pages/Funcionarios.jsx'
import Servicos from './pages/Servicos.jsx'
import Materiais from './pages/Materiais.jsx'
import ControleTempo from './pages/ControleTempo.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="agenda" element={<Agenda />} />
        <Route path="agendamentos" element={<Agendamentos />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="funcionarios" element={<Funcionarios />} />
        <Route path="servicos" element={<Servicos />} />
        <Route path="materiais" element={<Materiais />} />
        <Route path="controle-tempo" element={<ControleTempo />} />
      </Route>
    </Routes>
  )
}
