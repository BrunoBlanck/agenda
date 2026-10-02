import { useState } from 'react'
import { Col, Form, Input, Row, Tooltip, Typography } from 'antd'
import dayjs from 'dayjs'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { IconesCanais, SeletorCanais } from '../components/CanaisCliente.jsx'
import HistoricoCliente from '../components/HistoricoCliente.jsx'
import { canaisCliente } from '../data/mock.js'
import { nomeCompleto } from '../utils/formatos.js'

const colunas = [
  {
    title: 'Nome',
    key: 'nome',
    sorter: (a, b) => nomeCompleto(a).localeCompare(nomeCompleto(b)),
    render: (_, c) => nomeCompleto(c),
  },
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
  const [historicoDe, setHistoricoDe] = useState(null)

  // Clicar no nome abre o histórico do cliente
  const colunasComHistorico = [
    {
      ...colunas[0],
      render: (_, c) => (
        <Tooltip title="Ver histórico">
          <Typography.Link onClick={() => setHistoricoDe(c.id)} style={{ whiteSpace: 'nowrap' }}>
            {nomeCompleto(c)}
          </Typography.Link>
        </Tooltip>
      ),
    },
    ...colunas.slice(1),
  ]

  return (
    <>
      <CadastroTabela
        titulo="Cliente"
        lista={clientes}
        colunas={colunasComHistorico}
        campoBusca={nomeCompleto}
        somenteLeitura={!pode('clientes', 'escrita')}
        campos={
          <>
            {/* Nome e sobrenome separados: a loja chama o cliente pelo nome */}
            <Row gutter={12}>
              <Col span={10}>
                <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
                  <Input maxLength={60} />
                </Form.Item>
              </Col>
              <Col span={14}>
                <Form.Item name="sobrenome" label="Sobrenome" rules={[{ required: true, whitespace: true, message: 'Informe o sobrenome' }]}>
                  <Input maxLength={100} />
                </Form.Item>
              </Col>
            </Row>
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
      <HistoricoCliente clienteId={historicoDe} open={!!historicoDe} onClose={() => setHistoricoDe(null)} />
    </>
  )
}
