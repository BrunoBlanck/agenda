import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { Button } from 'antd'
import { DisconnectOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import CarregandoPagina from '../components/base/CarregandoPagina.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import { useSessaoLoja } from '../data/sessao/sessoes.js'
import { retirarEntregaSuporte } from '../data/sessao/entregaSuporte.js'
import { usePainelPath } from '../layout/caminhos.js'

export const MSG_SUPORTE_INVALIDO = 'O acesso de suporte não é válido ou venceu. Gere outro no SUPERADMIN.'

// Respostas que querem dizer "este token não serve": volta ao login. O resto (sem conexão) deixa tentar de novo.
const RECUSADO = [401, 403, 404, 422]

// /:slug/painel/suporte: entrada do "Acessar loja" do SUPERADMIN (PLA-17). Fora do AppLayout, como o login.
export default function AcessoSuporte() {
  const sessao = useSessaoLoja()
  const navigate = useNavigate()
  const caminho = usePainelPath()
  const [semConexao, setSemConexao] = useState(null)
  // Ref sobrevive ao duplo efeito do StrictMode: o token só existe na primeira leitura
  const token = useRef(undefined)

  const recusar = () => navigate(caminho('/login'), { replace: true, state: { motivo: MSG_SUPORTE_INVALIDO } })

  const entrar = async () => {
    setSemConexao(null)
    // Também sem token: entrarComToken apaga desta aba as outras sessões (cópia do SUPERADMIN) e rejeita com 401
    try {
      await sessao.entrarComToken(token.current)
      token.current = null
      navigate(caminho(), { replace: true })
    } catch (e) {
      if (RECUSADO.includes(e?.status)) recusar()
      else setSemConexao(e)
    }
  }

  const aoAbrir = useEffectEvent(() => {
    if (token.current !== undefined) return
    // O SUPERADMIN gravou o token no sessionStorage desta aba; lido e apagado na hora (nada na URL)
    token.current = retirarEntregaSuporte()
    entrar()
  })
  useEffect(() => {
    aoAbrir()
  }, [])

  if (semConexao) {
    return (
      <div className="carregando-area">
        <title>Acesso de suporte | Agenda</title>
        <div className="secao">
          <EstadoVazio
            icone={<DisconnectOutlined />}
            titulo="Não foi possível abrir o painel da loja"
            descricao={semConexao.mensagem ?? 'Sem conexão com o servidor. Confira a internet e tente de novo.'}
            acao={<Button onClick={entrar}>Tentar de novo</Button>}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="carregando-area">
      <title>Abrindo o painel | Agenda</title>
      <CarregandoPagina />
    </div>
  )
}
