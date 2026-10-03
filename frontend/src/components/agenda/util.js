import { cores } from '../../tema.js'
import { agoraNaLoja } from '../../data/api/conversao.js'

// Cor de quem não tem cor definida na agenda
export const COR_PADRAO = cores.textoTerciario

export const minutosDe = (hora) => {
  const [h, m] = String(hora ?? '').split(':').map(Number)
  return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : 0
}

export const MINUTOS_DIA = 24 * 60

export const horaDe = (minutos) =>
  `${String(Math.floor(minutos / 60)).padStart(2, '0')}:${String(minutos % 60).padStart(2, '0')}`

// Hora do fim (depois da meia-noite volta a contar do zero: 23h + 2h = 1h)
export const fimDe = (a) => a.horaFim ?? horaDe((minutosDe(a.hora) + (a.duracao ?? 0)) % MINUTOS_DIA)

// Agendamento que começa num dia e termina no seguinte (ex.: 23h às 1h)
export const passaDaMeiaNoite = (a) => minutosDe(a.hora) + (a.duracao ?? 0) > MINUTOS_DIA

// Cor do profissional na agenda (vem com o agendamento da API)
export const corDe = (a) => a?.cor ?? COR_PADRAO

// Local do agendamento para o LocalInfo (null = sem local)
export const localDe = (a) => (a?.localId ? { nome: a.localNome ?? '—', tipo: a.localTipo } : null)

// Cancelados e faltas aparecem esmaecidos e não contam como horário ocupado
export const inativo = (a) => a.status === 'cancelado' || a.status === 'nao_compareceu'

// Domingo da semana que contém a data
export const inicioDaSemana = (d) => d.subtract(d.day(), 'day').startOf('day')

export const diasDaSemana = (d) => Array.from({ length: 7 }, (_, i) => inicioDaSemana(d).add(i, 'day'))

// Sempre 6 semanas: a grade do mês tem altura fixa e não "pula" ao trocar de mês
export const diasDoMes = (d) => {
  const inicio = inicioDaSemana(d.startOf('month'))
  return Array.from({ length: 42 }, (_, i) => inicio.add(i, 'day'))
}

export const nomesDias = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

export const mesmoDia = (a, b) => a.isSame(b, 'day')

// "Hoje" é o dia da loja, não o do navegador
export const ehHoje = (d) => d.isSame(agoraNaLoja(), 'day')

// Distribui agendamentos sobrepostos lado a lado (coluna e total de colunas do grupo)
export function distribuir(eventos) {
  const ordenados = [...eventos].sort((a, b) => a.ini - b.ini || b.fim - a.fim)
  const resultado = []
  let grupo = []
  let fimGrupo = -1

  const fecharGrupo = () => {
    const colunas = []
    for (const e of grupo) {
      let c = colunas.findIndex((fim) => fim <= e.ini)
      if (c === -1) {
        c = colunas.length
        colunas.push(0)
      }
      colunas[c] = e.fim
      e.coluna = c
    }
    grupo.forEach((e) => (e.colunas = colunas.length))
    resultado.push(...grupo)
    grupo = []
  }

  for (const e of ordenados) {
    if (grupo.length && e.ini >= fimGrupo) fecharGrupo()
    grupo.push(e)
    fimGrupo = Math.max(fimGrupo, e.fim)
  }
  if (grupo.length) fecharGrupo()
  return resultado
}
