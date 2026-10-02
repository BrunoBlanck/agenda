import { useState } from 'react'
import { Button, DatePicker, Flex, Form, Input, Modal, Popconfirm, Select, Table, Tag, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { bloqueioDaLoja } from '../../data/horarios.js'

const FORMATO = 'YYYY-MM-DD HH:mm'

// Bloqueios, folgas e feriados (2.6) que atingem o perfil: os da loja inteira, os do perfil
// e os de cada funcionário dele (férias, consulta médica...)
export default function BloqueiosPerfil({ perfil, somenteLeitura }) {
  const { funcionarios, bloqueios } = useData()
  const [aberto, setAberto] = useState(false)
  const [form] = Form.useForm()

  const doPerfil = funcionarios.itens.filter((f) => f.perfilId === perfil.id)
  const idsDoPerfil = doPerfil.map((f) => f.id)
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'

  const lista = bloqueios.itens
    .filter((b) => bloqueioDaLoja(b) || b.perfilId === perfil.id || idsDoPerfil.includes(b.funcionarioId))
    .sort((a, b) => a.inicio.localeCompare(b.inicio))

  // "Aplica a": loja, perfil ou f<id> (um funcionário do perfil)
  const opcoesAlvo = [
    { value: 'perfil', label: `Todo o perfil ${perfil.nome}` },
    ...doPerfil.filter((f) => f.ativo).map((f) => ({ value: `f${f.id}`, label: f.nome })),
    { value: 'loja', label: 'Loja inteira (ex.: feriado)' },
  ]

  const salvar = async () => {
    const v = await form.validateFields()
    bloqueios.adicionar({
      perfilId: v.alvo === 'perfil' ? perfil.id : null,
      funcionarioId: v.alvo.startsWith('f') ? Number(v.alvo.slice(1)) : null,
      inicio: v.periodo[0].format(FORMATO),
      fim: v.periodo[1].format(FORMATO),
      motivo: v.motivo,
    })
    setAberto(false)
  }

  const colunas = [
    {
      title: 'Quem',
      key: 'quem',
      render: (_, b) =>
        bloqueioDaLoja(b) ? (
          <Tag color="purple">Loja inteira</Tag>
        ) : b.perfilId != null ? (
          <Tag color="blue">Todo o perfil</Tag>
        ) : (
          nomeFunc(b.funcionarioId)
        ),
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
        <Popconfirm
          title="Remover bloqueio?"
          description={bloqueioDaLoja(b) ? 'Ele vale para a loja inteira, não só para este perfil.' : undefined}
          onConfirm={() => bloqueios.remover(b.id)}
        >
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ].filter(Boolean)

  return (
    <>
      <Flex justify="space-between" align="center" gap={12} wrap style={{ marginBottom: 12 }}>
        <Typography.Text type="secondary">Mostra os bloqueios da loja inteira, do perfil e de cada funcionário dele.</Typography.Text>
        {!somenteLeitura && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              form.resetFields()
              setAberto(true)
            }}
          >
            Novo bloqueio
          </Button>
        )}
      </Flex>
      <Table rowKey="id" size="small" pagination={false} columns={colunas} dataSource={lista} scroll={{ x: true }} />
      <Modal title="Novo bloqueio" open={aberto} onOk={salvar} onCancel={() => setAberto(false)} okText="Salvar">
        <Form form={form} layout="vertical" initialValues={{ alvo: 'perfil' }}>
          <Form.Item name="alvo" label="Aplica a" rules={[{ required: true }]}>
            <Select options={opcoesAlvo} />
          </Form.Item>
          <Form.Item name="periodo" label="Período" rules={[{ required: true }]}>
            <DatePicker.RangePicker showTime={{ format: 'HH:mm', minuteStep: 15 }} format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="motivo" label="Motivo">
            <Input maxLength={150} placeholder="Férias, folga, feriado..." />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
