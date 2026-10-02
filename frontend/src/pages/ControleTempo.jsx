import { useState } from 'react'
import { Card, Table, Button, Flex, Select, Tag, DatePicker, TimePicker, Typography, Modal, Form, Input, Tooltip, message } from 'antd'
import { LoginOutlined, LogoutOutlined, EditOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'

function horasTrabalhadas(p) {
  if (!p.saida) return null
  const min = dayjs(`${p.data} ${p.saida}`).diff(dayjs(`${p.data} ${p.entrada}`), 'minute')
  return `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, '0')}min`
}

export default function ControleTempo() {
  const { pontos, funcionarios } = useData()
  const { usuario, pode } = useAcesso()
  const [escolhido, setEscolhido] = useState(null)
  const [data, setData] = useState(dayjs())
  const [corrigindo, setCorrigindo] = useState(null)
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()

  const verEquipe = pode('ponto_equipe')
  const corrigir = pode('ponto_equipe', 'escrita')
  const registrarProprio = pode('ponto_proprio', 'escrita')

  // Quem corrige o ponto da equipe pode registrar para outro funcionário; os demais, só para si
  const funcionarioId = corrigir ? (escolhido ?? usuario?.id) : usuario?.id

  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const hoje = dayjs().format('YYYY-MM-DD')
  const aberto = pontos.itens.find((p) => p.funcionarioId === funcionarioId && p.data === hoje && !p.saida)

  const registrar = () => {
    const agora = dayjs().format('HH:mm')
    if (aberto) {
      pontos.atualizar(aberto.id, { saida: agora })
      msg.success(`Saída registrada às ${agora}`)
    } else {
      pontos.adicionar({ funcionarioId, data: hoje, entrada: agora, saida: null, origem: 'sistema' })
      msg.success(`Entrada registrada às ${agora}`)
    }
  }

  const abrirCorrecao = (p) => {
    setCorrigindo(p)
    form.setFieldsValue({
      entrada: dayjs(p.entrada, 'HH:mm'),
      saida: p.saida ? dayjs(p.saida, 'HH:mm') : null,
      justificativa: '',
    })
  }

  const salvarCorrecao = async () => {
    const v = await form.validateFields()
    pontos.atualizar(corrigindo.id, {
      entrada: v.entrada.format('HH:mm'),
      saida: v.saida ? v.saida.format('HH:mm') : null,
      origem: 'manual',
      justificativa: v.justificativa,
      editadoPor: usuario?.id,
    })
    setCorrigindo(null)
  }

  const dados = pontos.itens
    .filter((p) => verEquipe || p.funcionarioId === usuario?.id)
    .filter((p) => !data || p.data === data.format('YYYY-MM-DD'))

  const colunas = [
    verEquipe && { title: 'Funcionário', dataIndex: 'funcionarioId', render: nomeFunc },
    { title: 'Data', dataIndex: 'data', render: (d) => dayjs(d).format('DD/MM/YYYY') },
    { title: 'Entrada', dataIndex: 'entrada' },
    { title: 'Saída', dataIndex: 'saida', render: (s) => s ?? <Tag color="processing">Em serviço</Tag> },
    { title: 'Total', key: 'total', render: (_, p) => horasTrabalhadas(p) ?? '—' },
    {
      title: 'Origem',
      dataIndex: 'origem',
      render: (o, p) =>
        o === 'manual' ? (
          <Tooltip title={`${p.justificativa} (por ${nomeFunc(p.editadoPor)})`}>
            <Tag color="orange">Ajuste manual</Tag>
          </Tooltip>
        ) : (
          <Tag>Sistema</Tag>
        ),
    },
    corrigir && {
      title: 'Ações',
      key: 'acoes',
      width: 80,
      render: (_, p) => <Button type="text" icon={<EditOutlined />} onClick={() => abrirCorrecao(p)} />,
    },
  ].filter(Boolean)

  return (
    <Flex vertical gap={16}>
      {contextHolder}
      {(registrarProprio || corrigir) && (
        <Card title="Registrar ponto">
          <Flex gap={8} wrap align="center">
            {corrigir ? (
              <Select
                style={{ minWidth: 260 }}
                value={funcionarioId}
                onChange={setEscolhido}
                options={funcionarios.itens.filter((f) => f.ativo).map((f) => ({ value: f.id, label: f.nome }))}
              />
            ) : (
              <Typography.Text strong>{usuario?.nome}</Typography.Text>
            )}
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
      )}
      <Card
        title={verEquipe ? 'Registros da equipe' : 'Meus registros'}
        extra={<DatePicker format="DD/MM/YYYY" value={data} onChange={setData} />}
      >
        <Table rowKey="id" columns={colunas} dataSource={dados} scroll={{ x: true }} />
      </Card>
      <Modal
        title={`Corrigir ponto de ${nomeFunc(corrigindo?.funcionarioId)}`}
        open={!!corrigindo}
        onOk={salvarCorrecao}
        onCancel={() => setCorrigindo(null)}
        okText="Salvar correção"
      >
        <Form form={form} layout="vertical">
          <Flex gap={16}>
            <Form.Item name="entrada" label="Entrada" rules={[{ required: true }]}>
              <TimePicker format="HH:mm" />
            </Form.Item>
            <Form.Item
              name="saida"
              label="Saída"
              dependencies={['entrada']}
              rules={[
                ({ getFieldValue }) => ({
                  validator: (_, saida) =>
                    !saida || saida.isAfter(getFieldValue('entrada'))
                      ? Promise.resolve()
                      : Promise.reject(new Error('Saída deve ser depois da entrada')),
                }),
              ]}
            >
              <TimePicker format="HH:mm" />
            </Form.Item>
          </Flex>
          <Form.Item name="justificativa" label="Justificativa" rules={[{ required: true, message: 'Informe o motivo da correção' }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Flex>
  )
}
