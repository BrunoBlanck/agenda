import { useState } from 'react'
import { Avatar, Button, Drawer, Empty, Flex, Segmented, Tag, Typography, theme } from 'antd'
import { EnvironmentOutlined, MailOutlined, PhoneOutlined, VideoCameraOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento } from '../data/mock.js'
import { inicioDe, useHistoricoCliente } from '../data/useHistoricoCliente.js'
import { moeda, nomeCompleto } from '../utils/formatos.js'
import { capitalizar, COR_PADRAO, fimDe } from './agenda/util.js'
import { IconesCanais } from './CanaisCliente.jsx'

const POR_PAGINA = 10

const FILTROS = {
  todos: { label: 'Todos', aceita: () => true },
  concluidos: { label: 'Concluídos', aceita: (a) => a.status === 'concluido' },
  faltas: { label: 'Faltas e cancelados', aceita: (a) => ['nao_compareceu', 'cancelado'].includes(a.status) },
}

const iniciais = (c) => `${c.nome?.[0] ?? ''}${c.sobrenome?.[0] ?? ''}`.toUpperCase()

const haQuanto = (data) => {
  const dias = dayjs().startOf('day').diff(dayjs(data).startOf('day'), 'day')
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'ontem'
  return `há ${dias} dias`
}

// Bloco de data (dia grande, mês abreviado) usado na lista e no próximo agendamento
function BlocoData({ data, destaque }) {
  const { token } = theme.useToken()
  return (
    <Flex
      vertical
      align="center"
      justify="center"
      style={{
        width: 48,
        height: 52,
        flexShrink: 0,
        borderRadius: token.borderRadius,
        background: destaque ? token.colorPrimary : token.colorFillTertiary,
        color: destaque ? '#fff' : token.colorText,
        lineHeight: 1.1,
      }}
    >
      <span style={{ fontSize: 18, fontWeight: 600 }}>{data.format('DD')}</span>
      <span style={{ fontSize: 11, textTransform: 'uppercase', opacity: 0.8 }}>{data.format('MMM').replace('.', '')}</span>
    </Flex>
  )
}

function Numero({ valor, rotulo, cor }) {
  const { token } = theme.useToken()
  return (
    <Flex vertical align="center" style={{ flex: 1, minWidth: 0 }}>
      <span style={{ fontSize: 20, fontWeight: 600, color: cor ?? token.colorText, whiteSpace: 'nowrap' }}>{valor}</span>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {rotulo}
      </Typography.Text>
    </Flex>
  )
}

