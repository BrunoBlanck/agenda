import { Row, Col, Card, Statistic, Table, Tag, Badge } from 'antd'
import { CalendarOutlined, UserOutlined, TeamOutlined, WarningOutlined, GlobalOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento } from '../data/mock.js'
import AceiteSolicitacao from '../components/AceiteSolicitacao.jsx'

// Cada bloco só aparece se o usuário tiver leitura no recurso correspondente
export default function Dashboard() {
  const { agendamentos, clientes, funcionarios, servicos, materiais, pontos } = useData()
  const { pode, agenda, moduloAtivo } = useAcesso()
  const hoje = dayjs().format('YYYY-MM-DD')

  const verAgenda = pode('agenda_propria') || pode('agenda_equipe')
  const verMateriais = pode('materiais')

  const agendaHoje = agendamentos.itens
    .filter((a) => a.data === hoje && agenda.ver(a))
    .sort((a, b) => a.hora.localeCompare(b.hora))
  const pendentes = agendamentos.itens
    .filter((a) => a.status === 'pendente' && agenda.ver(a))
    .sort((a, b) => `${a.data} ${a.hora}`.localeCompare(`${b.data} ${b.hora}`))
  const emServico = pontos.itens.filter((p) => p.data === hoje && !p.saida).length
  const aRepor = materiais.itens.filter((m) => m.quantidade < m.minimo)

  const nomeCliente = (id) => clientes.itens.find((c) => c.id === id)?.nome ?? '—'
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const nomeServico = (id) => servicos.itens.find((s) => s.id === id)?.nome ?? '—'

  const cards = [
    verAgenda && {
      titulo: agenda.verEquipe ? 'Agendamentos hoje' : 'Meus agendamentos hoje',
      valor: agendaHoje.length,
      icone: <CalendarOutlined />,
    },
    pode('clientes') && { titulo: 'Clientes cadastrados', valor: clientes.itens.length, icone: <UserOutlined /> },
    pode('ponto_equipe') && { titulo: 'Funcionários em serviço', valor: emServico, icone: <TeamOutlined /> },
    verMateriais && { titulo: 'Materiais a repor', valor: aRepor.length, icone: <WarningOutlined /> },
  ].filter(Boolean)

  return (
    <Row gutter={[16, 16]}>
      {pendentes.length > 0 && (
        <Col span={24}>
          <Card
            title={
              <span>
                <GlobalOutlined /> Solicitações do site <Badge count={pendentes.length} color="gold" style={{ marginLeft: 6 }} />
              </span>
            }
          >
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={pendentes}
              columns={[
                { title: 'Data', dataIndex: 'data', render: (d, a) => `${dayjs(d).format('DD/MM')} às ${a.hora}` },
                { title: 'Cliente', dataIndex: 'clienteId', render: nomeCliente },
                moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: nomeServico },
                agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioId', render: nomeFunc },
                {
                  key: 'acoes',
                  align: 'right',
                  render: (_, a) => (agenda.editar(a) ? <AceiteSolicitacao agendamento={a} /> : <Tag color="gold">Aguardando aceite</Tag>),
                },
              ].filter(Boolean)}
            />
          </Card>
        </Col>
      )}
      {cards.map((c) => (
        <Col key={c.titulo} xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title={c.titulo} value={c.valor} prefix={c.icone} />
          </Card>
        </Col>
      ))}
      {verAgenda && (
        <Col xs={24} lg={verMateriais ? 16 : 24}>
          <Card title={agenda.verEquipe ? 'Agenda de hoje' : 'Minha agenda de hoje'}>
            <Table
              rowKey="id"
              pagination={false}
              dataSource={agendaHoje}
              columns={[
                { title: 'Hora', dataIndex: 'hora' },
                { title: 'Cliente', dataIndex: 'clienteId', render: nomeCliente },
                agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioId', render: nomeFunc },
                moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: nomeServico },
                {
                  title: 'Status',
                  dataIndex: 'status',
                  render: (s) => <Tag color={statusAgendamento[s]?.color}>{statusAgendamento[s]?.label}</Tag>,
                },
              ].filter(Boolean)}
            />
          </Card>
        </Col>
      )}
      {verMateriais && (
        <Col xs={24} lg={verAgenda ? 8 : 24}>
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
      )}
    </Row>
  )
}
