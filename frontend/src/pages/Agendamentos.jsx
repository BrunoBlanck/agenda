import { useState } from 'react'
import { App, Button, DatePicker, Popconfirm, Select, Tooltip } from 'antd'
import { DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useNomes } from '../data/useNomes.js'
import { rotulosLocal } from '../data/locais.js'
import { dataBR, duracaoTexto, horaCurta } from '../utils/formatos.js'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'
import LocalInfo from '../components/LocalInfo.jsx'
import { EtiquetaStatus } from '../components/Etiquetas.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'

const noPeriodo = (data, periodo) =>
  !periodo || (!dayjs(data).isBefore(periodo[0], 'day') && !dayjs(data).isAfter(periodo[1], 'day'))

export default function Agendamentos() {
  const { agendamentos, funcionarios, locais, loja } = useData()
  const { agenda, moduloAtivo } = useAcesso()
  const nomes = useNomes()
  const { message } = App.useApp()
  const [profissional, setProfissional] = useState(null)
  const [local, setLocal] = useState(null)
  const [periodo, setPeriodo] = useState(null)
  const painel = usePainel()

  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja.dados)
  const filtrando = profissional || local || periodo

  const dados = agendamentos.itens
    .filter(agenda.ver)
    .filter((a) => !profissional || a.funcionarioId === profissional)
    .filter((a) => !comLocais || !local || a.localId === local)
    .filter((a) => noPeriodo(a.data, periodo))
    .sort((a, b) => `${a.data} ${a.hora}`.localeCompare(`${b.data} ${b.hora}`))

  const colunas = [
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Horário', dataIndex: 'hora', render: horaCurta },
    { title: 'Cliente', dataIndex: 'clienteId', render: (id) => <strong>{nomes.cliente(id)}</strong> },
    agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioId', render: nomes.profissional },
    moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoId', render: nomes.servico },
    comLocais && { title: rotulos.singular, dataIndex: 'localId', render: (id) => <LocalInfo local={nomes.local(id)} /> },
    { title: 'Duração', dataIndex: 'duracao', align: 'right', render: duracaoTexto },
    { title: 'Situação', dataIndex: 'status', render: (s) => <EtiquetaStatus status={s} /> },
    {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      width: 96,
      align: 'right',
      fixed: 'right',
      render: (_, a) => (
        <span className="acoes-linha">
          <Tooltip title={agenda.editar(a) ? 'Editar' : 'Ver'}>
            <Button
              type="text"
              size="small"
              icon={agenda.editar(a) ? <EditOutlined /> : <EyeOutlined />}
              aria-label={agenda.editar(a) ? 'Editar' : 'Ver'}
              onClick={() => painel.abrir(a)}
            />
          </Tooltip>
          {agenda.editar(a) && (
            <Popconfirm
              title="Excluir este agendamento?"
              description="Para registrar que o cliente desmarcou, prefira mudar a situação para Cancelado."
              okText="Excluir"
              okButtonProps={{ danger: true }}
              cancelText="Cancelar"
              onConfirm={() => {
                agendamentos.remover(a.id)
                message.success('Agendamento excluído.')
              }}
            >
              <Tooltip title="Excluir">
                <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label="Excluir" />
              </Tooltip>
            </Popconfirm>
          )}
        </span>
      ),
    },
  ].filter(Boolean)

  const limpar = () => {
    setProfissional(null)
    setLocal(null)
    setPeriodo(null)
  }

  return (
    <Pagina
      titulo="Agendamentos"
      descricao="Todos os agendamentos em lista, para buscar por profissional, local ou período."
      acoes={
        agenda.criar && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => painel.abrir({})}>
            Agendar
          </Button>
        )
      }
    >
      <Secao rente>
        <BarraFiltros acoes={filtrando && <Button type="link" onClick={limpar}>Limpar filtros</Button>}>
          {agenda.verEquipe && (
            <Select
              allowClear
              placeholder="Todos os profissionais"
              aria-label="Profissional"
              value={profissional}
              onChange={setProfissional}
              options={funcionarios.itens.map((f) => ({ value: f.id, label: f.nome }))}
            />
          )}
          {comLocais && (
            <Select
              allowClear
              placeholder={`Qualquer ${rotulos.singular.toLowerCase()}`}
              aria-label={rotulos.singular}
              value={local}
              onChange={setLocal}
              options={locais.itens.map((l) => ({ value: l.id, label: l.nome }))}
            />
          )}
          <DatePicker.RangePicker
            className="busca"
            format="DD/MM/YYYY"
            placeholder={['De', 'Até']}
            value={periodo}
            onChange={setPeriodo}
          />
        </BarraFiltros>
        <Tabela
          columns={colunas}
          dataSource={dados}
          destaqueId={painel.destaqueId}
          vazio={
            filtrando ? (
              <EstadoVazio compacto titulo="Nenhum agendamento com esses filtros" acao={<Button onClick={limpar}>Limpar filtros</Button>} />
            ) : (
              <EstadoVazio
                titulo="Nenhum agendamento ainda"
                acao={agenda.criar && <Button onClick={() => painel.abrir({})}>Agendar horário</Button>}
              />
            )
          }
        />
      </Secao>
      <AgendamentoPainel open={painel.aberto} agendamento={painel.registro?.id ? painel.registro : null} onClose={painel.fechar} />
    </Pagina>
  )
}
