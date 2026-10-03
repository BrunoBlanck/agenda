import { useConsulta } from './api/useConsulta.js'
import { carregarAgenda } from './api/agenda.js'
import { enviarData } from './api/conversao.js'

/**
 * Agenda de um período (semana, grade do mês ou dia): GET /api/loja/agenda.
 * periodo: { inicio, fim (dayjs), funcionarioId? }. Quem só tem Minha agenda recebe só os próprios.
 * Retorna { soPropria, profissionais, agendamentos, jornadas, bloqueios, carregando, atualizando, erro, recarregar }.
 */
export function useAgenda({ inicio, fim, funcionarioId = null }) {
  const de = enviarData(inicio)
  const ate = enviarData(fim)
  const consulta = useConsulta(
    (sinal) => carregarAgenda({ inicio: de, fim: ate, funcionarioId }, sinal),
    ['agenda', de, ate, funcionarioId],
    { ativo: !!(de && ate) },
  )
  const dados = consulta.dados
  return {
    soPropria: dados?.soPropria ?? false,
    profissionais: dados?.profissionais ?? [],
    agendamentos: dados?.agendamentos ?? [],
    jornadas: dados?.jornadas ?? [],
    bloqueios: dados?.bloqueios ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}
