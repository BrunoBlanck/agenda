import { Alert, Flex, Form, Input, Switch, Tag } from 'antd'
import dayjs from 'dayjs'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { useData } from '../../data/DataContext.jsx'

// superadmin_usuarios: só as contas de quem administra a plataforma.
// Funcionários das lojas são cadastrados na própria loja.
export default function Usuarios() {
  const { superadmins } = useData()

  const colunas = [
    { title: 'Nome', dataIndex: 'nome' },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Último acesso', dataIndex: 'ultimoLoginEm', render: (d) => (d ? dayjs(d).format('DD/MM/YYYY HH:mm') : 'Nunca entrou') },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => (a ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>) },
  ]

  return (
    <Flex vertical gap={16}>
      <Alert
        type="info"
        showIcon
        title="Contas com acesso ao painel SUPERADMIN. Os usuários das lojas (funcionários) são cadastrados dentro de cada loja."
      />
      <CadastroTabela
        titulo="Usuário admin"
        lista={superadmins}
        colunas={colunas}
        permitirExcluir={false}
        validar={(v, item) =>
          !v.ativo && item.id && superadmins.itens.filter((s) => s.ativo && s.id !== item.id).length === 0
            ? 'A plataforma precisa de pelo menos um usuário admin ativo.'
            : undefined
        }
        campos={
          <>
            <Form.Item name="nome" label="Nome" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item
              name="email"
              label="E-mail"
              rules={[{ required: true }, { type: 'email' }]}
              extra="Recebe um e-mail para definir a senha."
            >
              <Input />
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
