import { useState } from 'react'
import { Card, Table, Tag, Button, Flex, Select, DatePicker, Popconfirm } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento } from '../data/mock.js'
import AgendamentoModal from '../components/AgendamentoModal.jsx'
import { rotulosLocal } from '../data/locais.js'
import LocalInfo from '../components/LocalInfo.jsx'

export default function Agendamentos() {
  const { agendamentos, clientes, funcionarios, servicos, locais, loja } = useData()
  const { agenda, moduloAtivo } = useAcesso()
  const [profissional, setProfissional] = useState(null)
  const [local, setLocal] = useState(null)
  const [periodo, setPeriodo] = useState(null)
  const [modal, setModal] = useState({ open: false, agendamento: null })

  const nomeCliente = (id) => clientes.itens.find((c) => c.id === id)?.nome ?? '—'
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const nomeServico = (id) => servicos.itens.find((s) => s.id === id)?.nome ?? '—'
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja.dados)

  const dados = agendamentos.itens
    .filter(agenda.ver)
    .filter((a) => !profissional || a.funcionarioId === profissional)
    .filter((a) => !comLocais || !local || a.localId === local)
    .filter((a) => !periodo || (!dayjs(a.data).isBefore(periodo[0], 'day') && !dayjs(a.data).isAfter(periodo[1], 'day')))
    .sort((a, b) => `${a.data} ${a.hora}`.localeCompare(`${b.data} ${b.hora}`))

  const colunas = [
    { title: 'Data', dataIndex: 'data', render: (d) => dayjs(d).format('DD/MM/YYYY') },
    { title: 'Hora', dataIndex: 'hora' },
    { title: 'Cliente', dataIndex: 'clienteId', render: nomeCliente },
    agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioId', render: nomeFunc },
    moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: nomeServico },
    comLocais && {
      title: rotulos.singular,
      dataIndex: 'localId',
      render: (id) => <LocalInfo local={locais.itens.find((l) => l.id === id)} />,
    },
    { title: 'Duração', dataIndex: 'duracao', render: (d) => `${d} min` },
    {
      title: 'Status',
      dataIndex: 'status',
      render: (s) => <Tag color={statusAgendamento[s]?.color}>{statusAgendamento[s]?.label}</Tag>,
    },
    {
      title: 'Ações',
      key: 'acoes',
      width: 110,
      render: (_, a) => (
        <Flex gap={4}>
          <Button
            type="text"
            icon={agenda.editar(a) ? <EditOutlined /> : <EyeOutlined />}
            onClick={() => setModal({ open: true, agendamento: a })}
          />
          {agenda.editar(a) && (
            <Popconfirm title="Remover agendamento?" onConfirm={() => agendamentos.remover(a.id)}>
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Flex>
      ),
    },
  ].filter(Boolean)

  return (
    <Card>
      <Flex justify="space-between" wrap gap={16} style={{ marginBottom: 16 }}>
        <Flex gap={8} wrap>
          {agenda.verEquipe && (
            <Select
              allowClear
              placeholder="Todos os profissionais"
              style={{ minWidth: 220 }}
              onChange={setProfissional}
              options={funcionarios.itens.map((f) => ({ value: f.id, label: f.nome }))}
            />
          )}
          {comLocais && (
            <Select
              allowClear
              placeholder={`Qualquer ${rotulos.singular.toLowerCase()}`}
              style={{ minWidth: 200 }}
              onChange={setLocal}
              options={locais.itens.map((l) => ({ value: l.id, label: l.nome }))}
            />
          )}
          <DatePicker.RangePicker format="DD/MM/YYYY" onChange={setPeriodo} />
        </Flex>
        {agenda.criar && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModal({ open: true, agendamento: null })}>
            Novo agendamento
          </Button>
        )}
      </Flex>
      <Table rowKey="id" columns={colunas} dataSource={dados} scroll={{ x: true }} />
      <AgendamentoModal
        open={modal.open}
        agendamento={modal.agendamento}
        onClose={() => setModal({ open: false, agendamento: null })}
      />
    </Card>
  )
}
