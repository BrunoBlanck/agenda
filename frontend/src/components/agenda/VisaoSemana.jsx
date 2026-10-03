import { useEffect, useRef, useState } from 'react'
import { Tooltip } from 'antd'
import dayjs from 'dayjs'
import { statusAgendamento } from '../../data/dominio.js'
import { agoraNaLoja } from '../../data/api/conversao.js'
import { horaCurta } from '../../utils/formatos.js'
import { MINUTOS_DIA, corDe, distribuir, ehHoje, fimDe, horaDe, inativo, mesmoDia, minutosDe, nomesDias, passaDaMeiaNoite } from './util.js'

const ALTURA_HORA = 60 // px por hora
const PASSO = 30 // minutos ao clicar num horário vazio

// Agendamentos sobrepostos ficam lado a lado, mas cada um avança sobre o vizinho (o seguinte fica por cima)
// para o texto não ficar espremido
const larguraEvento = (coluna, colunas) =>
  coluna === colunas - 1 ? 1 / colunas : Math.min(1.7 / colunas, 1 - coluna / colunas)

// Parte do bloqueio que cai no dia, em minutos
const bloqueiosDoDia = (bloqueios, dia) =>
  bloqueios.flatMap((b) => {
    const [inicioBloqueio, fimBloqueio] = [dayjs(b.inicio), dayjs(b.fim)]
    const ini = inicioBloqueio.isAfter(dia.startOf('day')) ? inicioBloqueio : dia.startOf('day')
    const fim = fimBloqueio.isBefore(dia.endOf('day')) ? fimBloqueio : dia.endOf('day')
    if (!ini.isBefore(fim)) return []
    return [{ ...b, ini: ini.hour() * 60 + ini.minute(), fim: fim.hour() * 60 + fim.minute() }]
  })

// Blocos cinza no lugar dos agendamentos enquanto a semana carrega: [início em horas a partir do topo, duração]
const FANTASMAS = [
  [[1, 1], [3.5, 1.5]],
  [[0.5, 1.5], [4, 1]],
  [[2, 1], [5, 1.5]],
  [[1, 2]],
  [[0.5, 1], [3, 1], [6, 1]],
  [[2, 1.5]],
  [[1.5, 1]],
]

// Agendamentos do dia na grade. Quem passa da meia-noite é cortado às 24h ("continua") e a sobra
// aparece no topo do dia seguinte ("continuacao"), mesmo que comece antes da primeira hora da grade.
function eventosDoDia(agendamentos, dia, minutoInicial) {
  const chave = dia.format('YYYY-MM-DD')
  const anterior = dia.subtract(1, 'day').format('YYYY-MM-DD')
  const doDia = agendamentos
    .filter((a) => a.data === chave)
    .map((a) => {
      const ini = minutosDe(a.hora)
      return { a, chave: a.id, ini, fim: Math.min(MINUTOS_DIA, ini + (a.duracao ?? 0)), continua: passaDaMeiaNoite(a) }
    })
  const continuacoes = agendamentos
    .filter((a) => a.data === anterior && passaDaMeiaNoite(a))
    .map((a) => {
      const fim = Math.min(MINUTOS_DIA, minutosDe(a.hora) + (a.duracao ?? 0) - MINUTOS_DIA)
      // Termina antes da primeira hora da grade: fica um aviso compacto no topo
      const ini = Math.min(Math.max(0, minutoInicial), fim)
      const foraDaGrade = fim <= minutoInicial
      return { a, chave: `${a.id}:continuacao`, ini: foraDaGrade ? minutoInicial : ini, fim: foraDaGrade ? minutoInicial + 22 : fim, continuacao: true }
    })
  return distribuir([...continuacoes, ...doDia])
}

function Resumo({ a }) {
  return (
    <>
      <strong>
        {horaCurta(a.hora)} às {horaCurta(fimDe(a))}
        {passaDaMeiaNoite(a) && ' do dia seguinte'}
      </strong>
      <br />
      {a.clienteNome ?? '—'}
      <br />
      {a.servicoNome ?? 'Atendimento'}, com {a.funcionarioNome ?? '—'}
      <br />
      {statusAgendamento[a.status]?.label ?? 'Situação desconhecida'}
    </>
  )
}

