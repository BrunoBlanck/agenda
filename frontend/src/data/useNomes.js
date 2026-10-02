import { useData } from './DataContext.jsx'
import { nomeCompleto } from '../utils/formatos.js'
import { COR_PADRAO } from '../components/agenda/util.js'

// Nomes para exibir a partir dos ids. Busca também nos excluídos, para o histórico continuar legível.
export function useNomes() {
  const { clientes, funcionarios, servicos, locais } = useData()
  const achar = (lista, id) => lista.todos.find((i) => i.id === id)

  return {
    cliente: (id) => nomeCompleto(achar(clientes, id)) || '—',
    profissional: (id) => achar(funcionarios, id)?.nome ?? '—',
    servico: (id) => achar(servicos, id)?.nome ?? 'Atendimento',
    local: (id) => achar(locais, id),
    corDe: (id) => achar(funcionarios, id)?.cor ?? COR_PADRAO,
  }
}
