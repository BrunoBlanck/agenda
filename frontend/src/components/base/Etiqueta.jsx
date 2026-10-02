// Etiqueta de status com tom semântico: neutro, tinta, sucesso, atencao, perigo, marca (marca-texto) ou contorno.
// O tom nunca vem sozinho: sempre há texto, e os status trazem ícone (components/Etiquetas.jsx).
export default function Etiqueta({ tom = 'neutro', icone, title, children }) {
  return (
    <span className={`etiqueta etiqueta-${tom}`} title={title}>
      {icone}
      {children}
    </span>
  )
}