// Grade semanal: uma coluna por dia, horas na vertical, agendamentos posicionados pelo horário.
// Clicar num horário vazio agenda nele (onNovo); sem permissão de criar, onNovo é null.
// destaqueId: agendamento aberto no painel lateral (fica marcado na grade).
// carregando: a semana ainda não chegou (mostra blocos cinza no formato da grade, sem agendamentos).
export default function VisaoSemana({ dias, agendamentos, bloqueios, horaInicio, horaFim, diaSelecionado, onSelecionarDia, onAbrir, onNovo, destaqueId, carregando = false }) {
  const grade = useRef(null)
  // Linha do "agora" na hora da loja
  const [agora, setAgora] = useState(agoraNaLoja)
  useEffect(() => {
    const t = setInterval(() => setAgora(agoraNaLoja()), 60_000)
    return () => clearInterval(t)
  }, [])

  // Em telas estreitas a grade rola na horizontal: mantém o dia selecionado à vista
  const chaveSelecionado = diaSelecionado.format('YYYY-MM-DD')
  useEffect(() => {
    const caixa = grade.current
    const coluna = caixa?.querySelector('.agenda-semana-dia[aria-pressed="true"]')
    if (!caixa || !coluna || caixa.scrollWidth <= caixa.clientWidth) return
    const inicio = coluna.offsetLeft - 48
    if (inicio < caixa.scrollLeft || inicio + coluna.offsetWidth > caixa.scrollLeft + caixa.clientWidth) {
      caixa.scrollLeft = inicio
    }
  }, [chaveSelecionado])

  const horas = Array.from({ length: horaFim - horaInicio }, (_, i) => horaInicio + i)
  const topo = (minutos) => ((minutos - horaInicio * 60) / 60) * ALTURA_HORA
  const alturaTotal = horas.length * ALTURA_HORA

  const clicarHorario = (dia, e) => {
    onSelecionarDia(dia)
    if (!onNovo) return
    const y = e.clientY - e.currentTarget.getBoundingClientRect().top
    const minutos = horaInicio * 60 + Math.floor((y / ALTURA_HORA) * (60 / PASSO)) * PASSO
    onNovo(dia, horaDe(minutos))
  }

  return (
    <div className="agenda-semana" ref={grade}>
      <div className="agenda-semana-cabecalho">
        <div />
        {dias.map((dia) => (
          <button
            key={dia.format('YYYY-MM-DD')}
            type="button"
            aria-pressed={mesmoDia(dia, diaSelecionado)}
            aria-label={dia.format('dddd, DD [de] MMMM')}
            className={['agenda-semana-dia', ehHoje(dia) && 'hoje', mesmoDia(dia, diaSelecionado) && 'selecionado']
              .filter(Boolean)
              .join(' ')}
            onClick={() => onSelecionarDia(dia)}
          >
            <span>{nomesDias[dia.day()]}</span>
            <strong>{dia.format('DD')}</strong>
          </button>
        ))}
      </div>

      <div className="agenda-semana-corpo" style={{ height: alturaTotal }}>
        <div className="agenda-semana-horas" aria-hidden="true">
          {horas.map((h) => (
            <div key={h} style={{ height: ALTURA_HORA }}>
              {h}h
            </div>
          ))}
        </div>

        {dias.map((dia, indice) => {
          const chave = dia.format('YYYY-MM-DD')
          const eventos = carregando ? [] : eventosDoDia(agendamentos, dia, horaInicio * 60)
          return (
            <div
              key={chave}
              className={['agenda-semana-coluna', mesmoDia(dia, diaSelecionado) && 'selecionado'].filter(Boolean).join(' ')}
              style={{ '--altura-hora': `${ALTURA_HORA}px` }}
              aria-busy={carregando || undefined}
              onClick={(e) => clicarHorario(dia, e)}
            >
              {carregando &&
                FANTASMAS[indice % FANTASMAS.length]
                  .filter(([inicio]) => horaInicio + inicio < horaFim)
                  .map(([inicio, duracao]) => (
                    <div
                      key={inicio}
                      className="agenda-fantasma"
                      aria-hidden="true"
                      style={{ top: inicio * ALTURA_HORA + 1, height: Math.min(duracao, horaFim - horaInicio - inicio) * ALTURA_HORA - 2 }}
                    />
                  ))}

              {!carregando &&
                bloqueiosDoDia(bloqueios, dia).map((b) => (
                  <div
                    key={b.id}
                    className="agenda-bloqueio"
                    style={{ top: Math.max(0, topo(b.ini)), height: Math.min(alturaTotal, topo(b.fim)) - Math.max(0, topo(b.ini)) }}
                    title={b.motivo}
                  >
                    {b.quem == null ? b.motivo : `${b.quem}: ${b.motivo}`}
                  </div>
                ))}

              {eventos.map(({ a, chave: chaveEvento, ini, fim, coluna, colunas, continua, continuacao }) => {
                const cor = corDe(a)
                const altura = Math.max(22, ((fim - ini) / 60) * ALTURA_HORA - 2)
                // A continuação abre o agendamento no dia em que ele começa (é lá que o painel do dia o lista)
                const diaDoAgendamento = continuacao ? dia.subtract(1, 'day') : dia
                return (
                  <Tooltip key={chaveEvento} title={<Resumo a={a} />}>
                    <button
                      type="button"
                      className={[
                        'agenda-evento',
                        inativo(a) && 'inativo',
                        a.status === 'pendente' && 'pendente',
                        a.id === destaqueId && 'em-edicao',
                        continua && 'continua',
                        continuacao && 'continuacao',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      style={{
                        top: topo(ini) + 1,
                        height: altura,
                        left: `calc(${(coluna / colunas) * 100}% + 2px)`,
                        width: `calc(${larguraEvento(coluna, colunas) * 100}% - 4px)`,
                        zIndex: 2 + coluna,
                        borderLeftColor: cor,
                        // Solicitado pelo site: marca-texto até a loja aceitar
                        background: a.status === 'pendente' ? 'var(--cor-marca-texto-clara)' : `color-mix(in srgb, ${cor} 12%, var(--cor-superficie))`,
                      }}
                      onClick={(e) => {
                        e.stopPropagation()
                        onSelecionarDia(diaDoAgendamento)
                        onAbrir(a)
                      }}
                    >
                      {continuacao ? (
                        <>
                          <span className="sr-only">Continuação do dia anterior: </span>
                          <strong>até {horaCurta(fimDe(a))}</strong> {a.clienteNome ?? '—'}
                        </>
                      ) : (
                        <>
                          <strong>{horaCurta(a.hora)}</strong> {a.clienteNome ?? '—'}
                          {altura > 40 && a.servicoNome && <span className="agenda-evento-servico">{a.servicoNome}</span>}
                          {continua && <span className="agenda-evento-continua">continua amanhã até {horaCurta(fimDe(a))}</span>}
                        </>
                      )}
                    </button>
                  </Tooltip>
                )
              })}

              {ehHoje(dia) && agora.hour() >= horaInicio && agora.hour() < horaFim && (
                <div className="agenda-agora" style={{ top: topo(agora.hour() * 60 + agora.minute()) }} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
