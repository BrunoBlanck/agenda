import { ehHoje, inativo, mesmoDia, nomesDias } from './util.js'
import { bloqueioDaLoja } from '../../data/horarios.js'
import { useNomes } from '../../data/useNomes.js'
import { horaCurta, plural } from '../../utils/formatos.js'
import PontoCor from '../base/PontoCor.jsx'

const MAX_POR_DIA = 3

// Grade mensal com 6 semanas fixas. Clicar num dia só seleciona: a grade nunca muda de lugar.
export default function VisaoMes({ dias, mes, agendamentos, bloqueios, diaSelecionado, onSelecionarDia }) {
  const nomes = useNomes()
  const temBloqueioLoja = (dia) =>
    bloqueios.some((b) => bloqueioDaLoja(b) && dia.isBefore(b.fim) && dia.endOf('day').isAfter(b.inicio))

  return (
    <div className="agenda-mes">
      {nomesDias.map((n) => (
        <div key={n} className="agenda-mes-titulo" aria-hidden="true">
          {n}
        </div>
      ))}
      {dias.map((dia) => {
        const chave = dia.format('YYYY-MM-DD')
        const doDia = agendamentos.filter((a) => a.data === chave).sort((a, b) => a.hora.localeCompare(b.hora))
        const classes = [
          'agenda-mes-dia',
          !dia.isSame(mes, 'month') && 'fora',
          ehHoje(dia) && 'hoje',
          mesmoDia(dia, diaSelecionado) && 'selecionado',
          temBloqueioLoja(dia) && 'bloqueado',
        ]
        return (
          <button
            key={chave}
            type="button"
            className={classes.filter(Boolean).join(' ')}
            aria-pressed={mesmoDia(dia, diaSelecionado)}
            aria-label={`${dia.format('dddd, DD [de] MMMM')}: ${plural(doDia.length, 'agendamento', 'agendamentos')}`}
            onClick={() => onSelecionarDia(dia)}
          >
            <span className="agenda-mes-numero">{dia.date()}</span>
            {doDia.slice(0, MAX_POR_DIA).map((a) => (
              <span key={a.id} className={['agenda-mes-item', inativo(a) && 'inativo'].filter(Boolean).join(' ')}>
                <PontoCor cor={nomes.corDe(a.funcionarioId)} />
                {horaCurta(a.hora)} {nomes.cliente(a.clienteId)}
              </span>
            ))}
            {doDia.length > MAX_POR_DIA && <span className="agenda-mes-mais">+{doDia.length - MAX_POR_DIA}</span>}
          </button>
        )
      })}
    </div>
  )
}
