import { Avatar } from 'antd'

const iniciais = (nome = '') =>
  nome
    .replace(/^(Dra?\.|Prof\.?)\s+/i, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')

// Quem está logado, no canto da barra superior
export default function Usuario({ nome, detalhe }) {
  return (
    <div className="casca-usuario" title={detalhe ? `${nome} (${detalhe})` : nome}>
      <Avatar size={32} className="casca-usuario-avatar">
        {iniciais(nome)}
      </Avatar>
      <div className="casca-usuario-textos">
        <strong>{nome}</strong>
        {detalhe && <span>{detalhe}</span>}
      </div>
    </div>
  )
}
