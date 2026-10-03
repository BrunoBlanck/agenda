import {
  HomeOutlined,
  CalendarOutlined,
  ScheduleOutlined,
  UserOutlined,
  TeamOutlined,
  InboxOutlined,
  FieldTimeOutlined,
  TagsOutlined,
  SettingOutlined,
  ShopOutlined,
  SafetyOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons'
import { rotulosLocal } from '../data/locais.js'

// Itens do menu do painel da loja e a regra de acesso de cada tela (recebe o retorno de useAcesso).
// rota: o que vem depois de /{slug}/painel (o endereço completo sai de usePainelPath, em caminhos.js).
// labelDe(loja): nome da tela definido pela loja, no lugar de label
const verAgenda = (a) => a.pode('agenda_propria') || a.pode('agenda_equipe')

export const menu = [
  { rota: '', icon: <HomeOutlined />, label: 'Início', permitido: () => true },
  { rota: '/agenda', icon: <CalendarOutlined />, label: 'Agenda', permitido: verAgenda },
  { rota: '/agendamentos', icon: <ScheduleOutlined />, label: 'Agendamentos', permitido: verAgenda },
  { rota: '/clientes', icon: <UserOutlined />, label: 'Clientes', permitido: (a) => a.pode('clientes') },
  { rota: '/funcionarios', icon: <TeamOutlined />, label: 'Funcionários', permitido: (a) => a.pode('funcionarios') },
  { rota: '/servicos', icon: <TagsOutlined />, label: 'Serviços', permitido: (a) => a.pode('servicos') },
  {
    rota: '/locais',
    icon: <EnvironmentOutlined />,
    label: 'Locais',
    labelDe: (loja) => rotulosLocal(loja).plural,
    permitido: (a) => a.pode('locais'),
  },
  { rota: '/materiais', icon: <InboxOutlined />, label: 'Materiais', permitido: (a) => a.pode('materiais') },
  {
    rota: '/controle-tempo',
    icon: <FieldTimeOutlined />,
    label: 'Controle de tempo',
    permitido: (a) => a.pode('ponto_proprio') || a.pode('ponto_equipe'),
  },
  {
    rota: '/configuracoes',
    icon: <SettingOutlined />,
    label: 'Configurações',
    children: [
      { rota: '/configuracoes/loja', icon: <ShopOutlined />, label: 'Dados da loja', permitido: (a) => a.pode('config_loja') },
      // Perfis reúnem níveis de acesso, jornada semanal e bloqueios
      {
        rota: '/configuracoes/perfis',
        icon: <SafetyOutlined />,
        label: 'Perfis e horários',
        permitido: (a) => a.pode('perfis_acesso') || a.pode('config_agendamentos'),
      },
    ],
  },
]

const telas = menu.flatMap((i) => i.children ?? [i])

/** Tela do menu no endereço atual. caminho: retorno de usePainelPath. */
export const telaDaRota = (pathname, caminho) => telas.find((t) => caminho(t.rota) === pathname)

export const nomeDaTela = (tela, loja) => tela?.labelDe?.(loja) ?? tela?.label

// Menu sem os itens que o usuário não pode ver; grupo vazio também some. A chave de cada item é o endereço completo.
export function menuPermitido(acesso, loja, caminho) {
  const item = (i) => ({ key: caminho(i.rota), icon: i.icon, label: nomeDaTela(i, loja) })
  return menu.flatMap((i) => {
    if (!i.children) return i.permitido(acesso) ? [item(i)] : []
    const filhos = i.children.filter((c) => c.permitido(acesso)).map(item)
    return filhos.length ? [{ ...item(i), children: filhos }] : []
  })
}
