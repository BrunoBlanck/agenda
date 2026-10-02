import { useState } from 'react'
import { Card, Table, Select, Tag, TimePicker, DatePicker, Button, Flex, Modal, Form, Input, Popconfirm, Alert, Row, Col, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'

// Segunda a domingo
const dias = [
  [1, 'Segunda'],
  [2, 'Terça'],
  [3, 'Quarta'],
  [4, 'Quinta'],
  [5, 'Sexta'],
  [6, 'Sábado'],
  [0, 'Domingo'],
]

const FORMATO = 'YYYY-MM-DD HH:mm'

// Configurações > Agendamentos: jornada semanal (2.5) e bloqueios (2.6)
export default function ConfigAgendamentos() {
  const { funcionarios, jornadas, bloqueios } = useData()
  const { pode } = useAcesso()
  const somenteLeitura = !pode('config_agendamentos', 'escrita')
  const ativos = funcionarios.itens.filter((f) => f.ativo)
  const [funcionarioId, setFuncionarioId] = useState(ativos[0]?.id)
  const [novoBloqueio, setNovoBloqueio] = useState(false)
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()

  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'

  const faixasDoDia = (dia) =>
    jornadas.itens
      .filter((j) => j.funcionarioId === funcionarioId && j.diaSemana === dia)
      .sort((a, b) => a.inicio.localeCompare(b.inicio))

  const adicionarFaixa = (dia, intervalo) => {
    if (!intervalo) return
    const [inicio, fim] = intervalo.map((h) => h.format('HH:mm'))
    if (fim <= inicio) {
      msg.error('O fim deve ser depois do início.')
      return
    }
    if (faixasDoDia(dia).some((f) => inicio < f.fim && fim > f.inicio)) {
      msg.error('Essa faixa se sobrepõe a outra do mesmo dia.')
      return
    }
    jornadas.adicionar({ funcionarioId, diaSemana: dia, inicio, fim })
  }

  const salvarBloqueio = async () => {
    const v = await form.validateFields()
    bloqueios.adicionar({
      funcionarioId: v.funcionarioId ?? null,
      inicio: v.periodo[0].format(FORMATO),
      fim: v.periodo[1].format(FORMATO),
      motivo: v.motivo,
    })
    setNovoBloqueio(false)
  }

  const colunasJornada = [
    { title: 'Dia', dataIndex: 'nome', width: 110 },
    {
      title: 'Horários',
      key: 'faixas',
      render: (_, { dia }) => {
        const faixas = faixasDoDia(dia)
        if (!faixas.length) return <Tag>Não trabalha</Tag>
        return faixas.map((f) => (
          <Tag
            key={f.id}
            color="blue"
            closable={!somenteLeitura}
            onClose={(e) => {
              e.preventDefault()
              jornadas.remover(f.id)
            }}
          >
            {f.inicio} – {f.fim}
          </Tag>
        ))
      },
    },
    !somenteLeitura && {
      title: 'Adicionar faixa',
      key: 'adicionar',
      width: 230,
      render: (_, { dia }) => (
        <TimePicker.RangePicker
          format="HH:mm"
          minuteStep={15}
          value={null}
          placeholder={['Início', 'Fim']}
          onChange={(intervalo) => adicionarFaixa(dia, intervalo)}
        />
      ),
    },
  ].filter(Boolean)

  const colunasBloqueio = [
    {
      title: 'Quem',
      dataIndex: 'funcionarioId',
      render: (id) => (id == null ? <Tag color="purple">Loja inteira</Tag> : nomeFunc(id)),
    },
    {
      title: 'Período',
      key: 'periodo',
      render: (_, b) => `${dayjs(b.inicio).format('DD/MM/YYYY HH:mm')} até ${dayjs(b.fim).format('DD/MM/YYYY HH:mm')}`,
    },
    { title: 'Motivo', dataIndex: 'motivo' },
    !somenteLeitura && {
      title: '',
      key: 'acoes',
      width: 60,
      render: (_, b) => (
        <Popconfirm title="Remover bloqueio?" onConfirm={() => bloqueios.remover(b.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ].filter(Boolean)

  return (
    <Flex vertical gap={16}>
      {contextHolder}
      {somenteLeitura && <Alert type="info" showIcon title="Você tem acesso somente para leitura nesta tela." />}
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card
            title="Jornada semanal"
            extra={
              <Select
                style={{ minWidth: 220 }}
                value={funcionarioId}
                onChange={setFuncionarioId}
                options={ativos.map((f) => ({ value: f.id, label: f.nome }))}
              />
            }
          >
            <Table
              rowKey="dia"
              size="small"
              pagination={false}
              columns={colunasJornada}
              dataSource={dias.map(([dia, nome]) => ({ dia, nome }))}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card
            title="Bloqueios, folgas e feriados"
            extra={
              !somenteLeitura && (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    form.resetFields()
                    setNovoBloqueio(true)
                  }}
                >
                  Novo bloqueio
                </Button>
              )
            }
          >
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              columns={colunasBloqueio}
              dataSource={[...bloqueios.itens].sort((a, b) => a.inicio.localeCompare(b.inicio))}
            />
          </Card>
        </Col>
      </Row>
      <Modal title="Novo bloqueio" open={novoBloqueio} onOk={salvarBloqueio} onCancel={() => setNovoBloqueio(false)} okText="Salvar">
        <Form form={form} layout="vertical">
          <Form.Item name="funcionarioId" label="Profissional" extra="Deixe em branco para bloquear a loja inteira (ex.: feriado).">
            <Select allowClear placeholder="Loja inteira" options={ativos.map((f) => ({ value: f.id, label: f.nome }))} />
          </Form.Item>
          <Form.Item name="periodo" label="Período" rules={[{ required: true }]}>
            <DatePicker.RangePicker showTime={{ format: 'HH:mm', minuteStep: 15 }} format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="motivo" label="Motivo">
            <Input maxLength={150} placeholder="Férias, folga, feriado..." />
          </Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
