import { useState } from 'react'
import { DatePicker, Empty, Flex, Select, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { modulos } from '../data/acesso.js'
import { operacoesHistorico, PLATAFORMA, tabelasLoja, tabelasPlataforma } from '../data/plataforma.js'
import { usePlataforma } from './usePlataforma.js'

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
    return equipe.find((f) => f.id === h.funcionarioId)?.nome ?? `Funcionário #${h.funcionarioId}`
  }

  const rotulo = (linha) => {
    if (!linha) return '—'
    switch (tabela) {
      case 'agendamentos': {
        const cliente = lojaId === lojaAtualId && clientes.todos.find((c) => c.id === linha.clienteId)
        return `${dayjs(linha.data).format('DD/MM/YYYY')} ${linha.hora}${cliente ? ` · ${cliente.nome} ${cliente.sobrenome}` : ''}`
      }
      case 'registros_ponto':
        return `${dayjs(linha.data).format('DD/MM/YYYY')} · entrada ${linha.entrada}`
      case 'perfil_horarios':
        return `${DIAS[linha.diaSemana]} ${linha.inicio}–${linha.fim}`
      case 'bloqueios_agenda':
        return linha.motivo ?? `#${linha.id}`
      case 'loja_funcionalidades':
        return modulos.find((m) => m.codigo === linha.codigo)?.nome ?? linha.codigo
      case 'clientes':
        return `${linha.nome} ${linha.sobrenome ?? ''}`
      default:
        return linha.nomeFantasia ?? linha.nome ?? `#${linha.id}`
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
        <Flex gap={6} align="center" wrap>
          {nomeQuem(h)}
          {h.superadminId && <Tag color="purple">Admin</Tag>}
          {h.site && <Tag color="gold">Site</Tag>}
        </Flex>
      ),
    },
    {
      title: 'Operação',
      dataIndex: 'operacao',
      render: (o) => <Tag color={operacoesHistorico[o]?.color}>{operacoesHistorico[o]?.label}</Tag>,
    },
    {
      title: 'Registro',
      key: 'registro',
      render: (_, h) => (
        <>
          {rotulo(h.depois ?? h.antes)}{' '}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            #{h.registroId}
          </Typography.Text>
        </>
      ),
    },
    {
      title: 'O que mudou',
      key: 'mudancas',
      render: (_, h) => {
        if (h.operacao === 'inserir') return <Typography.Text type="secondary">Registro criado</Typography.Text>
        if (h.operacao === 'excluir') return <Typography.Text type="danger">Registro excluído</Typography.Text>
        const mudou = campos(h).filter((c) => c.mudou)
        return (
          <Flex vertical>
            {mudou.slice(0, 3).map((c) => (
              <span key={c.campo}>
                <Typography.Text strong>{nomesCampos[c.campo] ?? c.campo}:</Typography.Text>{' '}
                <Typography.Text delete type="secondary">{formatar(c.antes)}</Typography.Text> → {formatar(c.depois)}
              </span>
            ))}
            {mudou.length > 3 && <Typography.Text type="secondary">+{mudou.length - 3} campo(s)</Typography.Text>}
          </Flex>
        )
      },
    },
  ]

  return (
    <Flex vertical gap={16}>
      <Flex gap={8} wrap>
        <Select
          style={{ width: 220 }}
          value={tabela}
          onChange={(t) => {
            setTabela(t)
            setQuem(null)
          }}
          options={Object.entries(tabelas).map(([value, label]) => ({ value, label }))}
        />
        <DatePicker.RangePicker format="DD/MM/YYYY" value={periodo} onChange={setPeriodo} presets={PERIODOS} allowClear={false} />
        <Select
          allowClear
          placeholder="Todas as pessoas"
          style={{ width: 220 }}
          value={quem}
          onChange={setQuem}
          options={pessoas.map(([value, label]) => ({ value, label }))}
        />
      </Flex>
      <Table
        rowKey="id"
        size="middle"
        dataSource={dados}
        columns={colunas}
        scroll={{ x: true }}
        locale={{ emptyText: <Empty description="Nenhuma alteração nesta tabela no período" /> }}
        expandable={{
          expandedRowRender: (h) => (
            <Table
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
                  render: (_, c) => <Typography.Text strong={c.mudou && h.operacao === 'alterar'}>{formatar(c.depois)}</Typography.Text>,
                },
              ]}
            />
          ),
        }}
      />
    </Flex>
  )
}
