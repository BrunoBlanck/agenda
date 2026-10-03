import { useState } from 'react'
import { App, Button, DatePicker, Popconfirm, Select, Tooltip } from 'antd'
import { DeleteOutlined, DisconnectOutlined, EditOutlined, EyeOutlined, PlusOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useFiltrosAgenda, useListaAgendamentos } from '../data/useAgendamentos.js'
import { excluirAgendamento } from '../data/api/agendamentos.js'
import { enviarData } from '../data/api/conversao.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { rotulosLocal } from '../data/locais.js'
import { dataBR, duracaoTexto, horaCurta } from '../utils/formatos.js'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'
import LocalInfo from '../components/LocalInfo.jsx'
import { localDe } from '../components/agenda/util.js'
import { EtiquetaStatus } from '../components/Etiquetas.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'

const rotuloOpcao = (item) => (item.ativo === false ? `${item.nome} (inativo)` : item.nome)

export default function Agendamentos() {
  const { agenda, moduloAtivo, loja } = useAcesso()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [profissional, setProfissional] = useState(null)
  const [local, setLocal] = useState(null)
  const [periodo, setPeriodo] = useState(null)
  const [excluindoId, setExcluindoId] = useState(null)
  const painel = usePainel()

  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja)
  const filtrando = profissional || local || periodo
  const filtros = useFiltrosAgenda({ ativo: agenda.verEquipe || comLocais })

  // Filtros e paginação no servidor (só os agendamentos que o usuário pode ver). Sem período, os mais
  // recentes primeiro (a página 1 não pode ser o começo do histórico); com período, em ordem de horário.
  const lista = useListaAgendamentos({
    funcionarioId: agenda.verEquipe ? (profissional ?? undefined) : undefined,
    localId: comLocais ? (local ?? undefined) : undefined,
    inicio: periodo?.[0] ? enviarData(periodo[0]) : undefined,
    fim: periodo?.[1] ? enviarData(periodo[1]) : undefined,
    ordem: periodo ? 'asc' : 'desc',
  })

  const excluir = async (a) => {
    setExcluindoId(a.id)
    try {
      await excluirAgendamento(a.id)
      message.success('Agendamento excluído.')
      // Último da página: volta uma página (a lista vem de novo do servidor)
      if (lista.itens.length === 1 && lista.pagina > 1) lista.mudarPagina(lista.pagina - 1)
      else lista.recarregar()
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: lista.recarregar, aoConflito: lista.recarregar })
    } finally {
      setExcluindoId(null)
    }
  }

  const colunas = [
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Horário', dataIndex: 'hora', render: horaCurta },
    { title: 'Cliente', dataIndex: 'clienteNome', render: (nome) => <strong>{nome ?? '—'}</strong> },
    agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioNome', render: (nome) => nome ?? '—' },
    moduloAtivo('servicos') && { title: 'Serviço', dataIndex: 'servicoNome', render: (nome) => nome ?? '—' },
    comLocais && { title: rotulos.singular, key: 'local', render: (_, a) => <LocalInfo local={localDe(a)} /> },
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
          {/* Concluído não é excluído (AGE-21): os materiais já saíram do estoque */}
          {agenda.editar(a) && a.status !== 'concluido' && (
            <Popconfirm
              title="Excluir este agendamento?"
              description="Para registrar que o cliente desmarcou, prefira mudar a situação para Cancelado."
              okText="Excluir"
              okButtonProps={{ danger: true }}
              cancelText="Cancelar"
              onConfirm={() => excluir(a)}
            >
              <Tooltip title="Excluir">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  loading={excluindoId === a.id}
                  aria-label="Excluir"
                />
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

  const vazio = lista.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar os agendamentos"
      descricao={lista.erro.mensagem}
      acao={<Button onClick={lista.recarregar}>Tentar de novo</Button>}
    />
  ) : filtrando ? (
    <EstadoVazio compacto titulo="Nenhum agendamento com esses filtros" acao={<Button onClick={limpar}>Limpar filtros</Button>} />
  ) : (
    <EstadoVazio
      titulo="Nenhum agendamento ainda"
      acao={agenda.criar && <Button onClick={() => painel.abrir({})}>Agendar horário</Button>}
    />
  )

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
              onChange={(id) => setProfissional(id ?? null)}
              loading={filtros.carregando}
              notFoundContent={filtros.erro ? filtros.erro.mensagem : undefined}
              showSearch={{ optionFilterProp: 'label' }}
              options={filtros.profissionais.map((f) => ({ value: f.id, label: rotuloOpcao(f) }))}
            />
          )}
          {comLocais && (
            <Select
              allowClear
              placeholder={`Qualquer ${rotulos.singular.toLowerCase()}`}
              aria-label={rotulos.singular}
              value={local}
              onChange={(id) => setLocal(id ?? null)}
              loading={filtros.carregando}
              notFoundContent={filtros.erro ? filtros.erro.mensagem : undefined}
              options={(filtros.locais ?? []).map((l) => ({ value: l.id, label: rotuloOpcao(l) }))}
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
          dataSource={lista.itens}
          loading={lista.atualizando}
          scroll={{ x: 1100 }}
          destaqueId={painel.destaqueId}
          pagination={{
            current: lista.pagina,
            pageSize: lista.porPagina,
            total: lista.total,
            onChange: lista.mudarPagina,
            showSizeChanger: false,
            hideOnSinglePage: true,
          }}
          vazio={vazio}
        />
      </Secao>
      <AgendamentoPainel
        open={painel.aberto}
        agendamento={painel.registro?.id ? painel.registro : null}
        onClose={painel.fechar}
        onSalvo={lista.recarregar}
      />
    </Pagina>
  )
}
