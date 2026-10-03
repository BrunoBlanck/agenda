import { useState } from 'react'
import { App, Button, Flex, Popconfirm } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { aceitarSolicitacao, recusarSolicitacao } from '../data/api/agendamentos.js'
import { useTratarErro } from '../data/api/useTratarErro.js'

// Aceitar ou recusar um agendamento solicitado pelo site (status "pendente").
// onRespondido(agendamento | undefined): a tela atualiza a lista a partir do servidor
// (também quando a solicitação já foi respondida por outra pessoa ou não existe mais).
export default function AceiteSolicitacao({ agendamento, size = 'small', onRespondido }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [enviando, setEnviando] = useState(null) // 'aceitar' | 'recusar'

  const responder = async (acao) => {
    setEnviando(acao)
    try {
      const atualizado =
        acao === 'aceitar' ? await aceitarSolicitacao(agendamento.id) : await recusarSolicitacao(agendamento.id)
      message.success(acao === 'aceitar' ? 'Solicitação aceita. O horário está confirmado.' : 'Solicitação recusada.')
      onRespondido?.(atualizado)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: () => onRespondido?.(), aoConflito: () => onRespondido?.() })
    } finally {
      setEnviando(null)
    }
  }

  return (
    <Flex gap={8} onClick={(e) => e.stopPropagation()}>
      <Button
        size={size}
        type="primary"
        icon={<CheckOutlined />}
        loading={enviando === 'aceitar'}
        disabled={enviando === 'recusar'}
        onClick={() => responder('aceitar')}
      >
        Aceitar
      </Button>
      <Popconfirm
        title="Recusar esta solicitação?"
        description="O horário volta a ficar livre na agenda. Avise o cliente pelo telefone ou WhatsApp."
        okText="Recusar"
        okButtonProps={{ danger: true }}
        cancelText="Voltar"
        onConfirm={() => responder('recusar')}
      >
        <Button size={size} icon={<CloseOutlined />} loading={enviando === 'recusar'} disabled={enviando === 'aceitar'}>
          Recusar
        </Button>
      </Popconfirm>
    </Flex>
  )
}
