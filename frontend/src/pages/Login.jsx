import { Form, Input } from 'antd'
import { Navigate, useLocation, useSearchParams } from 'react-router-dom'
import TelaLogin from '../layout/TelaLogin.jsx'
import { useSessaoLoja } from '../data/sessao/sessoes.js'

// A última loja usada fica lembrada neste navegador (não é dado sensível: é o endereço público da loja)
const CHAVE_LOJA = 'agenda.ultimaLoja'
const lerUltimaLoja = () => {
  try {
    return window.localStorage.getItem(CHAVE_LOJA) ?? ''
  } catch {
    return ''
  }
}
const gravarUltimaLoja = (slug) => {
  try {
    window.localStorage.setItem(CHAVE_LOJA, slug)
  } catch {
    // storage bloqueado: só não lembra
  }
}

// Login do funcionário: loja (pelo endereço), e-mail e senha
export default function Login() {
  const sessao = useSessaoLoja()
  const { state } = useLocation()
  const [params] = useSearchParams()

  if (sessao.estado === 'logado') return <Navigate to={state?.de ?? '/painel'} replace />

  const entrar = async (valores) => {
    await sessao.entrar(valores)
    gravarUltimaLoja(valores.slug.trim().toLowerCase())
  }

  return (
    <TelaLogin
      area="Painel da loja"
      titulo="Entrar"
      descricao="Use o e-mail e a senha que o administrador da sua loja cadastrou."
      motivo={sessao.motivo}
      valoresIniciais={{ slug: params.get('loja') ?? lerUltimaLoja() }}
      aoEntrar={entrar}
      campos={
        <Form.Item
          name="slug"
          label="Endereço da loja"
          extra="Como aparece no endereço do site da loja, ex.: clinica-sorriso"
          normalize={(v) => v?.toLowerCase().replace(/\s+/g, '-')}
          rules={[{ required: true, whitespace: true, message: 'Informe o endereço da loja' }]}
        >
          <Input autoComplete="organization" autoCapitalize="none" spellCheck={false} />
        </Form.Item>
      }
      rodape="Esqueceu a senha? Peça ao administrador da loja para redefinir."
    />
  )
}
