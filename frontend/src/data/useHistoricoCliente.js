import dayjs from 'dayjs'
import { useData } from './DataContext.jsx'
import { useAcesso } from './useAcesso.js'

const ATIVOS = ['pendente', 'agendado', 'confirmado']

export const inicioDe = (a) => dayjs(`${a.data} ${a.hora}`)

// Agendamentos do cliente que o usuário logado pode ver, do mais recente para o mais antigo.
// Quem só vê a própria agenda vê só os atendimentos dele com o cliente.
export function useHistoricoCliente(clienteId) {
  const { agendamentos } = useData()
  const { agenda } = useAcesso()
  const agora = dayjs()

  const doCliente = agendamentos.itens.filter((a) => a.clienteId === clienteId)
  const visiveis = doCliente.filter(agenda.ver).sort((a, b) => inicioDe(b).diff(inicioDe(a)))
  const contar = (status) => visiveis.filter((a) => a.status === status).length

  return {
    visiveis,
    parcial: visiveis.length < doCliente.length,
    concluidos: contar('concluido'),
    faltas: contar('nao_compareceu'),
    cancelados: contar('cancelado'),
    ultimo: visiveis.find((a) => a.status === 'concluido'),
    proximo: visiveis
      .filter((a) => ATIVOS.includes(a.status) && inicioDe(a).isAfter(agora))
      .sort((a, b) => inicioDe(a).diff(inicioDe(b)))[0],
  }
}
