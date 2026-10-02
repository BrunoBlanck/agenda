import { Button, Flex, Popconfirm } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'

// Aceitar ou recusar um agendamento solicitado pelo site (status "pendente")
export default function AceiteSolicitacao({ agendamento, size = 'small' }) {
  const { agendamentos } = useData()
  const parar = (e) => e?.stopPropagation()

  return (
    <Flex gap={8} onClick={parar}>
      <Button
        size={size}
        type="primary"
        icon={<CheckOutlined />}
        onClick={() => agendamentos.atualizar(agendamento.id, { status: 'confirmado' })}
      >
        Aceitar
      </Button>
      <Popconfirm
        title="Recusar esta solicitação?"
        description="O cliente é avisado de que o horário não foi confirmado."
        onConfirm={() =>
          agendamentos.atualizar(agendamento.id, { status: 'cancelado', motivoCancelamento: 'Recusado pela loja' })
        }
      >
        <Button size={size} danger icon={<CloseOutlined />}>
          Recusar
        </Button>
      </Popconfirm>
    </Flex>
  )
}
