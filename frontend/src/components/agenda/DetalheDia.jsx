import { Card, Button, Flex, Tag, Typography, Empty, Alert } from 'antd'
import { PlusOutlined, ClockCircleOutlined, UserOutlined } from '@ant-design/icons'
import { statusAgendamento } from '../../data/mock.js'
import { moeda } from '../../utils/formatos.js'
import { capitalizar, ehHoje, fimDe, inativo } from './util.js'
import AceiteSolicitacao from '../AceiteSolicitacao.jsx'

// Painel lateral: todos os atendimentos do dia selecionado, em ordem de horário
export default function DetalheDia({ dia, agendamentos, bloqueios, podeCriar, podeEditar, onNovo, onAbrir, nomeCliente, nomeServico, nomeFunc, corDe, comServicos }) {
  const lista = [...agendamentos].sort((a, b) => a.hora.localeCompare(b.hora))
  const ativos = lista.filter((a) => !inativo(a))
  const minutos = ativos.reduce((t, a) => t + (a.duracao ?? 0), 0)
  const total = ativos.reduce((t, a) => t + (a.preco ?? 0), 0)

  return (
    <Card
      className="agenda-detalhe"
      title={
        <Flex vertical>
          <Flex align="center" gap={8}>
            <span>{capitalizar(dia.format('dddd, DD [de] MMMM'))}</span>
            {ehHoje(dia) && <Tag color="green">Hoje</Tag>}
          </Flex>
          <Typography.Text type="secondary" style={{ fontWeight: 'normal', fontSize: 13 }}>
            {ativos.length} {ativos.length === 1 ? 'atendimento' : 'atendimentos'} · {Math.floor(minutos / 60)}h
            {String(minutos % 60).padStart(2, '0')} agendadas{total > 0 && ` · ${moeda(total)}`}
          </Typography.Text>
        </Flex>
      }
    >
      {podeCriar && (
        <Button type="primary" block icon={<PlusOutlined />} onClick={onNovo} style={{ marginBottom: 16 }}>
          Agendar neste dia
        </Button>
      )}
      {bloqueios.map((b) => (
        <Alert
          key={b.id}
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          title={b.funcionarioId == null ? `Loja fechada: ${b.motivo}` : `${nomeFunc(b.funcionarioId)} indisponível: ${b.motivo}`}
        />
      ))}

      {lista.length === 0 && <Empty description="Nenhum agendamento neste dia" />}

      <Flex vertical gap={10}>
        {lista.map((a) => (
          <div
            key={a.id}
            className={['agenda-detalhe-item', inativo(a) && 'inativo', a.status === 'pendente' && 'pendente'].filter(Boolean).join(' ')}
            style={{ borderLeftColor: corDe(a.funcionarioId) }}
            onClick={() => onAbrir(a)}
          >
            <Flex justify="space-between" align="center">
              <Typography.Text strong>
                <ClockCircleOutlined /> {a.hora} – {fimDe(a)}
              </Typography.Text>
              <Tag color={statusAgendamento[a.status]?.color} style={{ marginInlineEnd: 0 }}>
                {statusAgendamento[a.status]?.label}
              </Tag>
            </Flex>
            <div className="agenda-detalhe-cliente">{nomeCliente(a.clienteId)}</div>
            {comServicos && <Typography.Text>{nomeServico(a.servicoId)}</Typography.Text>}
            <Flex justify="space-between">
              <Typography.Text type="secondary">
                <UserOutlined /> {nomeFunc(a.funcionarioId)}
              </Typography.Text>
              <Typography.Text type="secondary">
                {a.duracao} min{a.preco != null && ` · ${moeda(a.preco)}`}
              </Typography.Text>
            </Flex>
            {a.status === 'pendente' && podeEditar(a) && <AceiteSolicitacao agendamento={a} />}
          </div>
        ))}
      </Flex>
    </Card>
  )
}
