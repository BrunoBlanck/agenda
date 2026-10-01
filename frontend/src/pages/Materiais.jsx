import { Form, Input, InputNumber, Select, Tag } from 'antd'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'

const categorias = ['Descartáveis', 'Medicamentos', 'Curativos', 'Instrumentais', 'Limpeza']

const colunas = [
  { title: 'Material', dataIndex: 'nome' },
  { title: 'Categoria', dataIndex: 'categoria' },
  { title: 'Quantidade', dataIndex: 'quantidade', render: (q, r) => `${q} ${r.unidade ?? ''}` },
  { title: 'Estoque mínimo', dataIndex: 'minimo' },
  {
    title: 'Situação',
    key: 'situacao',
    render: (_, r) => (r.quantidade < r.minimo ? <Tag color="red">Repor</Tag> : <Tag color="green">OK</Tag>),
  },
]

export default function Materiais() {
  const { materiais } = useData()
  return (
    <CadastroTabela
      titulo="Material"
      lista={materiais}
      colunas={colunas}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="categoria" label="Categoria">
            <Select options={categorias.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="quantidade" label="Quantidade" rules={[{ required: true }]}><InputNumber min={0} /></Form.Item>
          <Form.Item name="unidade" label="Unidade"><Input placeholder="un, cx, pct..." /></Form.Item>
          <Form.Item name="minimo" label="Estoque mínimo"><InputNumber min={0} /></Form.Item>
        </>
      }
    />
  )
}
