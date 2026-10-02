import { Alert, Flex, Form, Input, Switch, Tag } from 'antd'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { useData } from '../../data/DataContext.jsx'
import { comAuditoria } from '../usePlataforma.js'

export default function Tipos() {
  const { tipos, lojas, registrarAuditoria } = useData()

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
    { title: 'Código', dataIndex: 'codigo', render: (c) => <code>{c}</code> },
    { title: 'Descrição', dataIndex: 'descricao' },
    { title: 'Lojas', key: 'lojas', align: 'center', render: (_, t) => lojas.itens.filter((l) => l.tipo === t.codigo).length },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => (a ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>) },
  ]

  return (
    <Flex vertical gap={16}>
      <Alert
        type="info"
        showIcon
        title="O tipo não libera nem bloqueia nada no painel da loja. Ele será usado só no futuro site do consumidor final (ex.: em uma Escola, “Profissional” vira “Professor”)."
      />
      <CadastroTabela
        titulo="Tipo"
        lista={comAuditoria(tipos, registrarAuditoria, 'tipo_loja')}
        colunas={colunas}
        permitirExcluir={false}
        validar={(v, item) =>
          tipos.itens.some((t) => t.id !== item.id && t.codigo === v.codigo) ? 'Já existe um tipo com esse código.' : undefined
        }
        campos={
          <>
            <Form.Item name="nome" label="Nome" rules={[{ required: true }]}>
              <Input maxLength={60} />
            </Form.Item>
            <Form.Item
              name="codigo"
              label="Código"
              rules={[{ required: true }, { pattern: /^[a-z_]+$/, message: 'Use letras minúsculas e _' }]}
              extra="Identificador usado pelo sistema (ex.: clinica). Evite mudar depois de criado."
            >
              <Input maxLength={30} />
            </Form.Item>
            <Form.Item name="descricao" label="Descrição">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Form.Item name="ativo" label="Ativo" valuePropName="checked" initialValue={true}>
              <Switch />
            </Form.Item>
          </>
        }
      />
    </Flex>
  )
}
