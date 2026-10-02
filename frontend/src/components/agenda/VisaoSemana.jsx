import { useEffect, useState } from 'react'
import { Tooltip } from 'antd'
import dayjs from 'dayjs'
import { statusAgendamento } from '../../data/mock.js'
import { distribuir, ehHoje, fimDe, horaDe, inativo, mesmoDia, minutosDe, nomesDias } from './util.js'

const ALTURA_HORA = 60 // px por hora
const PASSO = 30 // minutos ao clicar num horário vazio

// Agendamentos sobrepostos ficam lado a lado, mas cada um avança sobre o vizinho (o seguinte fica por cima)
// para o texto não ficar espremido
const larguraEvento = (coluna, colunas) =>
  coluna === colunas - 1 ? 1 / colunas : Math.min(1.7 / colunas, 1 - coluna / colunas)

// Grade semanal: uma coluna por dia, horas na vertical, agendamentos posicionados pelo horário
export default function VisaoSemana({
  dias,
  agendamentos,
  bloqueios,
  horaInicio,
  horaFim,
  diaSelecionado,
  onSelecionarDia,
  onAbrir,
  onNovo,
  nomeCliente,
  nomeServico,
  nomeFunc,
  corDe,
}) {
  const [agora, setAgora] = useState(dayjs())
  useEffect(() => {
    const t = setInterval(() => setAgora(dayjs()), 60_000)
    return () => clearInterval(t)
  }, [])

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

  // Parte do bloqueio que cai neste dia, em minutos
  const bloqueiosDoDia = (dia) =>
    bloqueios.flatMap((b) => {
      const [inicioBloqueio, fimBloqueio] = [dayjs(b.inicio), dayjs(b.fim)]
      const ini = inicioBloqueio.isAfter(dia.startOf('day')) ? inicioBloqueio : dia.startOf('day')
      const fim = fimBloqueio.isBefore(dia.endOf('day')) ? fimBloqueio : dia.endOf('day')
      if (!ini.isBefore(fim)) return []
      return [{ ...b, ini: ini.hour() * 60 + ini.minute(), fim: fim.hour() * 60 + fim.minute() }]
    })

  return (
    <div className="agenda-semana">
      <div className="agenda-semana-cabecalho">
        <div />
        {dias.map((dia) => (
          <button
            key={dia.format('YYYY-MM-DD')}
            type="button"
            className={[
              'agenda-semana-dia',
              ehHoje(dia) && 'hoje',
              mesmoDia(dia, diaSelecionado) && 'selecionado',
            ]
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
        <div className="agenda-semana-horas">
          {horas.map((h) => (
            <div key={h} style={{ height: ALTURA_HORA }}>
              {String(h).padStart(2, '0')}:00
            </div>
          ))}
        </div>

        {dias.map((dia) => {
          const chave = dia.format('YYYY-MM-DD')
          const eventos = distribuir(
            agendamentos
              .filter((a) => a.data === chave)
              .map((a) => ({ a, ini: minutosDe(a.hora), fim: minutosDe(a.hora) + (a.duracao ?? 0) })),
          )
          return (
            <div
              key={chave}
              className={['agenda-semana-coluna', mesmoDia(dia, diaSelecionado) && 'selecionado'].filter(Boolean).join(' ')}
              style={{ '--altura-hora': `${ALTURA_HORA}px` }}
              onClick={(e) => clicarHorario(dia, e)}
            >
              {bloqueiosDoDia(dia).map((b) => (
                <div
                  key={b.id}
                  className="agenda-bloqueio"
                  style={{ top: Math.max(0, topo(b.ini)), height: Math.min(alturaTotal, topo(b.fim)) - Math.max(0, topo(b.ini)) }}
                  title={b.motivo}
                >
                  {b.quem == null ? b.motivo : `${b.quem}: ${b.motivo}`}
                </div>
              ))}

              {eventos.map(({ a, ini, coluna, colunas }) => {
                const cor = corDe(a.funcionarioId)
                const altura = Math.max(22, ((a.duracao ?? 0) / 60) * ALTURA_HORA - 2)
                return (
                  <Tooltip
                    key={a.id}
                    title={`${a.hora}–${fimDe(a)} · ${nomeCliente(a.clienteId)} · ${nomeServico(a.servicoId)} · ${nomeFunc(a.funcionarioId)} · ${statusAgendamento[a.status]?.label}`}
                  >
                    <div
                      className={['agenda-evento', inativo(a) && 'inativo', a.status === 'pendente' && 'pendente'].filter(Boolean).join(' ')}
                      style={{
                        top: topo(ini) + 1,
                        height: altura,
                        left: `calc(${(coluna / colunas) * 100}% + 2px)`,
                        width: `calc(${larguraEvento(coluna, colunas) * 100}% - 4px)`,
                        zIndex: 2 + coluna,
                        borderLeftColor: cor,
                        background: `color-mix(in srgb, ${cor} 14%, #fff)`,
                      }}
                      onClick={(e) => {
                        e.stopPropagation()
                        onSelecionarDia(dia)
                        onAbrir(a)
                      }}
                    >
                      <strong>{a.hora}</strong> {nomeCliente(a.clienteId)}
                      {altura > 40 && <div className="agenda-evento-servico">{nomeServico(a.servicoId)}</div>}
                    </div>
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
