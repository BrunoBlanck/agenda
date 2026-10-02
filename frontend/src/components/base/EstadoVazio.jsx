// Lista ou tela sem dados: diz o que é e, quando der, oferece a ação
export default function EstadoVazio({ titulo, descricao, acao, icone, compacto = false }) {
  return (
    <div className={compacto ? 'estado-vazio compacto' : 'estado-vazio'}>
      {icone && <span className="estado-vazio-icone" aria-hidden="true">{icone}</span>}
      <strong>{titulo}</strong>
      {descricao && <span>{descricao}</span>}
      {acao}
    </div>
  )
}
