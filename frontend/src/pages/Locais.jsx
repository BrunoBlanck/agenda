import { Card, Flex, Form, Input, Select, Switch, Tag, Button, Typography, Table, Empty, message } from 'antd'
import { LinkOutlined, SaveOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { tiposLocal } from '../data/mock.js'
import { rotulosLocal } from '../data/locais.js'
import { statusAgendamento } from '../data/mock.js'
import { inativo } from '../components/agenda/util.js'
import dayjs from 'dayjs'

// Como a loja chama os locais (estrutura.md, 2.21). Muda o menu e os textos do painel.
function RotuloLocais({ loja, somenteLeitura }) {
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()
  const rotulos = rotulosLocal(loja.dados)

  const salvar = async () => {
    const v = await form.validateFields()
    loja.atualizar({ rotuloLocal: v.singular.trim(), rotuloLocalPlural: v.plural.trim() })
    msg.success('Nome atualizado.')
  }

  return (
    <Card size="small">
      {contextHolder}
      <Form form={form} layout="inline" initialValues={rotulos} disabled={somenteLeitura} style={{ rowGap: 8 }}>
        <Typography.Text style={{ marginRight: 12, lineHeight: '32px' }}>Como a loja chama seus locais:</Typography.Text>
        <Form.Item name="singular" rules={[{ required: true, whitespace: true, message: 'Informe o singular' }]}>
          <Input placeholder="Sala" style={{ width: 150 }} maxLength={40} />
        </Form.Item>
        <Form.Item name="plural" rules={[{ required: true, whitespace: true, message: 'Informe o plural' }]}>
          <Input placeholder="Salas" style={{ width: 150 }} maxLength={40} />
        </Form.Item>
        {!somenteLeitura && (
          <Button icon={<SaveOutlined />} onClick={salvar}>
            Salvar
          </Button>
        )}
      </Form>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        Ex.: Sala (escola), Cadeira (barbearia), Maca (estética), Consultório (clínica).
      </Typography.Text>
    </Card>
  )
}

export default function Locais() {
  const { locais, servicos, loja, agendamentos, clientes, funcionarios } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const somenteLeitura = !pode('locais', 'escrita')
  const { singular } = rotulosLocal(loja.dados)

  // Serviços que citam o local explicitamente; os sem vínculo aceitam qualquer local
  const servicosDoLocal = (id) => servicos.itens.filter((s) => s.localIds?.includes(id))

  // Agendamentos do local: próximos primeiro (do mais cedo ao mais tarde), depois os passados
  const hoje = dayjs().format('YYYY-MM-DD')
  const agendamentosDoLocal = (id) => {
    const lista = agendamentos.itens.filter((a) => a.localId === id)
    const chave = (a) => `${a.data} ${a.hora}`
    const futuros = lista.filter((a) => a.data >= hoje).sort((a, b) => chave(a).localeCompare(chave(b)))
    const passados = lista.filter((a) => a.data < hoje).sort((a, b) => chave(b).localeCompare(chave(a)))
    return [...futuros, ...passados]
  }
  const proximos = (id) => agendamentosDoLocal(id).filter((a) => a.data >= hoje && !inativo(a)).length
  const nome = (lista, id) => lista.itens.find((i) => i.id === id)?.nome ?? '—'

  const colunasAgendamentos = [
    { title: 'Data', dataIndex: 'data', render: (d) => dayjs(d).format('DD/MM/YYYY') },
    { title: 'Hora', dataIndex: 'hora' },
    { title: 'Cliente', dataIndex: 'clienteId', render: (id) => nome(clientes, id) },
    { title: 'Profissional', dataIndex: 'funcionarioId', render: (id) => nome(funcionarios, id) },
    moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: (id) => nome(servicos, id) },
    {
      title: 'Status',
      dataIndex: 'status',
      render: (st) => <Tag color={statusAgendamento[st]?.color}>{statusAgendamento[st]?.label}</Tag>,
    },
  ].filter(Boolean)

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
    {
      title: 'Tipo',
      dataIndex: 'tipo',
      filters: Object.entries(tiposLocal).map(([value, t]) => ({ value, text: t.label })),
      onFilter: (v, l) => l.tipo === v,
      render: (t) => <Tag color={tiposLocal[t]?.color}>{tiposLocal[t]?.label}</Tag>,
    },
    {
      title: 'Descrição / link',
      key: 'detalhe',
      render: (_, l) =>
        l.tipo === 'online' && l.linkPadrao ? (
          <a href={l.linkPadrao} target="_blank" rel="noreferrer">
            <LinkOutlined /> {l.linkPadrao}
          </a>
        ) : (
          l.descricao
        ),
    },
    moduloAtivo('servicos') && {
      title: 'Serviços vinculados',
      key: 'servicos',
      render: (_, l) => {
        const lista = servicosDoLocal(l.id)
        return lista.length ? lista.map((s) => <Tag key={s.id}>{s.nome}</Tag>) : <Typography.Text type="secondary">—</Typography.Text>
      },
    },
    {
      title: 'Agendamentos',
      key: 'agendamentos',
      render: (_, l) => {
        const n = proximos(l.id)
        return n ? <Tag color="blue">{n} {n === 1 ? 'próximo' : 'próximos'}</Tag> : <Typography.Text type="secondary">Nenhum próximo</Typography.Text>
      },
    },
    {
      title: 'Situação',
      dataIndex: 'ativo',
      render: (ativo) => (ativo ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>),
    },
  ].filter(Boolean)

  return (
    <Flex vertical gap={16}>
      <RotuloLocais loja={loja} somenteLeitura={somenteLeitura} />
      <CadastroTabela
        titulo={singular}
        textoNovo={`Adicionar ${singular.toLowerCase()}`}
        lista={locais}
        colunas={colunas}
        somenteLeitura={somenteLeitura}
        permitirExcluir={false}
        expandable={{
          expandedRowRender: (l) => {
            const lista = agendamentosDoLocal(l.id)
            return lista.length ? (
              <Table rowKey="id" size="small" columns={colunasAgendamentos} dataSource={lista} pagination={{ pageSize: 5, hideOnSinglePage: true }} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nenhum agendamento neste local" />
            )
          },
        }}
        validar={(v, item) =>
          locais.itens.some((l) => l.id !== item?.id && l.nome.trim().toLowerCase() === v.nome.trim().toLowerCase())
            ? `Já existe um local chamado "${v.nome}".`
            : null
        }
        campos={
          <>
            <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true }]}>
              <Input placeholder="Ex.: Sala 101, Cadeira 2, Zoom Prof. Ana" maxLength={80} />
            </Form.Item>
            <Form.Item name="tipo" label="Tipo" initialValue="presencial" rules={[{ required: true }]}>
              <Select options={Object.entries(tiposLocal).map(([value, t]) => ({ value, label: t.label }))} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(a, b) => a.tipo !== b.tipo}>
              {({ getFieldValue }) =>
                getFieldValue('tipo') === 'online' ? (
                  <Form.Item
                    name="linkPadrao"
                    label="Link fixo da reunião"
                    extra="Opcional. Se o link mudar a cada atendimento, informe no próprio agendamento."
                    rules={[{ type: 'url', message: 'Informe um link válido (https://...)' }]}
                  >
                    <Input placeholder="https://meet.google.com/..." />
                  </Form.Item>
                ) : (
                  <Form.Item name="descricao" label="Descrição">
                    <Input.TextArea rows={2} placeholder="Ex.: piano de cauda, isolamento acústico" />
                  </Form.Item>
                )
              }
            </Form.Item>
            <Form.Item
              name="ativo"
              label="Ativo"
              valuePropName="checked"
              initialValue={true}
              extra="Inativo não aparece em novos agendamentos, mas o histórico é mantido."
            >
              <Switch />
            </Form.Item>
          </>
        }
      />
    </Flex>
  )
}
