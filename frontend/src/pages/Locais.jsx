import { useState } from 'react'
import { App, Button, Form, Input, Select, Skeleton, Switch } from 'antd'
import { EnvironmentOutlined, LinkOutlined, VideoCameraOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import CampoServicosDoLocal from '../components/CampoServicosDoLocal.jsx'
import { EtiquetaSituacao, EtiquetaStatus, EtiquetaTipoLocal } from '../components/Etiquetas.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useAgendamentosDoLocal, useLocais, useRotulosLocal } from '../data/useLocais.js'
import { MAPA_ERROS_ROTULOS } from '../data/api/locais.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { tiposLocal } from '../data/dominio.js'
import { rotulosLocal } from '../data/locais.js'
import { dataBR, horaCurta, plural } from '../utils/formatos.js'

// Como a loja chama os locais (estrutura.md, 2.21). Muda o menu e os textos do painel.
function RotuloLocais({ somenteLeitura }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const { rotulos, carregando, erro, recarregar, salvar } = useRotulosLocal()
  const [salvando, setSalvando] = useState(false)

  const enviar = async (v) => {
    setSalvando(true)
    try {
      await salvar(v)
      message.success('Nome dos locais salvo.')
    } catch (e) {
      tratarErro(e, { form, mapa: MAPA_ERROS_ROTULOS })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Secao
      titulo="Como a loja chama os locais"
      descricao="Muda o nome no menu e nos formulários. Ex.: Sala (escola), Cadeira (barbearia), Maca (estética), Consultório (clínica)."
    >
      {carregando ? (
        <Skeleton.Input active block aria-label="Carregando" />
      ) : erro && !rotulos ? (
        <EstadoVazio
          compacto
          titulo="Não foi possível carregar o nome dos locais"
          descricao={erro.mensagem}
          acao={<Button onClick={recarregar}>Tentar de novo</Button>}
        />
      ) : (
        <Form
          // Recria o formulário quando os valores salvos mudam (depois de salvar ou recarregar)
          key={rotulos?.atualizadoEm ?? 'rotulos'}
          form={form}
          layout="inline"
          initialValues={{ singular: rotulos?.singular, plural: rotulos?.plural }}
          disabled={somenteLeitura || salvando}
          onFinish={enviar}
          colon={false}
          className="form-em-linha"
        >
          <Form.Item name="singular" label="Um" rules={[{ required: true, whitespace: true, message: 'Informe o singular' }]}>
            <Input placeholder="Sala" maxLength={40} />
          </Form.Item>
          <Form.Item name="plural" label="Vários" rules={[{ required: true, whitespace: true, message: 'Informe o plural' }]}>
            <Input placeholder="Salas" maxLength={40} />
          </Form.Item>
          {!somenteLeitura && (
            <Button htmlType="submit" loading={salvando}>
              Salvar nome
            </Button>
          )}
        </Form>
      )}
    </Secao>
  )
}

// Valor inicial do campo de serviços: servicoIds do contrato; enquanto a API não o trouxer, sai de servicos
const comServicoIds = (local) => ({ ...local, servicoIds: local.servicoIds ?? (local.servicos ?? []).map((s) => s.id) })

const nomeServico = (s) => (s.ativo === false ? `${s.nome} (inativo)` : s.nome)

// Agendamentos de hoje em diante no local (linha expandida); só os que o usuário pode ver na agenda
function AgendamentosDoLocal({ localId, comServicos }) {
  const ag = useAgendamentosDoLocal(localId)
  const colunas = [
    { title: 'Data', dataIndex: 'data', cartao: 'subtitulo', render: dataBR },
    { title: 'Horário', dataIndex: 'hora', cartao: 'subtitulo', render: horaCurta },
    { title: 'Cliente', dataIndex: 'clienteNome', cartao: 'titulo' },
    { title: 'Profissional', dataIndex: 'funcionarioNome' },
    comServicos && { title: 'Serviço', dataIndex: 'servicoNome' },
    { title: 'Situação', dataIndex: 'status', cartao: 'etiqueta', render: (s) => <EtiquetaStatus status={s} /> },
  ].filter(Boolean)

  return (
    <Tabela
      size="small"
      columns={colunas}
      dataSource={ag.itens}
      loading={ag.carregando}
      pagination={{
        current: ag.pagina,
        pageSize: ag.porPagina,
        total: ag.total,
        onChange: ag.mudarPagina,
        showSizeChanger: false,
        hideOnSinglePage: true,
      }}
      vazio={
        ag.erro ? (
          <EstadoVazio
            compacto
            titulo="Não foi possível carregar os agendamentos"
            descricao={ag.erro.mensagem}
            acao={<Button onClick={ag.recarregar}>Tentar de novo</Button>}
          />
        ) : (
          'Nenhum agendamento de hoje em diante'
        )
      }
    />
  )
}

export default function Locais() {
  const { pode, moduloAtivo, loja } = useAcesso()
  const locais = useLocais()
  const somenteLeitura = !pode('locais', 'escrita')
  const comServicos = moduloAtivo('servicos')
  const verAgendamentos = pode('agenda_equipe') || pode('agenda_propria')
  const { singular, plural: nomePlural } = rotulosLocal(loja)

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
    comServicos && {
      title: 'Serviços vinculados',
      dataIndex: 'servicos',
      render: (lista = []) =>
        lista.length ? lista.map(nomeServico).join(', ') : <span className="texto-apoio">Só os sem vínculo</span>,
    },
    {
      title: 'Próximos',
      dataIndex: 'proximosAgendamentos',
      align: 'right',
      render: (n) => (n ? <Etiqueta tom="tinta">{plural(n, 'agendamento', 'agendamentos')}</Etiqueta> : <span className="texto-apoio">Nenhum</span>),
    },
    { title: 'Situação', dataIndex: 'ativo', cartao: 'etiqueta', render: (ativo) => <EtiquetaSituacao ativo={ativo} /> },
  ].filter(Boolean)

  return (
    <CadastroTabela
      titulo={nomePlural}
      descricao={
        verAgendamentos
          ? 'Onde o atendimento acontece: salas, cadeiras, macas ou links online. Os próximos agendamentos de cada um aparecem na própria lista, ao expandir o item.'
          : 'Onde o atendimento acontece: salas, cadeiras, macas ou links online.'
      }
      item={singular.toLowerCase()}
      textoNovo={`Adicionar ${singular.toLowerCase()}`}
      textoSalvo="Salvo."
      lista={{ ...locais, carregarRegistro: async (registro) => comServicoIds(await locais.carregarRegistro(registro)) }}
      colunas={colunas}
      somenteLeitura={somenteLeitura}
      permitirExcluir={false}
      larguraTabela={960}
      antes={<RotuloLocais somenteLeitura={somenteLeitura} />}
      expandable={
        verAgendamentos
          ? {
              expandedRowRender: (l) => <AgendamentosDoLocal localId={l.id} comServicos={comServicos} />,
              rotuloCartao: 'Próximos agendamentos',
            }
          : undefined
      }
      valoresNovo={{ tipo: 'presencial', ativo: true, servicoIds: [] }}
      iconeRegistro={(l) => (l.tipo === 'online' ? <VideoCameraOutlined /> : <EnvironmentOutlined />)}
      campos={(registro) => (
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
                  <Input placeholder="https://meet.google.com/" maxLength={500} />
                </Form.Item>
              ) : (
                <Form.Item name="descricao" label="Descrição">
                  <Input.TextArea rows={2} maxLength={2000} placeholder="Ex.: piano de cauda, isolamento acústico" />
                </Form.Item>
              )
            }
          </Form.Item>
          {comServicos && <CampoServicosDoLocal registro={registro} somenteLeitura={somenteLeitura} singular={singular} />}
          <Form.Item
            name="ativo"
            label="Ativo"
            valuePropName="checked"
            extra="Inativo não aparece em novos agendamentos, mas o histórico é mantido."
          >
            <Switch />
          </Form.Item>
        </>
      )}
    />
  )
}
