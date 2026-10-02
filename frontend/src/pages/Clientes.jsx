import { Button, Col, Form, Input, Row } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { IconesCanais, SeletorCanais } from '../components/CanaisCliente.jsx'
import HistoricoCliente from '../components/HistoricoCliente.jsx'
import { usePainel } from '../components/base/usePainel.js'
import { canaisCliente } from '../data/mock.js'
import { dataBR, mascaraCpf, mascaraTelefone, nomeCompleto, soDigitos } from '../utils/formatos.js'

// Busca por nome, telefone ou CPF no mesmo campo (a recepção usa o que o cliente disser primeiro)
const textoBusca = (c) => `${nomeCompleto(c)} ${soDigitos(c.telefone)} ${soDigitos(c.cpf)} ${c.telefone ?? ''} ${c.cpf ?? ''}`

export default function Clientes() {
  const { clientes } = useData()
  const { pode } = useAcesso()
  const historico = usePainel()

  const colunas = [
    {
      title: 'Nome',
      key: 'nome',
      sorter: (a, b) => nomeCompleto(a).localeCompare(nomeCompleto(b)),
      // Clicar no nome abre o histórico do cliente
      render: (_, c) => (
        <button type="button" className="link-tabela" onClick={() => historico.abrir(c)} title="Ver histórico">
          {nomeCompleto(c)}
        </button>
      ),
    },
    { title: 'Telefone', dataIndex: 'telefone' },
    { title: 'CPF', dataIndex: 'cpf' },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Nascimento', dataIndex: 'nascimento', render: (d) => d && dataBR(d) },
    {
      title: 'Canais',
      dataIndex: 'canais',
      filters: Object.entries(canaisCliente).map(([value, text]) => ({ value, text })),
      onFilter: (v, c) => (c.canais ?? []).includes(v),
      render: (canais) => <IconesCanais canais={canais} />,
    },
  ]

  return (
    <>
      <CadastroTabela
        titulo="Clientes"
        descricao="Clique no nome para ver o histórico de atendimentos do cliente."
        item="cliente"
        lista={clientes}
        colunas={colunas}
        campoBusca={textoBusca}
        placeholderBusca="Buscar por nome, telefone ou CPF"
        somenteLeitura={!pode('clientes', 'escrita')}
        valoresNovo={{ canais: ['loja'] }}
        nomeRegistro={nomeCompleto}
        destaqueId={historico.destaqueId}
        acoesEdicao={(c, fechar) => (
          <Button
            type="text"
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => fechar(() => historico.abrir(c))}
          >
            Histórico
          </Button>
        )}
        campos={
          <>
            <h3 className="grupo-formulario">Dados pessoais</h3>
            {/* Nome e sobrenome separados: a loja chama o cliente pelo nome */}
            <Row gutter={12}>
              <Col xs={24} sm={10}>
                <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
                  <Input maxLength={60} autoComplete="off" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={14}>
                <Form.Item name="sobrenome" label="Sobrenome" rules={[{ required: true, whitespace: true, message: 'Informe o sobrenome' }]}>
                  <Input maxLength={100} autoComplete="off" />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={12}>
              <Col xs={24} sm={12}>
                <Form.Item name="cpf" label="CPF" normalize={mascaraCpf}>
                  <Input inputMode="numeric" placeholder="Opcional" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="nascimento" label="Nascimento">
                  <Input type="date" />
                </Form.Item>
              </Col>
            </Row>

            <h3 className="grupo-formulario">Contato</h3>
            <Form.Item
              name="telefone"
              label="Telefone"
              normalize={mascaraTelefone}
              validateTrigger="onBlur"
              rules={[
                { required: true, message: 'Informe o telefone' },
                { validator: (_, v) => (!v || soDigitos(v).length >= 10 ? Promise.resolve() : Promise.reject(new Error('Telefone incompleto: inclua o DDD'))) },
              ]}
            >
              <Input inputMode="tel" placeholder="(11) 99999-9999" />
            </Form.Item>
            <Form.Item name="email" label="E-mail" validateTrigger="onBlur" rules={[{ type: 'email', message: 'E-mail inválido. Confira o @ e o domínio' }]}>
              <Input type="email" placeholder="Opcional" />
            </Form.Item>
            <Form.Item name="canais" label="Canais em que o cliente está conectado">
              <SeletorCanais />
            </Form.Item>
          </>
        }
      />
      <HistoricoCliente clienteId={historico.registro?.id} open={historico.aberto} onClose={historico.fechar} />
    </>
  )
}
