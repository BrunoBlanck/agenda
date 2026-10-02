import { Suspense, useState } from 'react'
import { Button, Drawer, Layout, Menu } from 'antd'
import { MenuOutlined } from '@ant-design/icons'
import { useLocation } from 'react-router-dom'
import CarregandoPagina from '../components/base/CarregandoPagina.jsx'
import LimiteErro from '../components/base/LimiteErro.jsx'
import './casca.css'

const { Header, Sider, Content } = Layout

// Estrutura comum ao painel da loja e ao SUPERADMIN: menu lateral (recolhível no desktop,
// gaveta no celular), barra superior com as ações e o conteúdo da tela.
// escuro: barra lateral em grafite (SUPERADMIN).
export default function Casca({ marca, itens, selecionado, abertos, onNavegar, acoes, escuro = false, children }) {
  const [recolhido, setRecolhido] = useState(false)
  const [gaveta, setGaveta] = useState(false)
  const { pathname } = useLocation()
  const temaMenu = escuro ? 'dark' : 'light'

  const menu = (aoClicar) => (
    <Menu
      theme={temaMenu}
      mode="inline"
      selectedKeys={[selecionado]}
      defaultOpenKeys={abertos}
      items={itens}
      onClick={({ key }) => {
        aoClicar?.()
        onNavegar(key)
      }}
    />
  )

  return (
    <Layout className={escuro ? 'casca casca-escura' : 'casca'}>
      <a className="pular-para-conteudo" href="#conteudo">
        Pular para o conteúdo
      </a>
      <Sider
        className="casca-lateral"
        theme={temaMenu}
        width={240}
        collapsedWidth={68}
        collapsible
        collapsed={recolhido}
        onCollapse={setRecolhido}
      >
        <div className="casca-marca">{marca(recolhido)}</div>
        <nav aria-label="Menu principal">{menu()}</nav>
      </Sider>

      <Drawer
        className={escuro ? 'casca-gaveta casca-escura' : 'casca-gaveta'}
        placement="left"
        size={280}
        open={gaveta}
        onClose={() => setGaveta(false)}
        closable={false}
        styles={{ body: { padding: 0 } }}
      >
        <div className="casca-marca">{marca(false)}</div>
        <nav aria-label="Menu principal">{menu(() => setGaveta(false))}</nav>
      </Drawer>

      <Layout>
        <Header className="casca-topo">
          <Button
            className="casca-abrir-menu"
            type="text"
            icon={<MenuOutlined />}
            aria-label="Abrir menu"
            onClick={() => setGaveta(true)}
          />
          <div className="casca-topo-acoes">{acoes}</div>
        </Header>
        <Content id="conteudo" className="casca-conteudo" tabIndex={-1}>
          {/* key: trocar de tela limpa o erro da tela anterior */}
          <LimiteErro key={pathname}>
            <Suspense fallback={<CarregandoPagina />}>{children}</Suspense>
          </LimiteErro>
        </Content>
      </Layout>
    </Layout>
  )
}
