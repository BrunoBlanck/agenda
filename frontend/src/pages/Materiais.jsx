import { Col, Form, Input, InputNumber, Row, Select } from 'antd'
import { CheckCircleOutlined, InboxOutlined, WarningOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'

const categorias = ['Descartáveis', 'Medicamentos', 'Curativos', 'Instrumentais', 'Limpeza']

const colunas = [
  { title: 'Material', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
  { title: 'Categoria', dataIndex: 'categoria', filters: categorias.map((c) => ({ text: c, value: c })), onFilter: (v, r) => r.categoria === v },
  { title: 'Em estoque', dataIndex: 'quantidade', align: 'right', render: (q, r) => `${q} ${r.unidade ?? ''}` },
  { title: 'Mínimo', dataIndex: 'minimo', align: 'right', render: (q, r) => (q != null ? `${q} ${r.unidade ?? ''}` : '—') },
  {
    title: 'Situação',
    key: 'situacao',
    sorter: (a, b) => a.quantidade / (a.minimo || 1) - b.quantidade / (b.minimo || 1),
    render: (_, r) =>
      r.quantidade < r.minimo ? (
        <Etiqueta tom="marca" icone={<WarningOutlined />}>
          Repor
        </Etiqueta>
      ) : (
        <Etiqueta tom="sucesso" icone={<CheckCircleOutlined />}>
          Em dia
        </Etiqueta>
      ),
  },
]

export default function Materiais() {
  const { materiais } = useData()
  const { pode } = useAcesso()
  return (
    <CadastroTabela
      titulo="Materiais"
      descricao="Estoque da loja. Abaixo do mínimo, o material aparece como Repor aqui e no Início."
      item="material"
      lista={materiais}
      colunas={colunas}
      somenteLeitura={!pode('materiais', 'escrita')}
      iconeRegistro={() => <InboxOutlined />}
      campos={
        <>
          <h3 className="grupo-formulario">Material</h3>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={100} placeholder="Ex.: Luvas descartáveis (cx)" />
          </Form.Item>
          <Form.Item name="categoria" label="Categoria">
            <Select options={categorias.map((c) => ({ value: c, label: c }))} />
          </Form.Item>

          {/* Unidade primeiro: as quantidades são contadas nela */}
          <h3 className="grupo-formulario">Estoque</h3>
          <Row gutter={12}>
            <Col xs={8}>
              <Form.Item name="unidade" label="Unidade">
                <Input placeholder="un, cx, pct" />
              </Form.Item>
            </Col>
            <Col xs={8}>
              <Form.Item name="quantidade" label="Em estoque" rules={[{ required: true, message: 'Informe a quantidade' }]}>
                <InputNumber min={0} />
              </Form.Item>
            </Col>
            <Col xs={8}>
              <Form.Item name="minimo" label="Mínimo">
                <InputNumber min={0} />
              </Form.Item>
            </Col>
          </Row>
        </>
      }
    />
  )
}
