import { EnvironmentOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { EtiquetaTipoLocal } from './Etiquetas.jsx'

// Local do agendamento com o tipo à vista (Presencial ou Online)
export default function LocalInfo({ local }) {
  if (!local) return <span className="texto-apoio">Sem local</span>
  return (
    <span className="local-info">
      {local.tipo === 'online' ? <VideoCameraOutlined aria-hidden="true" /> : <EnvironmentOutlined aria-hidden="true" />}
      {local.nome}
      <EtiquetaTipoLocal tipo={local.tipo} />
    </span>
  )
}
