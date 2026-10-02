import { HistoryOutlined, RightOutlined } from '@ant-design/icons'
import { inicioDe, useHistoricoCliente } from '../data/useHistoricoCliente.js'
import { dataBR, plural } from '../utils/formatos.js'

// Resumo do cliente logo abaixo do campo Cliente do agendamento. Clicar abre o histórico completo.
// É um botão comum (fora dos campos do formulário), então continua clicável em agendamentos só de leitura.
export default function ResumoCliente({ clienteId, agendamentoId, onAbrir }) {
  const { visiveis, concluidos, faltas, ultimo, proximo } = useHistoricoCliente(clienteId)
  const outros = visiveis.filter((a) => a.id !== agendamentoId)

  if (!clienteId) return null

  if (outros.length === 0) {
    return (
      <p className="resumo-cliente-primeiro">
        <HistoryOutlined aria-hidden="true" /> Primeiro agendamento deste cliente.
      </p>
    )
  }

  return (
    <button type="button" className="resumo-cliente" onClick={onAbrir}>
      <HistoryOutlined className="resumo-cliente-icone" aria-hidden="true" />
      <span className="resumo-cliente-textos">
        <span>
          {plural(concluidos, 'atendimento', 'atendimentos')}
          {ultimo && `, o último em ${dataBR(ultimo.data)}`}
          {faltas > 0 && <span className="resumo-cliente-faltas">, {plural(faltas, 'falta', 'faltas')}</span>}
        </span>
        {proximo && proximo.id !== agendamentoId && (
          <span className="texto-apoio">Próximo: {inicioDe(proximo).format('DD/MM [às] HH:mm')}</span>
        )}
      </span>
      <span className="resumo-cliente-link">
        Ver histórico <RightOutlined aria-hidden="true" />
      </span>
    </button>
  )
}
