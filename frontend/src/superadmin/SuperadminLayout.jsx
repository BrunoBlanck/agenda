import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Button, ConfigProvider } from 'antd'
import { AuditOutlined, CreditCardOutlined, HomeOutlined, LogoutOutlined, ShopOutlined, TeamOutlined } from '@ant-design/icons'
import { useSessaoSuperadmin } from '../data/sessao/sessoes.js'
import ExigirSessao from '../layout/ExigirSessao.jsx'
import { temaPlataforma } from '../tema.js'
import Casca from '../layout/Casca.jsx'
import Usuario from '../layout/Usuario.jsx'
import MarcaPlataforma from './MarcaPlataforma.jsx'

const itensMenu = [
  { key: '/superadmin', icon: <HomeOutlined />, label: 'Visão geral' },
  { key: '/superadmin/lojas', icon: <ShopOutlined />, label: 'Lojas' },
  { key: '/superadmin/planos', icon: <CreditCardOutlined />, label: 'Planos' },
  { key: '/superadmin/usuarios', icon: <TeamOutlined />, label: 'Usuários admin' },
  { key: '/superadmin/auditoria', icon: <AuditOutlined />, label: 'Auditoria' },
]

// /superadmin/lojas/3 deixa "Lojas" selecionado; endereço que não existe não marca nenhum item
const itemDaRota = (pathname) =>
  pathname === '/superadmin'
    ? '/superadmin'
    : itensMenu.find((i) => i.key !== '/superadmin' && (pathname === i.key || pathname.startsWith(`${i.key}/`)))?.key ?? ''

// Área da Plataforma: mesma estrutura do painel da loja, com a barra lateral escura para não confundir as duas
export default function SuperadminLayout() {
  const sessao = useSessaoSuperadmin()
  return (
    <ConfigProvider theme={temaPlataforma}>
      <ExigirSessao sessao={sessao} login="/superadmin/login">
        <Plataforma />
      </ExigirSessao>
    </ConfigProvider>
  )
}

function Plataforma() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { eu, sair } = useSessaoSuperadmin()

  return (
    <>
      <Casca
        escuro
        marca={(recolhido) => (
          <>
            <MarcaPlataforma />
            {!recolhido && (
              <div className="casca-marca-textos">
                <strong>Plataforma</strong>
                <span>SUPERADMIN</span>
              </div>
            )}
          </>
        )}
        itens={itensMenu}
        selecionado={itemDaRota(pathname)}
        onNavegar={navigate}
        acoes={
          <>
            <Usuario nome={eu?.nome} detalhe="Superadmin" />
            <Button type="text" icon={<LogoutOutlined />} onClick={sair} aria-label="Sair">
              <span className="rotulo-largo">Sair</span>
            </Button>
          </>
        }
      >
        <Outlet />
      </Casca>
    </>
  )
}
