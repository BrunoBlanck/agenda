import { Form, Input, Select, Switch, Tag } from 'antd'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'

const cargos = ['Dentista', 'Médico(a)', 'Fisioterapeuta', 'Enfermeiro(a)', 'Recepcionista', 'Administrador']

const colunas = [
  { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
  { title: 'Cargo', dataIndex: 'cargo', filters: cargos.map((c) => ({ text: c, value: c })), onFilter: (v, r) => r.cargo === v },
  { title: 'E-mail', dataIndex: 'email' },
  { title: 'Telefone', dataIndex: 'telefone' },
  {
    title: 'Situação',
    dataIndex: 'ativo',
    render: (ativo) => (ativo ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>),
  },
]

export default function Funcionarios() {
  const { funcionarios } = useData()
  return (
    <CadastroTabela
      titulo="Funcionário"
      lista={funcionarios}
      colunas={colunas}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="cargo" label="Cargo" rules={[{ required: true }]}>
            <Select options={cargos.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="email" label="E-mail (login)" rules={[{ required: true }]}><Input type="email" /></Form.Item>
          <Form.Item name="telefone" label="Telefone"><Input /></Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked" initialValue={true}><Switch /></Form.Item>
        </>
      }
    />
  )
}
