import { useState } from 'react'
import { DatePicker, Select } from 'antd'
import { ArrowRightOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { modulos } from '../data/acesso.js'
import { PLATAFORMA, tabelasLoja, tabelasPlataforma } from '../data/plataforma.js'
import { dataBR } from '../utils/formatos.js'
import { usePlataforma } from './usePlataforma.js'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import { EtiquetaOperacao } from '../components/Etiquetas.jsx'

const CONTROLE = ['id', 'criadoEm', 'atualizadoEm', 'atualizadoPor', 'excluidoEm', 'excluidoPor']
const DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

const PERIODOS = [
  { label: 'Hoje', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { label: 'Últimos 7 dias', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: 'Últimos 30 dias', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: 'Últimos 90 dias', value: [dayjs().subtract(89, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: 'Último ano', value: [dayjs().subtract(1, 'year').startOf('day'), dayjs().endOf('day')] },
]

const nomesCampos = {
  nome: 'Nome',
  sobrenome: 'Sobrenome',
  nomeFantasia: 'Nome da loja',
  email: 'E-mail',
  telefone: 'Telefone',
  status: 'Situação',
  ativo: 'Ativo',
  descricao: 'Descrição',
  precoMensal: 'Preço mensal',
  preco: 'Preço',
  duracao: 'Duração (min)',
  quantidade: 'Quantidade',
  data: 'Data',
  hora: 'Hora',
  perfil: 'Perfil',
  senha: 'Senha',
  observacao: 'Observação',
  expiraEm: 'Expira em',
  motivo: 'Motivo',
  planoId: 'Plano',
  tipo: 'Tipo',
}

const formatar = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'Sim' : 'Não'
  if (Array.isArray(v) && v.every((x) => typeof x !== 'object')) return v.join(', ') || '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// Campos da linha (sem as colunas de controle) e se mudaram
const campos = ({ antes, depois }) => {
  const chaves = [...new Set([...Object.keys(antes ?? {}), ...Object.keys(depois ?? {})])].filter((c) => !CONTROLE.includes(c))
  return chaves.map((c) => ({ campo: c, antes: antes?.[c], depois: depois?.[c], mudou: !igual(antes?.[c], depois?.[c]) }))
}

// Um campo alterado: valor antigo riscado, seta, valor novo
function Mudanca({ antes, depois }) {
  return (
    <span className="mudanca">
      <del>{formatar(antes)}</del>
      <ArrowRightOutlined aria-label="mudou para" />
      <strong>{formatar(depois)}</strong>
    </span>
  )
}

// Histórico de alterações de uma loja (ou da plataforma), uma tabela por vez, num período.
export default function HistoricoAlteracoes({ lojaId }) {
  const { historico, lojas, superadmins, clientes, lojaAtualId } = useData()
  const { funcionariosDe } = usePlataforma()
  const plataforma = lojaId === PLATAFORMA
  const tabelas = plataforma ? tabelasPlataforma : tabelasLoja
  const [tabela, setTabela] = useState(Object.keys(tabelas)[0])
  const [periodo, setPeriodo] = useState(PERIODOS[2].value)
  const [quem, setQuem] = useState(null)

  const loja = lojas.todos.find((l) => l.id === lojaId)
  const equipe = loja ? funcionariosDe(loja, { comExcluidos: true }) : []

  // Chave de quem fez: f<id> = funcionário, s<id> = superadmin, site = cliente pelo site
  const chaveQuem = (h) => (h.site ? 'site' : h.superadminId ? `s${h.superadminId}` : `f${h.funcionarioId}`)
  const nomeQuem = (h) => {
    if (h.site) return 'Cliente, pelo site'
    if (h.superadminId) return superadmins.todos.find((s) => s.id === h.superadminId)?.nome ?? 'Superadmin'
    return equipe.find((f) => f.id === h.funcionarioId)?.nome ?? `Funcionário ${h.funcionarioId}`
  }

  const rotulo = (linha) => {
    if (!linha) return '—'
    switch (tabela) {
      case 'agendamentos': {
        const cliente = lojaId === lojaAtualId && clientes.todos.find((c) => c.id === linha.clienteId)
        return `${dataBR(linha.data)} ${linha.hora}${cliente ? `, ${cliente.nome} ${cliente.sobrenome}` : ''}`
      }
      case 'registros_ponto':
        return `${dataBR(linha.data)}, entrada ${linha.entrada}`
      case 'perfil_horarios':
        return `${DIAS[linha.diaSemana]} ${linha.inicio} às ${linha.fim}`
      case 'bloqueios_agenda':
        return linha.motivo ?? `Bloqueio ${linha.id}`
      case 'loja_funcionalidades':
        return modulos.find((m) => m.codigo === linha.codigo)?.nome ?? linha.codigo
      case 'clientes':
        return `${linha.nome} ${linha.sobrenome ?? ''}`
      default:
        return linha.nomeFantasia ?? linha.nome ?? `Registro ${linha.id}`
    }
  }

  const [de, ate] = periodo ?? [null, null]
  const doPeriodo = historico
    .filter((h) => (plataforma ? h.lojaId === null : h.lojaId === lojaId))
    .filter((h) => h.tabela === tabela)
    .filter((h) => !de || (dayjs(h.criadoEm).isAfter(de) && dayjs(h.criadoEm).isBefore(ate)))
  const dados = doPeriodo.filter((h) => !quem || chaveQuem(h) === quem).sort((a, b) => b.criadoEm.localeCompare(a.criadoEm))
  const pessoas = [...new Map(doPeriodo.map((h) => [chaveQuem(h), nomeQuem(h)])).entries()]

  const colunas = [
    { title: 'Quando', dataIndex: 'criadoEm', width: 150, render: (d) => dayjs(d).format('DD/MM/YYYY HH:mm') },
    {
      title: 'Quem',
      key: 'quem',
      render: (_, h) => (
        <span className="com-ponto">
          {nomeQuem(h)}
          {h.superadminId && <Etiqueta tom="contorno">Superadmin</Etiqueta>}
          {h.site && <Etiqueta tom="contorno">Site</Etiqueta>}
        </span>
      ),
    },
    { title: 'Operação', dataIndex: 'operacao', render: (o) => <EtiquetaOperacao operacao={o} /> },
    {
      title: 'Registro',
      key: 'registro',
      render: (_, h) => (
        <span className="recurso">
          <span>{rotulo(h.depois ?? h.antes)}</span>
          <span className="texto-apoio">Código {h.registroId}</span>
        </span>
      ),
    },
    {
      title: 'O que mudou',
      key: 'mudancas',
      render: (_, h) => {
        if (h.operacao === 'inserir') return <span className="texto-apoio">Registro criado</span>
        if (h.operacao === 'excluir') return <span className="texto-apoio">Registro excluído</span>
        const mudou = campos(h).filter((c) => c.mudou)
        return (
          <span className="recurso">
            {mudou.slice(0, 3).map((c) => (
              <span key={c.campo}>
                {nomesCampos[c.campo] ?? c.campo}: <Mudanca antes={c.antes} depois={c.depois} />
              </span>
            ))}
            {mudou.length > 3 && <span className="texto-apoio">e mais {mudou.length - 3}</span>}
          </span>
        )
      },
    },
  ]

  return (
    <div className="historico-alteracoes">
      <BarraFiltros>
        <Select
          aria-label="Tabela"
          value={tabela}
          onChange={(t) => {
            setTabela(t)
            setQuem(null)
          }}
          options={Object.entries(tabelas).map(([value, label]) => ({ value, label }))}
        />
        <DatePicker.RangePicker
          className="busca"
          format="DD/MM/YYYY"
          value={periodo}
          onChange={setPeriodo}
          presets={PERIODOS}
          allowClear={false}
          aria-label="Período"
        />
        <Select
          allowClear
          placeholder="Todas as pessoas"
          aria-label="Quem fez"
          value={quem}
          onChange={setQuem}
          options={pessoas.map(([value, label]) => ({ value, label }))}
        />
      </BarraFiltros>
      <Tabela
        scroll={{ x: 960 }}
        dataSource={dados}
        columns={colunas}
        vazio={<EstadoVazio compacto titulo="Nenhuma alteração nesta tabela no período" descricao="Tente um período maior ou outra tabela." />}
        expandable={{
          expandedRowRender: (h) => (
            <Tabela
              rowKey="campo"
              size="small"
              pagination={false}
              dataSource={campos(h)}
              columns={[
                { title: 'Campo', dataIndex: 'campo', width: 200, render: (c) => nomesCampos[c] ?? c },
                { title: 'Antes', dataIndex: 'antes', render: formatar },
                {
                  title: 'Depois',
                  key: 'depois',
                  render: (_, c) => (c.mudou && h.operacao === 'alterar' ? <strong>{formatar(c.depois)}</strong> : formatar(c.depois)),
                },
              ]}
            />
          ),
        }}
      />
    </div>
  )
}
