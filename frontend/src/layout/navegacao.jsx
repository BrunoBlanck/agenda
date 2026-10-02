import {
  DashboardOutlined,
  CalendarOutlined,
  ScheduleOutlined,
  UserOutlined,
  TeamOutlined,
  MedicineBoxOutlined,
  FieldTimeOutlined,
  ExperimentOutlined,
  SettingOutlined,
  ShopOutlined,
  ClockCircleOutlined,
  SafetyOutlined,
} from '@ant-design/icons'

// Itens do menu do painel da loja (/painel/...) e a regra de acesso de cada tela (recebe o retorno de useAcesso)
const verAgenda = (a) => a.pode('agenda_propria') || a.pode('agenda_equipe')

export const menu = [
  { key: '/painel', icon: <DashboardOutlined />, label: 'Início', permitido: () => true },
  { key: '/painel/agenda', icon: <CalendarOutlined />, label: 'Agenda', permitido: verAgenda },
  { key: '/painel/agendamentos', icon: <ScheduleOutlined />, label: 'Agendamentos', permitido: verAgenda },
  { key: '/painel/clientes', icon: <UserOutlined />, label: 'Clientes', permitido: (a) => a.pode('clientes') },
  { key: '/painel/funcionarios', icon: <TeamOutlined />, label: 'Funcionários', permitido: (a) => a.pode('funcionarios') },
  { key: '/painel/servicos', icon: <ExperimentOutlined />, label: 'Serviços', permitido: (a) => a.pode('servicos') },
  { key: '/painel/materiais', icon: <MedicineBoxOutlined />, label: 'Materiais', permitido: (a) => a.pode('materiais') },
  {
    key: '/painel/controle-tempo',
    icon: <FieldTimeOutlined />,
    label: 'Controle de Tempo',
    permitido: (a) => a.pode('ponto_proprio') || a.pode('ponto_equipe'),
  },
  {
    key: '/painel/configuracoes',
    icon: <SettingOutlined />,
    label: 'Configurações',
    children: [
      { key: '/painel/configuracoes/loja', icon: <ShopOutlined />, label: 'Dados da loja', permitido: (a) => a.pode('config_loja') },
      {
        key: '/painel/configuracoes/agendamentos',
        icon: <ClockCircleOutlined />,
        label: 'Horários e bloqueios',
        permitido: (a) => a.pode('config_agendamentos'),
      },
      {
        key: '/painel/configuracoes/perfis',
        icon: <SafetyOutlined />,
        label: 'Perfis de acesso',
        permitido: (a) => a.pode('perfis_acesso'),
      },
    ],
  },
]

const telas = menu.flatMap((i) => i.children ?? [i])

export const telaDaRota = (pathname) => telas.find((t) => t.key === pathname)

// Menu sem os itens que o usuário não pode ver; grupo vazio também some
export function menuPermitido(acesso) {
  const item = ({ key, icon, label }) => ({ key, icon, label })
  return menu.flatMap((i) => {
    if (!i.children) return i.permitido(acesso) ? [item(i)] : []
    const filhos = i.children.filter((c) => c.permitido(acesso)).map(item)
    return filhos.length ? [{ ...item(i), children: filhos }] : []
  })
}