// Histórico do cliente: resumo e os agendamentos dele, do mais recente para o mais antigo.
export default function HistoricoCliente({ clienteId, open, onClose }) {
  const { token } = theme.useToken()
  const { clientes, servicos, funcionarios, locais } = useData()
  const { agenda, moduloAtivo } = useAcesso()
  const cliente = clientes.todos.find((c) => c.id === clienteId)
  const { visiveis, parcial, concluidos, faltas, cancelados, ultimo, proximo } = useHistoricoCliente(clienteId)
  const [filtro, setFiltro] = useState('todos')
  const [limite, setLimite] = useState(POR_PAGINA)

  const servico = (id) => servicos.todos.find((s) => s.id === id)
  const profissional = (id) => funcionarios.todos.find((f) => f.id === id)
  const local = (id) => locais.todos.find((l) => l.id === id)
  const gasto = visiveis.filter((a) => a.status === 'concluido').reduce((t, a) => t + (a.preco ?? 0), 0)

  const lista = visiveis.filter(FILTROS[filtro].aceita)
  // Agrupa por mês, mantendo a ordem (mais recente primeiro)
  const meses = lista.slice(0, limite).reduce((grupos, a) => {
    const chave = a.data.slice(0, 7)
    const grupo = grupos.at(-1)
    if (grupo?.chave === chave) grupo.itens.push(a)
    else grupos.push({ chave, itens: [a] })
    return grupos
  }, [])

  // Profissional (com a cor dele na agenda) e local
  const quemOnde = (a) => {
    const p = profissional(a.funcionarioId)
    const l = moduloAtivo('locais') && a.localId && local(a.localId)
    return (
      <Flex gap={12} wrap style={{ fontSize: 13 }}>
        <Typography.Text type="secondary">
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: p?.cor ?? COR_PADRAO,
              marginInlineEnd: 6,
            }}
          />
          {p?.nome ?? '—'}
        </Typography.Text>
        {l && (
          <Typography.Text type="secondary">
            {l.tipo === 'online' ? <VideoCameraOutlined /> : <EnvironmentOutlined />} {l.nome}
          </Typography.Text>
        )}
      </Flex>
    )
  }

  const titulo = (a) => `${a.hora}–${fimDe(a)} · ${servico(a.servicoId)?.nome ?? 'Atendimento'}`

  return (
    <Drawer
      title="Histórico do cliente"
      open={open}
      onClose={onClose}
      size={560}
      destroyOnHidden
      styles={{ body: { padding: 0 } }}
      afterOpenChange={(aberto) => {
        if (!aberto) {
          setFiltro('todos')
          setLimite(POR_PAGINA)
        }
      }}
    >
      {cliente && (
        <Flex vertical style={{ paddingBottom: 24 }}>
          {/* Cabeçalho */}
          <Flex gap={16} align="center" style={{ padding: '20px 24px' }}>
            <Avatar size={56} style={{ background: token.colorPrimary, fontSize: 20, flexShrink: 0 }}>
              {iniciais(cliente)}
            </Avatar>
            <Flex vertical gap={4} style={{ minWidth: 0 }}>
              <Flex align="center" gap={10} wrap>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {nomeCompleto(cliente)}
                </Typography.Title>
                <IconesCanais canais={cliente.canais} />
              </Flex>
              <Flex gap={16} wrap style={{ fontSize: 13 }}>
                <Typography.Text type="secondary">
                  <PhoneOutlined /> {cliente.telefone}
                </Typography.Text>
                {cliente.email && (
                  <Typography.Text type="secondary">
                    <MailOutlined /> {cliente.email}
                  </Typography.Text>
                )}
              </Flex>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {ultimo
                  ? `Último atendimento ${haQuanto(ultimo.data)} (${dayjs(ultimo.data).format('DD/MM/YYYY')})`
                  : 'Ainda sem atendimentos concluídos'}
              </Typography.Text>
            </Flex>
          </Flex>

          {cliente.observacoes && (
            <Typography.Paragraph
              style={{ margin: '0 24px 16px', padding: '8px 12px', background: token.colorWarningBg, borderRadius: token.borderRadius }}
            >
              {cliente.observacoes}
            </Typography.Paragraph>
          )}

          {/* Números */}
          <Flex
            style={{
              margin: '0 24px',
              padding: '12px 0',
              border: `1px solid ${token.colorBorderSecondary}`,
              borderRadius: token.borderRadiusLG,
            }}
          >
            <Numero valor={concluidos} rotulo="Atendimentos" />
            <Numero valor={faltas} rotulo="Faltas" cor={faltas ? token.colorWarning : undefined} />
            <Numero valor={cancelados} rotulo="Cancelados" cor={cancelados ? token.colorError : undefined} />
            <Numero valor={moeda(gasto)} rotulo="Total gasto" />
          </Flex>

          {/* Próximo agendamento */}
          {proximo && (
            <Flex
              gap={14}
              align="center"
              style={{
                margin: '16px 24px 0',
                padding: 12,
                borderRadius: token.borderRadiusLG,
                background: token.colorPrimaryBg,
                border: `1px solid ${token.colorPrimaryBorder}`,
              }}
            >
              <BlocoData data={inicioDe(proximo)} destaque />
              <Flex vertical gap={2} style={{ flex: 1, minWidth: 0 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Próximo agendamento · {capitalizar(inicioDe(proximo).format('dddd'))}
                </Typography.Text>
                <Typography.Text strong>{titulo(proximo)}</Typography.Text>
                {quemOnde(proximo)}
              </Flex>
              <Tag color={statusAgendamento[proximo.status]?.color} style={{ marginInlineEnd: 0 }}>
                {statusAgendamento[proximo.status]?.label}
              </Tag>
            </Flex>
          )}

          {/* Lista */}
          <Flex vertical gap={8} style={{ padding: '24px 24px 8px' }}>
            <Flex justify="space-between" align="center" gap={8} wrap>
              <Typography.Text strong>Agendamentos</Typography.Text>
              <Segmented
                size="small"
                value={filtro}
                onChange={(v) => {
                  setFiltro(v)
                  setLimite(POR_PAGINA)
                }}
                options={Object.entries(FILTROS).map(([value, f]) => ({ value, label: f.label }))}
              />
            </Flex>
            {!agenda.verEquipe && parcial && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Mostrando só os atendimentos da sua agenda.
              </Typography.Text>
            )}
          </Flex>

          {lista.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nenhum agendamento" />}

          {meses.map((mes) => (
            <div key={mes.chave}>
              <Typography.Text
                type="secondary"
                style={{
                  display: 'block',
                  padding: '12px 24px 6px',
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.6,
                }}
              >
                {dayjs(`${mes.chave}-01`).format('MMMM [de] YYYY')}
              </Typography.Text>
              {mes.itens.map((a) => {
                const apagado = a.status === 'cancelado' || a.status === 'nao_compareceu'
                return (
                  <Flex
                    key={a.id}
                    gap={14}
                    align="center"
                    style={{ padding: '10px 24px', borderTop: `1px solid ${token.colorSplit}`, opacity: apagado ? 0.7 : 1 }}
                  >
                    <BlocoData data={inicioDe(a)} />
                    <Flex vertical gap={2} style={{ flex: 1, minWidth: 0 }}>
                      <Typography.Text strong delete={a.status === 'cancelado'}>
                        {titulo(a)}
                      </Typography.Text>
                      {quemOnde(a)}
                      {a.motivoCancelamento && (
                        <Typography.Text type="secondary" italic style={{ fontSize: 12 }}>
                          {a.motivoCancelamento}
                        </Typography.Text>
                      )}
                    </Flex>
                    <Flex vertical align="end" gap={4} style={{ flexShrink: 0 }}>
                      <Tag color={statusAgendamento[a.status]?.color} style={{ marginInlineEnd: 0 }}>
                        {statusAgendamento[a.status]?.label}
                      </Tag>
                      {a.preco != null && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {moeda(a.preco)}
                        </Typography.Text>
                      )}
                    </Flex>
                  </Flex>
                )
              })}
            </div>
          ))}

          {lista.length > limite && (
            <Button type="link" onClick={() => setLimite((n) => n + POR_PAGINA)} style={{ alignSelf: 'center', marginTop: 8 }}>
              Ver mais {lista.length - limite}
            </Button>
          )}
        </Flex>
      )}
    </Drawer>
  )
}
