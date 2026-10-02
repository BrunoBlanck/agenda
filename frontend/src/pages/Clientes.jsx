import { Form, Input } from 'antd'
import dayjs from 'dayjs'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { IconesCanais, SeletorCanais } from '../components/CanaisCliente.jsx'
import { canaisCliente } from '../data/mock.js'

const colunas = [
  { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
  { title: 'CPF', dataIndex: 'cpf' },
  { title: 'Telefone', dataIndex: 'telefone' },
  { title: 'E-mail', dataIndex: 'email' },
  { title: 'Nascimento', dataIndex: 'nascimento', render: (d) => d && dayjs(d).format('DD/MM/YYYY') },
  {
    title: 'Canais',
    dataIndex: 'canais',
    filters: Object.entries(canaisCliente).map(([value, text]) => ({ value, text })),
    onFilter: (v, c) => (c.canais ?? []).includes(v),
    render: (canais) => <IconesCanais canais={canais} />,
  },
]

export default function Clientes() {
  const { clientes } = useData()
  const { pode } = useAcesso()
  return (
    <CadastroTabela
      titulo="Cliente"
      lista={clientes}
      colunas={colunas}
      somenteLeitura={!pode('clientes', 'escrita')}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="cpf" label="CPF"><Input /></Form.Item>
          <Form.Item name="telefone" label="Telefone" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="email" label="E-mail"><Input type="email" /></Form.Item>
          <Form.Item name="nascimento" label="Data de nascimento"><Input type="date" /></Form.Item>
          <Form.Item name="canais" label="Canais em que o cliente está conectado" initialValue={['loja']}>
            <SeletorCanais />
          </Form.Item>
        </>
      }
    />
  )
}
