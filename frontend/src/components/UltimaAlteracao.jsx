import { dataHoraBR } from '../utils/formatos.js'

// "Última alteração por Fulano em 02/10/2026 às 14:30" a partir de atualizadoEm/atualizadoPorNome (API).
// Sem nome (alterado pelo superadmin, pelo cliente no site ou por uma rotina), a API não diz quem foi:
// mostra só quando, para não afirmar um autor que pode estar errado.
export default function UltimaAlteracao({ item }) {
  if (!item?.atualizadoEm) return null
  const nome = item.atualizadoPorNome
  return (
    <span className="texto-apoio">
      Última alteração{nome ? ` por ${nome}` : ''} em {dataHoraBR(item.atualizadoEm)}
    </span>
  )
}
