export const soDigitos = (valor) => String(valor ?? '').replace(/\D/g, '')

export const mascaraCep = (valor) =>
  soDigitos(valor)
    .slice(0, 8)
    .replace(/^(\d{5})(\d)/, '$1-$2')

export const mascaraCnpj = (valor) =>
  soDigitos(valor)
    .slice(0, 14)
    .replace(/^(\d{2})(\d)/, '$1.$2')
    .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1/$2')
    .replace(/(\d{4})(\d)/, '$1-$2')

export function mascaraTelefone(valor) {
  const d = soDigitos(valor).slice(0, 11)
  if (d.length <= 2) return d
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}

export function cnpjValido(valor) {
  const n = soDigitos(valor)
  if (n.length !== 14 || /^(\d)\1+$/.test(n)) return false
  const digito = (base) => {
    let soma = 0
    let peso = base.length - 7
    for (const c of base) {
      soma += Number(c) * peso--
      if (peso < 2) peso = 9
    }
    const resto = soma % 11
    return resto < 2 ? 0 : 11 - resto
  }
  const d1 = digito(n.slice(0, 12))
  const d2 = digito(n.slice(0, 12) + d1)
  return n.endsWith(`${d1}${d2}`)
}

export const moeda = (valor) =>
  valor != null ? valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—'

// Cliente: nome e sobrenome ficam separados; nas listas aparece o nome completo
export const nomeCompleto = (pessoa) => [pessoa?.nome, pessoa?.sobrenome].filter(Boolean).join(' ')
