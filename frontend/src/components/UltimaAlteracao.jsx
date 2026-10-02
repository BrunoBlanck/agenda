import { SITE, useData } from '../data/DataContext.jsx'
import { dataHoraBR } from '../utils/formatos.js'

// "Última alteração por Fulano em 02/10/2026 às 14:30" a partir de atualizadoPor/atualizadoEm
export default function UltimaAlteracao({ item }) {
  const { funcionarios } = useData()
  if (!item?.atualizadoEm) return null
  const nome =
    funcionarios.todos.find((f) => f.id === item.atualizadoPor)?.nome ??
    (item.atualizadoPor === SITE || item.origem === 'site' ? 'o cliente, pelo site' : 'Superadmin')
  return (
    <span className="texto-apoio">
      Última alteração por {nome} em {dataHoraBR(item.atualizadoEm)}
    </span>
  )
}
