import { Typography } from 'antd'
import dayjs from 'dayjs'
import { SITE, useData } from '../data/DataContext.jsx'

// "Última alteração por Fulano em 02/10/2026 14:30" a partir de atualizadoPor/atualizadoEm
export default function UltimaAlteracao({ item }) {
  const { funcionarios } = useData()
  if (!item?.atualizadoEm) return null
  const nome =
    funcionarios.todos.find((f) => f.id === item.atualizadoPor)?.nome ??
    (item.atualizadoPor === SITE || item.origem === 'site' ? 'o cliente, pelo site' : 'Superadmin')
  return (
    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
      Última alteração por {nome} em {dayjs(item.atualizadoEm).format('DD/MM/YYYY HH:mm')}
    </Typography.Text>
  )
}
