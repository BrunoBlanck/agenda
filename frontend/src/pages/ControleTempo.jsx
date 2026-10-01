import { useState } from 'react'
import { Card, Table, Button, Flex, Select, Tag, DatePicker, Typography, message } from 'antd'
import { LoginOutlined, LogoutOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'

function horasTrabalhadas(p) {
  if (!p.saida) return null
  const min = dayjs(`${p.data} ${p.saida}`).diff(dayjs(`${p.data} ${p.entrada}`), 'minute')
  return `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, '0')}min`
}

export default function ControleTempo() {
  const { pontos, funcionarios } = useData()
  const [funcionarioId, setFuncionarioId] = useState(null)
  const [data, setData] = useState(dayjs())
  const [msg, contextHolder] = message.useMessage()

  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const hoje = dayjs().format('YYYY-MM-DD')
  const aberto = pontos.itens.find((p) => p.funcionarioId === funcionarioId && p.data === hoje && !p.saida)

  const registrar = () => {
    const agora = dayjs().format('HH:mm')
    if (aberto) {
      pontos.atualizar(aberto.id, { saida: agora })
      msg.success(`Saída registrada às ${agora}`)
    } else {
      pontos.adicionar({ funcionarioId, data: hoje, entrada: agora, saida: null })
      msg.success(`Entrada registrada às ${agora}`)
    }
  }

  const dados = pontos.itens.filter((p) => !data || p.data === data.format('YYYY-MM-DD'))

  const colunas = [
    { title: 'Funcionário', dataIndex: 'funcionarioId', render: nomeFunc },
    { title: 'Data', dataIndex: 'data', render: (d) => dayjs(d).format('DD/MM/YYYY') },
    { title: 'Entrada', dataIndex: 'entrada' },
    { title: 'Saída', dataIndex: 'saida', render: (s) => s ?? <Tag color="processing">Em serviço</Tag> },
    { title: 'Total', key: 'total', render: (_, p) => horasTrabalhadas(p) ?? '—' },
  ]

  return (
    <Flex vertical gap={16}>
      {contextHolder}
      <Card title="Registrar ponto">
        <Flex gap={8} wrap align="center">
          <Select
            placeholder="Selecione o funcionário"
            style={{ minWidth: 260 }}
            onChange={setFuncionarioId}
            options={funcionarios.itens.filter((f) => f.ativo).map((f) => ({ value: f.id, label: f.nome }))}
          />
          <Button
            type="primary"
            danger={!!aberto}
            disabled={!funcionarioId}
            icon={aberto ? <LogoutOutlined /> : <LoginOutlined />}
            onClick={registrar}
          >
            {aberto ? 'Registrar saída' : 'Registrar entrada'}
          </Button>
          {aberto && <Typography.Text type="secondary">Entrada às {aberto.entrada}</Typography.Text>}
        </Flex>
      </Card>
      <Card title="Registros" extra={<DatePicker format="DD/MM/YYYY" value={data} onChange={setData} />}>
        <Table rowKey="id" columns={colunas} dataSource={dados} scroll={{ x: true }} />
      </Card>
    </Flex>
  )
}
