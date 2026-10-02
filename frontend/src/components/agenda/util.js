import dayjs from 'dayjs'

export const COR_PADRAO = '#64748b'

export const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1)

export const minutosDe = (hora) => {
  const [h, m] = hora.split(':').map(Number)
  return h * 60 + m
}

export const horaDe = (minutos) =>
  `${String(Math.floor(minutos / 60)).padStart(2, '0')}:${String(minutos % 60).padStart(2, '0')}`

export const fimDe = (a) => horaDe(minutosDe(a.hora) + (a.duracao ?? 0))

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

export const ehHoje = (d) => d.isSame(dayjs(), 'day')

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
