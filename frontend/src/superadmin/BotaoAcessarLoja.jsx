import { useState } from 'react'
import { App, Button, Tooltip } from 'antd'
import { LoginOutlined } from '@ant-design/icons'
import { gerarAcessoLoja } from '../data/api/plataforma.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { caminhoPainel } from '../layout/caminhos.js'
import { CHAVE_ENTREGA_SUPORTE } from '../data/sessao/entregaSuporte.js'

const AJUDA = 'Abre o painel em outra aba como o Administrador da loja, por 1 hora.'
const MSG_SEM_ENTREGA = 'Não foi possível abrir a loja nesta aba. Tente de novo.'

// Acessar loja (PLA-17): abre o painel da loja em outra aba já logado como o Administrador.
// A aba nasce no clique (about:blank), senão o bloqueador de pop-up barra a abertura depois do await.
// O token nunca vai na URL (iria para o histórico do navegador): é gravado no sessionStorage da aba
// nova (about:blank é da mesma origem) e a tela /suporte lê e apaga na hora.
export default function BotaoAcessarLoja({ lojaId }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [abrindo, setAbrindo] = useState(false)

  const acessar = async () => {
    const aba = window.open('about:blank', '_blank')
    if (!aba) {
      message.error('Permita pop-ups deste site para acessar a loja.')
      return
    }
    setAbrindo(true)
    try {
      const { token, slug } = await gerarAcessoLoja(lojaId)
      if (aba.closed) return
      try {
        aba.sessionStorage.setItem(CHAVE_ENTREGA_SUPORTE, token)
      } catch {
        // storage bloqueado ou aba que já não é da mesma origem: sem entrega, não abre
        aba.close()
        message.error(MSG_SEM_ENTREGA)
        return
      }
      // A aba do painel não pode controlar o SUPERADMIN (window.opener)
      aba.opener = null
      // replace: o about:blank não fica no histórico da aba; endereço absoluto porque a aba é about:blank
      aba.location.replace(new URL(caminhoPainel(slug, '/suporte'), window.location.origin).href)
    } catch (e) {
      aba.close()
      tratarErro(e)
    } finally {
      setAbrindo(false)
    }
  }

  return (
    <Tooltip title={AJUDA} placement="bottom">
      <Button icon={<LoginOutlined />} loading={abrindo} onClick={acessar} aria-description={AJUDA}>
        Acessar loja
      </Button>
    </Tooltip>
  )
}
