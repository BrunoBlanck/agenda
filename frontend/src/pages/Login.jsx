import { Avatar } from 'antd'
import { Navigate, useLocation } from 'react-router-dom'
import TelaLogin from '../layout/TelaLogin.jsx'
import { usePainelPath, useSlugLoja } from '../layout/caminhos.js'
import { useSessaoLoja } from '../data/sessao/sessoes.js'
import { useLojaPublica } from '../data/useLojaPublica.js'

// Logo da loja ao lado do nome; sem logo (ou enquanto carrega), a inicial sobre a tinta
function MarcaLoja({ nome, logoUrl }) {
  return (
    <Avatar shape="square" size={40} src={logoUrl || undefined} className="login-marca-loja" aria-hidden="true">
      {nome[0]?.toUpperCase() ?? '?'}
    </Avatar>
  )
}

// Login do funcionário: a loja vem do endereço (/:slug/painel/login), a pessoa só digita e-mail e senha (ACE-02)
export default function Login() {
  const sessao = useSessaoLoja()
  const slug = useSlugLoja()
  const caminho = usePainelPath()
  const { state } = useLocation()
  // Erro ou 404 no endpoint público não trava o login: loja suspensa também some do site,
  // e quem diz o motivo certo é a resposta do próprio login
  const { loja, carregando } = useLojaPublica(slug)

  if (sessao.estado === 'logado') {
    const de = typeof state?.de === 'string' && state.de.startsWith(caminho()) ? state.de : caminho()
    return <Navigate to={de} replace />
  }

  const nome = loja?.nome || slug

  return (
    <TelaLogin
      area="Painel da loja"
      marca={<MarcaLoja nome={nome} logoUrl={loja?.logoUrl} />}
      titulo={
        <span className={carregando ? 'login-titulo-provisorio' : undefined} aria-busy={carregando || undefined}>
          {nome}
        </span>
      }
      descricao="Entre com o e-mail e a senha que o administrador da loja cadastrou para você."
      motivo={sessao.motivo}
      aoEntrar={({ email, senha }) => sessao.entrar({ email, senha })}
      rodape="Esqueceu a senha? Peça ao administrador da loja para redefinir."
    />
  )
}
