// Marca da plataforma (a mesma do favicon): página da agenda com um horário marcado a marca-texto
export default function MarcaPlataforma({ tamanho = 36 }) {
  return (
    <svg className="marca-plataforma" width={tamanho} height={tamanho} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="var(--cor-tinta)" />
      <path d="M8 11h16M8 16h16M8 21h16" stroke="#fff" strokeOpacity=".35" strokeWidth="1.5" />
      <rect x="7" y="13.5" width="14" height="5" rx="1.5" fill="var(--cor-marca-texto)" />
    </svg>
  )
}
