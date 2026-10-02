import { App, Button, Form, Input, Select, Switch } from 'antd'
import { EnvironmentOutlined, LinkOutlined, VideoCameraOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import { EtiquetaSituacao, EtiquetaStatus, EtiquetaTipoLocal } from '../components/Etiquetas.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useNomes } from '../data/useNomes.js'
import { tiposLocal } from '../data/mock.js'
import { rotulosLocal } from '../data/locais.js'
import { inativo } from '../components/agenda/util.js'
import { dataBR, horaCurta, plural } from '../utils/formatos.js'
import dayjs from 'dayjs'

// Como a loja chama os locais (estrutura.md, 2.21). Muda o menu e os textos do painel.
function RotuloLocais({ loja, somenteLeitura }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()

  const salvar = (v) => {
    loja.atualizar({ rotuloLocal: v.singular.trim(), rotuloLocalPlural: v.plural.trim() })
    message.success('Nome dos locais salvo.')
  }

  return (
    <Secao
      titulo="Como a loja chama os locais"
      descricao="Muda o nome no menu e nos formulários. Ex.: Sala (escola), Cadeira (barbearia), Maca (estética), Consultório (clínica)."
    >
      <Form form={form} layout="inline" initialValues={rotulosLocal(loja.dados)} disabled={somenteLeitura} onFinish={salvar} colon={false} className="form-em-linha">
        <Form.Item name="singular" label="Um" rules={[{ required: true, whitespace: true, message: 'Informe o singular' }]}>
          <Input placeholder="Sala" maxLength={40} />
        </Form.Item>
        <Form.Item name="plural" label="Vários" rules={[{ required: true, whitespace: true, message: 'Informe o plural' }]}>
          <Input placeholder="Salas" maxLength={40} />
        </Form.Item>
        {!somenteLeitura && <Button htmlType="submit">Salvar nome</Button>}
      </Form>
    </Secao>
  )
}

export default function Locais() {
  const { locais, servicos, loja, agendamentos } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const nomes = useNomes()
  const somenteLeitura = !pode('locais', 'escrita')
  const { singular, plural: nomePlural } = rotulosLocal(loja.dados)

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

  const colunasAgendamentos = [
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Horário', dataIndex: 'hora', render: horaCurta },
    { title: 'Cliente', dataIndex: 'clienteId', render: nomes.cliente },
    { title: 'Profissional', dataIndex: 'funcionarioId', render: nomes.profissional },
    moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: nomes.servico },
    { title: 'Situação', dataIndex: 'status', render: (s) => <EtiquetaStatus status={s} /> },
  ].filter(Boolean)

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    {
      title: 'Tipo',
      dataIndex: 'tipo',
      filters: Object.entries(tiposLocal).map(([value, t]) => ({ value, text: t.label })),
      onFilter: (v, l) => l.tipo === v,
      render: (t) => <EtiquetaTipoLocal tipo={t} />,
    },
    {
      title: 'Descrição ou link',
      key: 'detalhe',
      render: (_, l) =>
        l.tipo === 'online' && l.linkPadrao ? (
          <a href={l.linkPadrao} target="_blank" rel="noreferrer">
            <LinkOutlined aria-hidden="true" /> {l.linkPadrao}
          </a>
        ) : (
          l.descricao || <span className="texto-apoio">—</span>
        ),
    },
    moduloAtivo('servicos') && {
      title: 'Serviços vinculados',
      key: 'servicos',
      render: (_, l) => {
        const lista = servicosDoLocal(l.id)
        return lista.length ? lista.map((s) => s.nome).join(', ') : <span className="texto-apoio">Só os sem vínculo</span>
      },
    },
    {
      title: 'Próximos',
      key: 'agendamentos',
      align: 'right',
      render: (_, l) => {
        const n = proximos(l.id)
        return n ? <Etiqueta tom="tinta">{plural(n, 'agendamento', 'agendamentos')}</Etiqueta> : <span className="texto-apoio">Nenhum</span>
      },
    },
    { title: 'Situação', dataIndex: 'ativo', render: (ativo) => <EtiquetaSituacao ativo={ativo} /> },
  ].filter(Boolean)

  return (
    <CadastroTabela
      titulo={nomePlural}
      descricao={`Onde o atendimento acontece: salas, cadeiras, macas ou links online. Abra a linha para ver os agendamentos de cada ${singular.toLowerCase()}.`}
      item={singular.toLowerCase()}
      textoNovo={`Adicionar ${singular.toLowerCase()}`}
      textoSalvo="Salvo."
      lista={locais}
      colunas={colunas}
      somenteLeitura={somenteLeitura}
      permitirExcluir={false}
      larguraTabela={960}
      antes={<RotuloLocais loja={loja} somenteLeitura={somenteLeitura} />}
      expandable={{
        expandedRowRender: (l) => (
          <Tabela
            size="small"
            columns={colunasAgendamentos}
            dataSource={agendamentosDoLocal(l.id)}
            pagination={{ pageSize: 5, hideOnSinglePage: true }}
            vazio="Nenhum agendamento aqui"
          />
        ),
      }}
      validar={(v, item) =>
        locais.itens.some((l) => l.id !== item?.id && l.nome.trim().toLowerCase() === v.nome.trim().toLowerCase())
          ? `Já existe um local chamado "${v.nome}". Use outro nome.`
          : null
      }
      valoresNovo={{ tipo: 'presencial', ativo: true }}
      iconeRegistro={(l) => (l.tipo === 'online' ? <VideoCameraOutlined /> : <EnvironmentOutlined />)}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input placeholder="Ex.: Sala 101, Cadeira 2, Zoom Prof. Ana" maxLength={80} />
          </Form.Item>
          <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]}>
            <Select options={Object.entries(tiposLocal).map(([value, t]) => ({ value, label: t.label }))} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(a, b) => a.tipo !== b.tipo}>
            {({ getFieldValue }) =>
              getFieldValue('tipo') === 'online' ? (
                <Form.Item
                  name="linkPadrao"
                  label="Link fixo da reunião"
                  extra="Opcional. Se o link mudar a cada atendimento, informe no próprio agendamento."
                  rules={[{ type: 'url', message: 'Informe um link completo, começando com https://' }]}
                >
                  <Input placeholder="https://meet.google.com/" />
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
            extra="Inativo não aparece em novos agendamentos, mas o histórico é mantido."
          >
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
