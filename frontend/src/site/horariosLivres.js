import dayjs from 'dayjs'
import { horaDe, inativo, minutosDe } from '../components/agenda/util.js'
import { localOcupado } from '../data/locais.js'
import { bloqueioAtinge, jornadaDe } from '../data/horarios.js'

const PASSO = 30 // minutos entre um horário oferecido e outro
const ANTECEDENCIA = 60 // minutos mínimos a partir de agora

// Horários livres de um dia: dentro da jornada (do perfil de cada profissional), fora de bloqueios e sem conflito com outro agendamento.
// Com mais de um profissional, cada horário fica com o primeiro que estiver livre.
// localIds: locais onde o serviço pode acontecer (módulo Locais); o horário só é oferecido se algum estiver livre.
// null = loja sem o módulo, não verifica local.
export function horariosLivres({ data, funcionarioIds, funcionarios, duracao, jornadas, bloqueios, agendamentos, localIds = null }) {
  const chave = data.format('YYYY-MM-DD')
  const limite = dayjs().add(ANTECEDENCIA, 'minute')
  const livres = new Map()

  for (const funcionarioId of funcionarioIds) {
    const funcionario = funcionarios.find((f) => f.id === funcionarioId)
    const ocupados = agendamentos
      .filter((a) => a.funcionarioId === funcionarioId && a.data === chave && !inativo(a))
      .map((a) => [minutosDe(a.hora), minutosDe(a.hora) + (a.duracao ?? 0)])
    const bloqueado = (ini, fim) => {
      const [inicio, termino] = [data.startOf('day').add(ini, 'minute'), data.startOf('day').add(fim, 'minute')]
      return bloqueios.some(
        (b) =>
          bloqueioAtinge(b, funcionario) &&
          inicio.isBefore(dayjs(b.fim)) &&
          termino.isAfter(dayjs(b.inicio)),
      )
    }

    const faixas = jornadaDe(funcionario, jornadas).filter((j) => j.diaSemana === data.day())
    for (const faixa of faixas) {
      for (let ini = minutosDe(faixa.inicio); ini + duracao <= minutosDe(faixa.fim); ini += PASSO) {
        const fim = ini + duracao
        const hora = horaDe(ini)
        if (livres.has(hora)) continue
        if (data.startOf('day').add(ini, 'minute').isBefore(limite)) continue
        if (ocupados.some(([o1, o2]) => ini < o2 && fim > o1)) continue
        if (bloqueado(ini, fim)) continue
        const localId = localIds?.find((id) => !localOcupado(id, chave, ini, fim, agendamentos)) ?? null
        if (localIds && localId == null) continue
        livres.set(hora, { funcionarioId, localId })
      }
    }
  }

  return [...livres.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([hora, livre]) => ({ hora, ...livre }))
}
