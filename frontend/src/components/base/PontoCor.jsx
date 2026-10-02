// Bolinha com a cor do profissional na agenda
export default function PontoCor({ cor }) {
  return <span className="ponto-cor" style={{ background: cor }} aria-hidden="true" />
}
