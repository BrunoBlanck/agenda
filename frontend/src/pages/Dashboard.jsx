import { Row, Col, Card, Statistic, Table, Tag } from 'antd'
import { CalendarOutlined, UserOutlined, TeamOutlined, WarningOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { statusAgendamento } from '../data/mock.js'

export default function Dashboard() {
  const { agendamentos, clientes, funcionarios, servicos, materiais, pontos } = useData()
  const hoje = dayjs().format('YYYY-MM-DD')

  const agendaHoje = agendamentos.itens.filter((a) => a.data === hoje).sort((a, b) => a.hora.localeCompare(b.hora))
  const emServico = pontos.itens.filter((p) => p.data === hoje && !p.saida).length
  const aRepor = materiais.itens.filter((m) => m.quantidade < m.minimo)

  const nomeCliente = (id) => clientes.itens.find((c) => c.id === id)?.nome ?? '—'
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const nomeServico = (id) => servicos.itens.find((s) => s.id === id)?.nome ?? '—'

  const cards = [
    { titulo: 'Agendamentos hoje', valor: agendaHoje.length, icone: <CalendarOutlined /> },
    { titulo: 'Clientes cadastrados', valor: clientes.itens.length, icone: <UserOutlined /> },
    { titulo: 'Funcionários em serviço', valor: emServico, icone: <TeamOutlined /> },
    { titulo: 'Materiais a repor', valor: aRepor.length, icone: <WarningOutlined /> },
  ]

  return (
    <Row gutter={[16, 16]}>
      {cards.map((c) => (
        <Col key={c.titulo} xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title={c.titulo} value={c.valor} prefix={c.icone} />
          </Card>
        </Col>
      ))}
      <Col xs={24} lg={16}>
        <Card title="Agenda de hoje">
          <Table
            rowKey="id"
            pagination={false}
            dataSource={agendaHoje}
            columns={[
              { title: 'Hora', dataIndex: 'hora' },
              { title: 'Cliente', dataIndex: 'clienteId', render: nomeCliente },
              { title: 'Profissional', dataIndex: 'funcionarioId', render: nomeFunc },
              { title: 'Serviço', dataIndex: 'servicoId', render: nomeServico },
              {
                title: 'Status',
                dataIndex: 'status',
                render: (s) => <Tag color={statusAgendamento[s]?.color}>{statusAgendamento[s]?.label}</Tag>,
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Card title="Estoque baixo">
          <Table
            rowKey="id"
            pagination={false}
            dataSource={aRepor}
            columns={[
              { title: 'Material', dataIndex: 'nome' },
              { title: 'Qtd.', dataIndex: 'quantidade', render: (q) => <Tag color="red">{q}</Tag> },
            ]}
          />
        </Card>
      </Col>
    </Row>
  )
}
