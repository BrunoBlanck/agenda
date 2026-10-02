// Filtros à esquerda (quebram linha no celular) e ações da lista à direita
export default function BarraFiltros({ acoes, children }) {
  return (
    <div className="barra-filtros">
      <div className="barra-filtros-campos">{children}</div>
      {acoes && <div className="barra-filtros-acoes">{acoes}</div>}
    </div>
  )
}
