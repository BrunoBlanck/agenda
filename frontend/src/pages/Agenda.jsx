import { useState } from 'react'
import { Calendar, Card, Row, Col, Select, Badge, Button, Flex, Tag, Typography, Empty } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { statusAgendamento } from '../data/mock.js'
import AgendamentoModal from '../components/AgendamentoModal.jsx'

export default function Agenda() {
  const { agendamentos, clientes, funcionarios, servicos } = useData()
  const [dia, setDia] = useState(dayjs())
  const [profissional, setProfissional] = useState(null)
  const [modal, setModal] = useState({ open: false, agendamento: null })

  const nomeCliente = (id) => clientes.itens.find((c) => c.id === id)?.nome ?? '—'
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const nomeServico = (id) => servicos.itens.find((s) => s.id === id)?.nome ?? '—'

  const filtrados = agendamentos.itens.filter((a) => !profissional || a.funcionarioId === profissional)
  const doDia = (d) =>
    filtrados.filter((a) => a.data === d.format('YYYY-MM-DD')).sort((a, b) => a.hora.localeCompare(b.hora))

  const cellRender = (data, info) => {
    if (info.type !== 'date') return info.originNode
    return doDia(data).slice(0, 3).map((a) => (
      <div key={a.id} style={{ fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        <Badge color={statusAgendamento[a.status]?.color === 'default' ? 'gray' : statusAgendamento[a.status]?.color} text={`${a.hora} ${nomeCliente(a.clienteId)}`} />
      </div>
    ))
  }

  const listaDia = doDia(dia)

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={16}>
        <Card>
          <Flex gap={8} style={{ marginBottom: 8 }}>
            <Select
              allowClear
              placeholder="Todos os profissionais"
              style={{ minWidth: 240 }}
              value={profissional}
              onChange={setProfissional}
              options={funcionarios.itens.map((f) => ({ value: f.id, label: f.nome }))}
            />
          </Flex>
          <Calendar value={dia} onSelect={setDia} cellRender={cellRender} />
        </Card>
      </Col>
      <Col xs={24} xl={8}>
        <Card
          title={dia.format('dddd, DD [de] MMMM')}
          extra={
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModal({ open: true, agendamento: null })}>
              Agendar
            </Button>
          }
        >
          {listaDia.length === 0 && <Empty description="Nenhum agendamento neste dia" />}
          <Flex vertical gap={12}>
            {listaDia.map((a) => (
              <Card
                key={a.id}
                size="small"
                hoverable
                onClick={() => setModal({ open: true, agendamento: a })}
              >
                <Flex justify="space-between">
                  <Typography.Text strong>
                    {a.hora} · {a.duracao} min
                  </Typography.Text>
                  <Tag color={statusAgendamento[a.status]?.color}>{statusAgendamento[a.status]?.label}</Tag>
                </Flex>
                <div>{nomeCliente(a.clienteId)} — {nomeServico(a.servicoId)}</div>
                <Typography.Text type="secondary">{nomeFunc(a.funcionarioId)}</Typography.Text>
              </Card>
            ))}
          </Flex>
        </Card>
      </Col>
      <AgendamentoModal
        open={modal.open}
        agendamento={modal.agendamento}
        dataInicial={dia}
        onClose={() => setModal({ open: false, agendamento: null })}
      />
    </Row>
  )
}
