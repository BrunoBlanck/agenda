import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Avatar, Flex, Typography, theme } from 'antd'
import {
  DashboardOutlined,
  CalendarOutlined,
  ScheduleOutlined,
  UserOutlined,
  TeamOutlined,
  MedicineBoxOutlined,
  FieldTimeOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = Layout

const itensMenu = [
  { key: '/', icon: <DashboardOutlined />, label: 'Início' },
  { key: '/agenda', icon: <CalendarOutlined />, label: 'Agenda' },
  { key: '/agendamentos', icon: <ScheduleOutlined />, label: 'Agendamentos' },
  { key: '/clientes', icon: <UserOutlined />, label: 'Clientes' },
  { key: '/funcionarios', icon: <TeamOutlined />, label: 'Funcionários' },
  { key: '/servicos', icon: <ExperimentOutlined />, label: 'Serviços' },
  { key: '/materiais', icon: <MedicineBoxOutlined />, label: 'Materiais' },
  { key: '/controle-tempo', icon: <FieldTimeOutlined />, label: 'Controle de Tempo' },
]

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { token } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} breakpoint="lg">
        <div style={{ color: '#fff', padding: 16, fontWeight: 600, fontSize: 18, whiteSpace: 'nowrap' }}>
          {collapsed ? '🦷' : '🦷 Clínica'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[pathname]}
          items={itensMenu}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: token.colorBgContainer, padding: '0 24px' }}>
          <Flex justify="space-between" align="center" style={{ height: '100%' }}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {itensMenu.find((i) => i.key === pathname)?.label}
            </Typography.Title>
            <Flex align="center" gap={8}>
              <Typography.Text>Juliana Alves</Typography.Text>
              <Avatar icon={<UserOutlined />} />
            </Flex>
          </Flex>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
