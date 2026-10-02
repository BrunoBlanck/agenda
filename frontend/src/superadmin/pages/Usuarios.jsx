import { Form, Input, Switch, Tag } from 'antd'
import dayjs from 'dayjs'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { useData } from '../../data/DataContext.jsx'
import { comAuditoria } from '../usePlataforma.js'

// superadmin_usuarios: tabela separada dos funcionários das lojas
export default function Usuarios() {
  const { superadmins, registrarAuditoria } = useData()

  const colunas = [
    { title: 'Nome', dataIndex: 'nome' },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Último acesso', dataIndex: 'ultimoLoginEm', render: (d) => (d ? dayjs(d).format('DD/MM/YYYY HH:mm') : 'Nunca entrou') },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => (a ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>) },
  ]

  return (
    <CadastroTabela
      titulo="Usuário"
      lista={comAuditoria(superadmins, registrarAuditoria, 'superadmin')}
      colunas={colunas}
      permitirExcluir={false}
      validar={(v, item) =>
        !v.ativo && item.id && superadmins.itens.filter((s) => s.ativo && s.id !== item.id).length === 0
          ? 'A plataforma precisa de pelo menos um superadmin ativo.'
          : undefined
      }
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="E-mail" rules={[{ required: true }, { type: 'email' }]} extra="Recebe um e-mail para definir a senha.">
            <Input />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
