import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Avatar, Button } from 'antd'
import { GlobalOutlined, LockOutlined, LogoutOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useSessaoLoja } from '../data/sessao/sessoes.js'
import { menuPermitido, telaDaRota } from './navegacao.jsx'
import { caminhoSite, usePainelPath, useSlugLoja } from './caminhos.js'
import Casca from './Casca.jsx'
import Usuario from './Usuario.jsx'
import AvisoSuporte from './AvisoSuporte.jsx'
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
  const caminho = usePainelPath()
  return (
    <Pagina titulo="Sem acesso">
      <Secao>
        <EstadoVazio
          icone={<LockOutlined />}
          titulo="Seu perfil não tem acesso a esta tela"
          descricao="Ou o módulo não está ativo nesta loja. Peça ao Administrador para liberar o acesso no seu perfil."
          acao={<Button onClick={() => navigate(caminho())}>Ir para o início</Button>}
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
  const slug = useSlugLoja()
  const caminho = usePainelPath()

  const tela = telaDaRota(pathname, caminho)
  const permitido = !tela || tela.permitido(acesso)

  return (
    <Casca
      marca={(recolhido) => <MarcaLoja loja={loja} recolhido={recolhido} />}
      itens={menuPermitido(acesso, loja, caminho)}
      selecionado={pathname}
      abertos={pathname.startsWith(caminho('/configuracoes')) ? [caminho('/configuracoes')] : []}
      onNavegar={navigate}
      aviso={<AvisoSuporte />}
      acoes={
        <>
          {/* O site do consumidor é página do back-end, fora da SPA: link de página inteira, não rota do React */}
          <Button
            type="text"
            icon={<GlobalOutlined />}
            href={caminhoSite(slug)}
            target="_blank"
            rel="noopener"
            aria-label="Site da loja"
          >
            <span className="rotulo-largo">Site da loja</span>
          </Button>
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
  const caminho = usePainelPath()
  return (
    <ExigirSessao sessao={sessao} login={caminho('/login')}>
      <Painel />
    </ExigirSessao>
  )
}
