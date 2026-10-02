import { Alert, Checkbox, Flex, Form, Input, InputNumber, Switch, Tag } from 'antd'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { moeda } from '../../utils/formatos.js'
import { comAuditoria } from '../usePlataforma.js'

const opcionais = modulos.filter((m) => m.opcional)
const limite = (v) => (v == null ? 'Ilimitado' : v)

export default function Planos() {
  const { planos, lojas, registrarAuditoria } = useData()

  const colunas = [
    { title: 'Plano', dataIndex: 'nome' },
    { title: 'Preço mensal', dataIndex: 'precoMensal', render: moeda },
    { title: 'Funcionários', dataIndex: 'limiteFuncionarios', render: limite },
    { title: 'Agendamentos/mês', dataIndex: 'limiteAgendamentosMes', render: limite },
    {
      title: 'Módulos sugeridos',
      dataIndex: 'modulos',
      render: (lista = []) => (
        <Flex gap={4} wrap>
          {opcionais.filter((m) => lista.includes(m.codigo)).map((m) => <Tag key={m.codigo} color="cyan">{m.nome}</Tag>)}
        </Flex>
      ),
    },
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
        title="Os módulos do plano só servem de sugestão quando a loja é criada. Depois disso, os módulos de cada loja são ligados e desligados na própria loja."
      />
      <CadastroTabela
        titulo="Plano"
        lista={comAuditoria(planos, registrarAuditoria, 'plano')}
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
            <Flex gap={16}>
              <Form.Item name="limiteFuncionarios" label="Limite de funcionários" extra="Vazio = ilimitado">
                <InputNumber min={1} style={{ width: 180 }} />
              </Form.Item>
              <Form.Item name="limiteAgendamentosMes" label="Agendamentos por mês" extra="Vazio = ilimitado">
                <InputNumber min={1} style={{ width: 180 }} />
              </Form.Item>
            </Flex>
            <Form.Item name="modulos" label="Módulos sugeridos" initialValue={[]}>
              <Checkbox.Group options={opcionais.map((m) => ({ value: m.codigo, label: m.nome }))} />
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
