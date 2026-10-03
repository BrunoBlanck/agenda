import { HistoryOutlined, RightOutlined } from '@ant-design/icons'
import { useHistoricoCliente } from '../data/useHistoricoCliente.js'
import { dataBR, plural } from '../utils/formatos.js'

// Resumo do cliente logo abaixo do campo Cliente do agendamento. Clicar abre o histórico completo.
// É um botão comum (fora dos campos do formulário), então continua clicável em agendamentos só de leitura.
// Busca sozinho o resumo na API (GET /clientes/{id}/historico, uma linha só da lista); sem leitura em
// Clientes, não aparece.
export default function ResumoCliente({ clienteId, agendamentoId, onAbrir }) {
  const h = useHistoricoCliente(clienteId, { porPagina: 1 })

  if (!clienteId || !h.permitido) return null

  if (h.carregando) {
    return (
      <p className="resumo-cliente-primeiro texto-apoio" role="status">
        <HistoryOutlined aria-hidden="true" /> Carregando o histórico do cliente…
      </p>
    )
  }

  if (h.erro) {
    return (
      <p className="resumo-cliente-primeiro texto-apoio">
        <HistoryOutlined aria-hidden="true" /> Não foi possível carregar o histórico agora.
      </p>
    )
  }

  // Há outro agendamento além deste? Com um só na lista, ele pode ser o próprio agendamento aberto
  const temOutros = h.total > 1 || (h.total === 1 && h.agendamentos[0]?.id !== agendamentoId)

  if (!temOutros) {
    return (
      <p className="resumo-cliente-primeiro">
        <HistoryOutlined aria-hidden="true" /> Primeiro agendamento deste cliente.
      </p>
    )
  }

  const { concluidos, faltas, ultimo, proximo } = h
  return (
    <button type="button" className="resumo-cliente" onClick={onAbrir}>
      <HistoryOutlined className="resumo-cliente-icone" aria-hidden="true" />
      <span className="resumo-cliente-textos">
        <span>
          {plural(concluidos, 'atendimento', 'atendimentos')}
          {ultimo && `, o último em ${dataBR(ultimo.data)}`}
          {faltas > 0 && <span className="resumo-cliente-faltas">, {plural(faltas, 'falta', 'faltas')}</span>}
        </span>
        {proximo?.inicio && proximo.id !== agendamentoId && (
          <span className="texto-apoio">Próximo: {proximo.inicio.format('DD/MM [às] HH:mm')}</span>
        )}
      </span>
      <span className="resumo-cliente-link">
        Ver histórico <RightOutlined aria-hidden="true" />
      </span>
    </button>
  )
}
