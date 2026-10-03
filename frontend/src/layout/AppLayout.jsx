import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Avatar, Button } from 'antd'
import { GlobalOutlined, LockOutlined, LogoutOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useSessaoLoja } from '../data/sessao/sessoes.js'
import { menuPermitido, telaDaRota } from './navegacao.jsx'
import Casca from './Casca.jsx'
import Usuario from './Usuario.jsx'
import ExigirSessao from './ExigirSessao.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'

function MarcaLoja({ loja, recolhido }) {
  const nome = loja?.nomeFantasia || loja?.nome || ''
  return (
    <>
      <Avatar shape="square" size={36} src={loja?.logoUrl || undefined} className="marca-loja">
        {nome[0]?.toUpperCase() ?? '?'}
      </Avatar>
      {!recolhido && (
        <div className="casca-marca-textos">
          <strong>{nome}</strong>
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

function Painel() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { sair } = useSessaoLoja()
  const acesso = useAcesso()
  const loja = acesso.loja

  const tela = telaDaRota(pathname)
  const permitido = !tela || tela.permitido(acesso)

  return (
    <Casca
      marca={(recolhido) => <MarcaLoja loja={loja} recolhido={recolhido} />}
      itens={menuPermitido(acesso, loja)}
      selecionado={pathname}
      abertos={pathname.startsWith('/painel/configuracoes') ? ['/painel/configuracoes'] : []}
      onNavegar={navigate}
      acoes={
        <>
          {/* O site do consumidor fica fora da SPA do painel (no futuro, servido pelo back-end) */}
          {loja?.slug && (
            <Button type="text" icon={<GlobalOutlined />} href={`/site/${loja.slug}`} target="_blank" aria-label="Site da loja">
              <span className="rotulo-largo">Site da loja</span>
            </Button>
          )}
          <Usuario nome={acesso.usuario?.nome} detalhe={acesso.perfil?.nome} />
          <Button type="text" icon={<LogoutOutlined />} onClick={sair} aria-label="Sair">
            <span className="rotulo-largo">Sair</span>
          </Button>
        </>
      }
    >
      {permitido ? <Outlet /> : <SemAcesso />}
    </Casca>
  )
}

export default function AppLayout() {
  const sessao = useSessaoLoja()
  return (
    <ExigirSessao sessao={sessao} login="/painel/login">
      <Painel />
    </ExigirSessao>
  )
}
