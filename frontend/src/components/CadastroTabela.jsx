import { useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Flex, Popconfirm, Tag, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import UltimaAlteracao from './UltimaAlteracao.jsx'

// Tela genérica de cadastro: busca + tabela + modal de formulário.
// somenteLeitura: perfil com nível "leitura" (sem criar, editar ou excluir).
// validar(valores, item): regra extra antes de salvar; retorna a mensagem de erro ou nada.
// campoBusca: campo (ou função que recebe o item) usado na busca.
// textoNovo: texto do botão de criar (padrão "Novo <titulo>"), para nomes femininos ou definidos pela loja.
export default function CadastroTabela({
  titulo,
  textoNovo = `Novo ${titulo.toLowerCase()}`,
  lista,
  colunas,
  campos,
  campoBusca = 'nome',
  somenteLeitura = false,
  permitirExcluir = true,
  validar,
  expandable,
}) {
  const [busca, setBusca] = useState('')
  const [editando, setEditando] = useState(null) // null = fechado, {} = novo, item = edição
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()

  const abrir = (item) => {
    setEditando(item)
    form.resetFields()
    form.setFieldsValue(item)
  }

  const salvar = async () => {
    const valores = await form.validateFields()
    const erro = validar?.(valores, editando)
    if (erro) {
      msg.error(erro)
      return
    }
    if (editando.id) lista.atualizar(editando.id, valores)
    else lista.adicionar(valores)
    setEditando(null)
  }

  const textoBusca = typeof campoBusca === 'function' ? campoBusca : (i) => i[campoBusca]
  const dados = lista.itens.filter((i) =>
    String(textoBusca(i) ?? '').toLowerCase().includes(busca.toLowerCase()),
  )

  const colunaAcoes = {
    title: 'Ações',
    key: 'acoes',
    width: 110,
    render: (_, item) => (
      <Flex gap={4}>
        <Button type="text" icon={<EditOutlined />} onClick={() => abrir(item)} />
        {permitirExcluir && (
          <Popconfirm title="Remover este registro?" onConfirm={() => lista.remover(item.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        )}
      </Flex>
    ),
  }

  return (
    <Card>
      {contextHolder}
      <Flex justify="space-between" gap={16} style={{ marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Buscar..."
          allowClear
          style={{ maxWidth: 300 }}
          onChange={(e) => setBusca(e.target.value)}
        />
        {somenteLeitura ? (
          <Tag color="blue">Somente leitura</Tag>
        ) : (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => abrir({})}>
            {textoNovo}
          </Button>
        )}
      </Flex>
      <Table
        rowKey="id"
        columns={somenteLeitura ? colunas : [...colunas, colunaAcoes]}
        dataSource={dados}
        scroll={{ x: true }}
        expandable={expandable}
      />
      <Modal
        title={editando?.id ? `Editar ${titulo.toLowerCase()}` : textoNovo}
        open={!!editando}
        onOk={salvar}
        onCancel={() => setEditando(null)}
        okText="Salvar"
      >
        <Form form={form} layout="vertical">
          {campos}
        </Form>
        <UltimaAlteracao item={editando} />
      </Modal>
    </Card>
  )
}
