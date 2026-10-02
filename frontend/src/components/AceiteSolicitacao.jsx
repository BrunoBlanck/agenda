import { App, Button, Flex, Popconfirm } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'

// Aceitar ou recusar um agendamento solicitado pelo site (status "pendente")
export default function AceiteSolicitacao({ agendamento, size = 'small' }) {
  const { agendamentos } = useData()
  const { message } = App.useApp()

  return (
    <Flex gap={8} onClick={(e) => e.stopPropagation()}>
      <Button
        size={size}
        type="primary"
        icon={<CheckOutlined />}
        onClick={() => {
          agendamentos.atualizar(agendamento.id, { status: 'confirmado' })
          message.success('Solicitação aceita. O horário está confirmado.')
        }}
      >
        Aceitar
      </Button>
      <Popconfirm
        title="Recusar esta solicitação?"
        description="O cliente é avisado de que o horário não foi confirmado."
        okText="Recusar"
        okButtonProps={{ danger: true }}
        cancelText="Voltar"
        onConfirm={() => {
          agendamentos.atualizar(agendamento.id, { status: 'cancelado', motivoCancelamento: 'Recusado pela loja' })
          message.success('Solicitação recusada.')
        }}
      >
        <Button size={size} icon={<CloseOutlined />}>
          Recusar
        </Button>
      </Popconfirm>
    </Flex>
  )
}
