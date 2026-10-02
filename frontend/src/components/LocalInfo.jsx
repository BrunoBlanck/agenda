import { Tag, Typography } from 'antd'
import { EnvironmentOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { tiposLocal } from '../data/mock.js'

// Local do agendamento com o tipo à vista: "Sala 101 · Presencial" ou "Online · Dr. Carlos · Online"
export default function LocalInfo({ local, secundario = false }) {
  if (!local) return <Typography.Text type="secondary">Sem local</Typography.Text>
  const tipo = tiposLocal[local.tipo] ?? tiposLocal.presencial
  return (
    <Typography.Text type={secundario ? 'secondary' : undefined}>
      {local.tipo === 'online' ? <VideoCameraOutlined /> : <EnvironmentOutlined />} {local.nome}{' '}
      <Tag color={tipo.color} style={{ marginInlineStart: 4 }}>
        {tipo.label}
      </Tag>
    </Typography.Text>
  )
}
