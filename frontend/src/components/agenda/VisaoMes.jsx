import { corDe, ehHoje, inativo, mesmoDia, nomesDias } from './util.js'
import { horaCurta, plural } from '../../utils/formatos.js'
import PontoCor from '../base/PontoCor.jsx'

const MAX_POR_DIA = 3

// Linhas cinza por dia enquanto o mês carrega (quantidade varia para não parecer uma tabela)
const FANTASMAS_POR_DIA = [2, 1, 0, 3, 1, 2, 0]
const LARGURAS_FANTASMA = ['90%', '70%', '50%']

// Grade mensal com 6 semanas fixas. Clicar num dia só seleciona: a grade nunca muda de lugar.
// carregando: o mês ainda não chegou (linhas cinza no lugar dos agendamentos).
export default function VisaoMes({ dias, mes, agendamentos, bloqueios, diaSelecionado, onSelecionarDia, carregando = false }) {
  // Loja fechada no dia (feriado...): bloqueio da loja inteira
  const temBloqueioLoja = (dia) =>
    bloqueios.some((b) => b.quem == null && dia.isBefore(b.fim) && dia.endOf('day').isAfter(b.inicio))

  return (
    <div className="agenda-mes">
      {nomesDias.map((n) => (
        <div key={n} className="agenda-mes-titulo" aria-hidden="true">
          {n}
        </div>
      ))}
      {dias.map((dia, indice) => {
        const chave = dia.format('YYYY-MM-DD')
        const doDia = carregando
          ? []
          : agendamentos.filter((a) => a.data === chave).sort((a, b) => a.inicio.localeCompare(b.inicio))
        const classes = [
          'agenda-mes-dia',
          !dia.isSame(mes, 'month') && 'fora',
          ehHoje(dia) && 'hoje',
          mesmoDia(dia, diaSelecionado) && 'selecionado',
          !carregando && temBloqueioLoja(dia) && 'bloqueado',
        ]
        return (
          <button
            key={chave}
            type="button"
            className={classes.filter(Boolean).join(' ')}
            aria-pressed={mesmoDia(dia, diaSelecionado)}
            aria-label={
              carregando
                ? dia.format('dddd, DD [de] MMMM')
                : `${dia.format('dddd, DD [de] MMMM')}: ${plural(doDia.length, 'agendamento', 'agendamentos')}`
            }
            onClick={() => onSelecionarDia(dia)}
          >
            <span className="agenda-mes-numero">{dia.date()}</span>
            {carregando &&
              LARGURAS_FANTASMA.slice(0, FANTASMAS_POR_DIA[(indice + Math.floor(indice / 7) * 3) % FANTASMAS_POR_DIA.length]).map((largura) => (
                <span key={largura} className="agenda-fantasma-linha" aria-hidden="true" style={{ width: largura }} />
              ))}
            {doDia.slice(0, MAX_POR_DIA).map((a) => (
              <span key={a.id} className={['agenda-mes-item', inativo(a) && 'inativo'].filter(Boolean).join(' ')}>
                <PontoCor cor={corDe(a)} />
                {horaCurta(a.hora)} {a.clienteNome ?? '—'}
              </span>
            ))}
            {doDia.length > MAX_POR_DIA && <span className="agenda-mes-mais">+{doDia.length - MAX_POR_DIA}</span>}
          </button>
        )
      })}
    </div>
  )
}
