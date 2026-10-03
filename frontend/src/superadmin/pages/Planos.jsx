import { Form, Input, InputNumber, Switch } from 'antd'
import { CreditCardOutlined } from '@ant-design/icons'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { EtiquetaSituacao } from '../../components/Etiquetas.jsx'
import { moeda } from '../../utils/formatos.js'
import { usePlanos } from '../usePlataforma.js'

// Planos: só comercial. Os módulos de cada loja são escolhidos na própria loja.
export default function Planos() {
  const planos = usePlanos()

  const colunas = [
    { title: 'Plano', dataIndex: 'nome', render: (n) => <strong>{n}</strong> },
    { title: 'Descrição', dataIndex: 'descricao', render: (d) => d ?? <span className="texto-apoio">—</span> },
    { title: 'Preço mensal', dataIndex: 'precoMensal', align: 'right', render: moeda },
    { title: 'Lojas ativas', dataIndex: 'lojasAtivas', align: 'right' },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => <EtiquetaSituacao ativo={a} /> },
  ]

  return (
    <CadastroTabela
      titulo="Planos"
      descricao="O plano define só o valor cobrado. Os módulos (Serviços, Materiais, Controle de tempo, Locais) são ligados loja a loja, na tela da loja."
      item="plano"
      lista={planos}
      colunas={colunas}
      valoresNovo={{ ativo: true }}
      textoExcluir="Só dá para excluir um plano sem lojas. Com lojas, inative o plano: ele deixa de aparecer para lojas novas."
      larguraTabela={720}
      iconeRegistro={() => <CreditCardOutlined />}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={80} />
          </Form.Item>
          <Form.Item name="descricao" label="Descrição">
            <Input.TextArea rows={2} maxLength={2000} placeholder="Para quem é este plano" />
          </Form.Item>
          <Form.Item name="precoMensal" label="Preço mensal" rules={[{ required: true, message: 'Informe o preço' }]}>
            <InputNumber min={0} max={99999999.99} step={10} precision={2} decimalSeparator="," prefix="R$" className="campo-valor" />
          </Form.Item>
          <Form.Item name="ativo" label="Disponível para novas lojas" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
