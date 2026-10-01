import { useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Flex, Popconfirm } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'

// Tela genérica de cadastro: busca + tabela + modal de formulário.
export default function CadastroTabela({ titulo, lista, colunas, campos, campoBusca = 'nome' }) {
  const [busca, setBusca] = useState('')
  const [editando, setEditando] = useState(null) // null = fechado, {} = novo, item = edição
  const [form] = Form.useForm()

  const abrir = (item) => {
    setEditando(item)
    form.resetFields()
    form.setFieldsValue(item)
  }

  const salvar = async () => {
    const valores = await form.validateFields()
    if (editando.id) lista.atualizar(editando.id, valores)
    else lista.adicionar(valores)
    setEditando(null)
  }

  const dados = lista.itens.filter((i) =>
    String(i[campoBusca] ?? '').toLowerCase().includes(busca.toLowerCase()),
  )

  const colunaAcoes = {
    title: 'Ações',
    key: 'acoes',
    width: 110,
    render: (_, item) => (
      <Flex gap={4}>
        <Button type="text" icon={<EditOutlined />} onClick={() => abrir(item)} />
        <Popconfirm title="Remover este registro?" onConfirm={() => lista.remover(item.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Flex>
    ),
  }

  return (
    <Card>
      <Flex justify="space-between" gap={16} style={{ marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Buscar..."
          allowClear
          style={{ maxWidth: 300 }}
          onChange={(e) => setBusca(e.target.value)}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => abrir({})}>
          Novo {titulo.toLowerCase()}
        </Button>
      </Flex>
      <Table rowKey="id" columns={[...colunas, colunaAcoes]} dataSource={dados} scroll={{ x: true }} />
      <Modal
        title={editando?.id ? `Editar ${titulo.toLowerCase()}` : `Novo ${titulo.toLowerCase()}`}
        open={!!editando}
        onOk={salvar}
        onCancel={() => setEditando(null)}
        okText="Salvar"
      >
        <Form form={form} layout="vertical">
          {campos}
        </Form>
      </Modal>
    </Card>
  )
}
