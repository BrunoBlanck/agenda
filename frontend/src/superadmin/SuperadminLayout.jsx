import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Button, ConfigProvider } from 'antd'
import { ArrowLeftOutlined, AuditOutlined, CreditCardOutlined, HomeOutlined, ShopOutlined, TeamOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
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

// /superadmin/lojas/3 deixa "Lojas" selecionado
const itemDaRota = (pathname) =>
  [...itensMenu].sort((a, b) => b.key.length - a.key.length).find((i) => pathname.startsWith(i.key))?.key ?? '/superadmin'

// Área da Plataforma: mesma estrutura do painel da loja, com a barra lateral escura para não confundir as duas
export default function SuperadminLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { superadmins, sessao } = useData()
  const eu = superadmins.itens.find((s) => s.id === sessao.superadminId)

  return (
    <ConfigProvider theme={temaPlataforma}>
      <Casca
        escuro
        marca={(recolhido) => (
          <>
            <MarcaPlataforma />
            {!recolhido && (
              <div className="casca-marca-textos">
                <strong>Plataforma</strong>
                <span>SUPERADMIN (prévia)</span>
              </div>
            )}
          </>
        )}
        itens={itensMenu}
        selecionado={itemDaRota(pathname)}
        onNavegar={navigate}
        acoes={
          <>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/painel')} aria-label="Painel da loja">
              <span className="rotulo-largo">Painel da loja</span>
            </Button>
            <Usuario nome={eu?.nome} detalhe="Superadmin" />
          </>
        }
      >
        <Outlet />
      </Casca>
    </ConfigProvider>
  )
}
