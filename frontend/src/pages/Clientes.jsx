import { App, Button, Col, Form, Input, Menu, Row, Switch } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useClientes } from '../data/useClientes.js'
import { MAPA_ERROS_CLIENTE } from '../data/api/clientes.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { IconesCanais, SeletorCanais } from '../components/CanaisCliente.jsx'
import HistoricoCliente from '../components/HistoricoCliente.jsx'
import { EtiquetaSituacao } from '../components/Etiquetas.jsx'
import { usePainel } from '../components/base/usePainel.js'
import { canaisCliente } from '../data/dominio.js'
import { dataBR, mascaraCpf, mascaraTelefone, nomeCompleto, soDigitos } from '../utils/formatos.js'

const opcoesSituacao = { true: 'Ativos', false: 'Inativos' }

// Filtro de coluna que vai para a API (a tabela é paginada no servidor: filtrar só a página na tela
// esconderia clientes das outras páginas). Um valor por vez, como a API aceita.
function filtroNoServidor(opcoes, valor, mudar) {
  return {
    filters: Object.entries(opcoes).map(([value, text]) => ({ value, text })),
    filteredValue: valor == null ? null : [String(valor)],
    filterMultiple: false,
    filterDropdown: ({ close }) => (
      <Menu
        selectable
        selectedKeys={[valor == null ? '' : String(valor)]}
        items={[{ key: '', label: 'Todos' }, ...Object.entries(opcoes).map(([key, label]) => ({ key, label }))]}
        onClick={({ key }) => {
          mudar(key === '' ? null : key)
          close()
        }}
      />
    ),
  }
}

// Exclusão recusada porque o cliente tem agendamentos: a tela já ofereceu inativar, então o
// CadastroTabela não mostra o erro de novo (erro de cancelamento é ignorado pelo useTratarErro)
const jaTratado = () => new DOMException('Exclusão trocada por inativação', 'AbortError')

export default function Clientes() {
  const { pode } = useAcesso()
  const { message, modal } = App.useApp()
  const tratarErro = useTratarErro()
  const clientes = useClientes({ ativo: pode('clientes') })
  const historico = usePainel()

  const oferecerInativar = (cliente, motivo) =>
    modal.confirm({
      title: `Inativar ${nomeCompleto(cliente)}?`,
      content: `${motivo} Inativo, ele não aparece para novos agendamentos, mas o histórico continua.`,
      okText: 'Inativar cliente',
      cancelText: 'Cancelar',
      onOk: async () => {
        try {
          await clientes.salvar({ ...cliente, ativo: false }, cliente)
          message.success('Cliente inativado.')
        } catch (e) {
          tratarErro(e, { aoNaoEncontrado: clientes.recarregar })
        }
      },
    })

  const lista = {
    ...clientes,
    excluir: async (cliente) => {
      try {
        await clientes.excluir(cliente)
      } catch (e) {
        if (e?.status !== 409 || !cliente.ativo) throw e
        oferecerInativar(cliente, e.mensagem)
        throw jaTratado()
      }
    },
  }

  const colunas = [
    {
      title: 'Nome',
      key: 'nome',
      // A API já devolve em ordem alfabética; clicar no nome abre o histórico do cliente
      render: (_, c) => (
        <button type="button" className="link-tabela" onClick={() => historico.abrir(c)} title="Ver histórico">
          {nomeCompleto(c)}
        </button>
      ),
    },
    { title: 'Telefone', dataIndex: 'telefone', render: (t) => t || '—' },
    { title: 'CPF', dataIndex: 'cpf', render: (cpf) => cpf ?? '—' },
    { title: 'E-mail', dataIndex: 'email', render: (email) => email ?? '—' },
    { title: 'Nascimento', dataIndex: 'nascimento', render: (d) => (d ? dataBR(d) : '—') },
    {
      title: 'Canais',
      dataIndex: 'canais',
      ...filtroNoServidor(canaisCliente, clientes.filtros.canal, (v) => clientes.filtrar('canal', v)),
      render: (canais) => <IconesCanais canais={canais} />,
    },
    {
      title: 'Situação',
      dataIndex: 'ativo',
      ...filtroNoServidor(opcoesSituacao, clientes.filtros.ativo, (v) => clientes.filtrar('ativo', v == null ? null : v === 'true')),
      render: (ativo) => <EtiquetaSituacao ativo={ativo} />,
    },
  ]

  return (
    <>
      <CadastroTabela
        titulo="Clientes"
        descricao="Clique no nome para ver o histórico de atendimentos do cliente."
        item="cliente"
        lista={lista}
        colunas={colunas}
        placeholderBusca="Buscar por nome, telefone ou CPF"
        larguraTabela={1040}
        somenteLeitura={!pode('clientes', 'escrita')}
        valoresNovo={{ canais: ['loja'], ativo: true }}
        nomeRegistro={nomeCompleto}
        destaqueId={historico.destaqueId}
        mapaErros={MAPA_ERROS_CLIENTE}
        textoExcluir="Só dá para excluir cliente sem agendamentos. Com agendamentos, ele pode ser inativado."
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
                <Form.Item
                  name="cpf"
                  label="CPF"
                  normalize={mascaraCpf}
                  validateTrigger="onBlur"
                  rules={[
                    {
                      validator: (_, v) =>
                        !v || soDigitos(v).length === 11 ? Promise.resolve() : Promise.reject(new Error('CPF incompleto: são 11 dígitos')),
                    },
                  ]}
                >
                  <Input inputMode="numeric" placeholder="Opcional" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="nascimento" label="Nascimento">
                  <Input type="date" min="1900-01-01" />
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

            <h3 className="grupo-formulario">Mais informações</h3>
            <Form.Item name="observacoes" label="Observações" extra="Aparecem no histórico do cliente (ex.: alergias, preferências).">
              <Input.TextArea rows={3} maxLength={2000} />
            </Form.Item>
            <Form.Item name="ativo" label="Ativo" valuePropName="checked" extra="Inativo não aparece para novos agendamentos. O histórico continua.">
              <Switch />
            </Form.Item>
          </>
        }
      />
      <HistoricoCliente clienteId={historico.registro?.id} open={historico.aberto} onClose={historico.fechar} />
    </>
  )
}
