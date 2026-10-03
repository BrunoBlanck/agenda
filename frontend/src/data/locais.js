// Como a loja chama os locais na tela (Sala, Cadeira, Consultório...), a partir de eu.loja (API)
export const rotulosLocal = (loja) => ({
  singular: loja?.rotuloLocal || 'Local',
  plural: loja?.rotuloLocalPlural || 'Locais',
})
