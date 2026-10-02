import { Flex, Typography, theme } from 'antd'
import { HistoryOutlined, RightOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { inicioDe, useHistoricoCliente } from '../data/useHistoricoCliente.js'

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`

// Resumo do cliente logo abaixo do campo Cliente do agendamento. Clicar abre o histórico completo.
// Fica fora do <Form> desabilitado, então continua clicável em agendamentos só de leitura.
export default function ResumoCliente({ clienteId, agendamentoId, onAbrir }) {
  const { token } = theme.useToken()
  const { visiveis, concluidos, faltas, ultimo, proximo } = useHistoricoCliente(clienteId)
  const outros = visiveis.filter((a) => a.id !== agendamentoId)

  if (!clienteId) return null

  if (outros.length === 0) {
    return (
      <Typography.Text type="secondary" style={{ display: 'block', margin: '-16px 0 16px', fontSize: 13 }}>
        <HistoryOutlined /> Primeiro agendamento deste cliente.
      </Typography.Text>
    )
  }

  const detalhes = [
    plural(concluidos, 'atendimento', 'atendimentos'),
    ultimo && `último em ${dayjs(ultimo.data).format('DD/MM/YYYY')}`,
  ].filter(Boolean)

  return (
    <Flex
      role="button"
      tabIndex={0}
      onClick={onAbrir}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onAbrir()}
      align="center"
      gap={12}
      style={{
        margin: '-12px 0 20px',
        padding: '8px 12px',
        borderRadius: token.borderRadius,
        background: token.colorFillQuaternary,
        border: `1px solid ${token.colorBorderSecondary}`,
        cursor: 'pointer',
      }}
    >
      <HistoryOutlined style={{ color: token.colorPrimary, fontSize: 16 }} />
      <Flex vertical style={{ flex: 1, minWidth: 0, lineHeight: 1.4 }}>
        <Typography.Text style={{ fontSize: 13 }}>
          {detalhes.join(' · ')}
          {faltas > 0 && (
            <Typography.Text type="warning" style={{ fontSize: 13 }}>
              {' · '}
              {plural(faltas, 'falta', 'faltas')}
            </Typography.Text>
          )}
        </Typography.Text>
        {proximo && proximo.id !== agendamentoId && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Próximo: {inicioDe(proximo).format('DD/MM [às] HH:mm')}
          </Typography.Text>
        )}
      </Flex>
      <Typography.Text style={{ color: token.colorPrimary, fontSize: 13, whiteSpace: 'nowrap' }}>
        Ver histórico <RightOutlined style={{ fontSize: 10 }} />
      </Typography.Text>
    </Flex>
  )
}
