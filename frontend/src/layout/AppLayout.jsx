import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Avatar, Button } from 'antd'
import { ControlOutlined, GlobalOutlined, LockOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { menuPermitido, telaDaRota } from './navegacao.jsx'
import Casca from './Casca.jsx'
import Usuario from './Usuario.jsx'
import PainelDemonstracao from './PainelDemonstracao.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'

function MarcaLoja({ loja, recolhido }) {
  return (
    <>
      <Avatar shape="square" size={36} src={loja.logoUrl} className="marca-loja">
        {loja.nomeFantasia?.[0]?.toUpperCase() ?? '?'}
      </Avatar>
      {!recolhido && (
        <div className="casca-marca-textos">
          <strong>{loja.nomeFantasia}</strong>
          <span>Painel da loja</span>
        </div>
      )}
    </>
  )
}

function SemAcesso() {
  const navigate = useNavigate()
  return (
    <Pagina titulo="Sem acesso">
      <Secao>
        <EstadoVazio
          icone={<LockOutlined />}
          titulo="Seu perfil não tem acesso a esta tela"
          descricao="Ou o módulo não está ativo nesta loja. Peça ao Administrador para liberar o acesso no seu perfil."
          acao={<Button onClick={() => navigate('/painel')}>Ir para o início</Button>}
        />
      </Secao>
    </Pagina>
  )
}

export default function AppLayout() {
  const [demo, setDemo] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { loja } = useData()
  const acesso = useAcesso()

  const tela = telaDaRota(pathname)
  const permitido = !tela || tela.permitido(acesso)

  return (
    <>
      <Casca
        marca={(recolhido) => <MarcaLoja loja={loja.dados} recolhido={recolhido} />}
        itens={menuPermitido(acesso, loja.dados)}
        selecionado={pathname}
        abertos={pathname.startsWith('/painel/configuracoes') ? ['/painel/configuracoes'] : []}
        onNavegar={navigate}
        acoes={
          <>
            {/* O site do consumidor fica na raiz (no futuro, servido pelo back-end): link comum, não rota da SPA */}
            <Button type="text" icon={<GlobalOutlined />} href="/" aria-label="Site da loja">
              <span className="rotulo-largo">Site da loja</span>
            </Button>
            <Button type="text" icon={<ControlOutlined />} onClick={() => setDemo(true)} aria-label="Demonstração">
              <span className="rotulo-largo">Demonstração</span>
            </Button>
            <Usuario nome={acesso.usuario?.nome} detalhe={acesso.perfil?.nome} />
          </>
        }
      >
        {permitido ? <Outlet /> : <SemAcesso />}
      </Casca>
      <PainelDemonstracao open={demo} onClose={() => setDemo(false)} />
    </>
  )
}
