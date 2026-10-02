import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Avatar, Flex, Typography, Tag, Button, Result, theme } from 'antd'
import { UserOutlined, ControlOutlined, GlobalOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { menuPermitido, telaDaRota } from './navegacao.jsx'
import PainelDemonstracao from './PainelDemonstracao.jsx'

const { Header, Sider, Content } = Layout

function LogoLoja({ loja, collapsed }) {
  const inicial = loja.nomeFantasia?.[0]?.toUpperCase() ?? '?'
  return (
    <Flex align="center" gap={10} style={{ padding: 16, overflow: 'hidden' }}>
      <Avatar shape="square" size={32} src={loja.logoUrl} style={{ flexShrink: 0, background: '#0f766e' }}>
        {inicial}
      </Avatar>
      {!collapsed && (
        <Typography.Text strong ellipsis style={{ color: '#fff', fontSize: 16 }}>
          {loja.nomeFantasia}
        </Typography.Text>
      )}
    </Flex>
  )
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [demo, setDemo] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { token } = theme.useToken()
  const { loja } = useData()
  const acesso = useAcesso()

  const tela = telaDaRota(pathname)
  const permitido = !tela || tela.permitido(acesso)

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} breakpoint="lg">
        <LogoLoja loja={loja.dados} collapsed={collapsed} />
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[pathname]}
          defaultOpenKeys={pathname.startsWith('/painel/configuracoes') ? ['/painel/configuracoes'] : []}
          items={menuPermitido(acesso)}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: token.colorBgContainer, padding: '0 24px' }}>
          <Flex justify="space-between" align="center" style={{ height: '100%' }}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {tela?.label}
            </Typography.Title>
            <Flex align="center" gap={8}>
              <Button icon={<GlobalOutlined />} onClick={() => navigate('/')}>
                Site da loja
              </Button>
              <Button icon={<ControlOutlined />} onClick={() => setDemo(true)}>
                Demonstração
              </Button>
              <Typography.Text>{acesso.usuario?.nome}</Typography.Text>
              <Tag color={acesso.perfil?.acessoTotal ? 'gold' : 'default'}>{acesso.perfil?.nome}</Tag>
              <Avatar icon={<UserOutlined />} />
            </Flex>
          </Flex>
        </Header>
        <Content style={{ margin: 24 }}>
          {permitido ? (
            <Outlet />
          ) : (
            <Result
              status="403"
              title="Sem acesso"
              subTitle="Seu perfil não tem acesso a esta tela, ou o módulo não está ativo nesta loja."
              extra={<Button type="primary" onClick={() => navigate('/painel')}>Ir para o início</Button>}
            />
          )}
        </Content>
      </Layout>
      <PainelDemonstracao open={demo} onClose={() => setDemo(false)} />
    </Layout>
  )
}
