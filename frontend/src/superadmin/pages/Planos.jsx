import { Alert, Flex, Form, Input, InputNumber, Switch, Tag } from 'antd'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { useData } from '../../data/DataContext.jsx'
import { moeda } from '../../utils/formatos.js'

// planos: só comercial. Os módulos de cada loja são escolhidos na própria loja.
export default function Planos() {
  const { planos, lojas } = useData()

  const colunas = [
    { title: 'Plano', dataIndex: 'nome' },
    { title: 'Descrição', dataIndex: 'descricao' },
    { title: 'Preço mensal', dataIndex: 'precoMensal', render: moeda },
    {
      title: 'Lojas ativas',
      key: 'lojas',
      align: 'center',
      render: (_, p) => lojas.itens.filter((l) => l.planoId === p.id && l.status === 'ativa').length,
    },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => (a ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>) },
  ]

  return (
    <Flex vertical gap={16}>
      <Alert
        type="info"
        showIcon
        title="O plano define só o valor cobrado. Os módulos (Serviços, Materiais, Controle de Tempo, Locais) são ligados loja a loja, em Lojas › Módulos, para esconder o que a loja não usa."
      />
      <CadastroTabela
        titulo="Plano"
        lista={planos}
        colunas={colunas}
        permitirExcluir={false}
        campos={
          <>
            <Form.Item name="nome" label="Nome" rules={[{ required: true }]}>
              <Input maxLength={80} />
            </Form.Item>
            <Form.Item name="descricao" label="Descrição">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Form.Item name="precoMensal" label="Preço mensal" rules={[{ required: true }]}>
              <InputNumber min={0} step={10} precision={2} decimalSeparator="," prefix="R$" style={{ width: 180 }} />
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
