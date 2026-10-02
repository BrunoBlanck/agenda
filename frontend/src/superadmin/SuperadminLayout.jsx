import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ConfigProvider, Layout, Menu, Avatar, Flex, Typography, Tag, Button, theme } from 'antd'
import {
  CrownOutlined,
  DashboardOutlined,
  ShopOutlined,
  CreditCardOutlined,
  UserOutlined,
  TeamOutlined,
  AuditOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'

const { Header, Sider, Content } = Layout

const COR = '#4f46e5'
const FUNDO_MENU = '#1e1b4b'

const itensMenu = [
  { key: '/superadmin', icon: <DashboardOutlined />, label: 'Visão geral' },
  { key: '/superadmin/lojas', icon: <ShopOutlined />, label: 'Lojas' },
  { key: '/superadmin/planos', icon: <CreditCardOutlined />, label: 'Planos' },
  { key: '/superadmin/usuarios', icon: <TeamOutlined />, label: 'Usuários admin' },
  { key: '/superadmin/auditoria', icon: <AuditOutlined />, label: 'Auditoria' },
]

// Área da Plataforma: layout e cor próprios para não confundir com o painel da loja
function Conteudo() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { token } = theme.useToken()
  const { superadmins, sessao } = useData()
  const eu = superadmins.itens.find((s) => s.id === sessao.superadminId)

  // /superadmin/lojas/3 deixa "Lojas" selecionado
  const selecionado =
    [...itensMenu].sort((a, b) => b.key.length - a.key.length).find((i) => pathname.startsWith(i.key))?.key ?? '/superadmin'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} breakpoint="lg" width={230}>
        <Flex align="center" gap={10} style={{ padding: 16, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden' }}>
          <Avatar shape="square" size={32} icon={<CrownOutlined />} style={{ background: COR, flexShrink: 0 }} />
          {!collapsed && (
            <Flex vertical style={{ lineHeight: 1.2 }}>
              <strong style={{ fontSize: 16 }}>Plataforma</strong>
              <span style={{ fontSize: 12, opacity: 0.65 }}>SUPERADMIN</span>
            </Flex>
          )}
        </Flex>
        <Menu theme="dark" mode="inline" selectedKeys={[selecionado]} items={itensMenu} onClick={({ key }) => navigate(key)} />
      </Sider>
      <Layout>
        <Header style={{ background: token.colorBgContainer, padding: '0 24px' }}>
          <Flex justify="space-between" align="center" style={{ height: '100%' }}>
            <Flex align="center" gap={12}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                {itensMenu.find((i) => i.key === selecionado)?.label}
              </Typography.Title>
              <Tag color="purple">Prévia</Tag>
            </Flex>
            <Flex align="center" gap={8}>
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/painel')}>
                Painel da loja
              </Button>
              <Typography.Text>{eu?.nome}</Typography.Text>
              <Avatar icon={<UserOutlined />} style={{ background: COR }} />
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

export default function SuperadminLayout() {
  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: COR },
        components: {
          Layout: { siderBg: FUNDO_MENU, triggerBg: '#312e81' },
          Menu: { darkItemBg: FUNDO_MENU, darkSubMenuItemBg: FUNDO_MENU, darkItemSelectedBg: COR },
        },
      }}
    >
      <Conteudo />
    </ConfigProvider>
  )
}
