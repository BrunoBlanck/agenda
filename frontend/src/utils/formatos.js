import dayjs from 'dayjs'
import { lerData, lerDataHora } from '../data/api/conversao.js'

export const soDigitos = (valor) => String(valor ?? '').replace(/\D/g, '')

export const mascaraCep = (valor) =>
  soDigitos(valor)
    .slice(0, 8)
    .replace(/^(\d{5})(\d)/, '$1-$2')

export const mascaraCpf = (valor) =>
  soDigitos(valor)
    .slice(0, 11)
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2')

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

const formatoMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

// Aceita número ou texto numérico (a API manda número; nunca mostra "NaN")
export const moeda = (valor) => {
  if (valor === null || valor === undefined || valor === '') return '—'
  const n = Number(valor)
  return Number.isFinite(n) ? formatoMoeda.format(n) : '—'
}

// Cliente: nome e sobrenome ficam separados; nas listas aparece o nome completo
export const nomeCompleto = (pessoa) => [pessoa?.nome, pessoa?.sobrenome].filter(Boolean).join(' ')

export const capitalizar = (texto = '') => texto.charAt(0).toUpperCase() + texto.slice(1)

// Endereço da loja (slug): minúsculas, números e hífens entre eles, ex.: clinica-sorriso
export const PADRAO_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
// Endereços do próprio sistema, que nunca são loja (PLA-16). Cópia da lista de backend/app/services/slugs.py
// (SLUGS_RESERVADOS, que vale de verdade: 422 na API e CHECK no banco): mudou lá, mude aqui.
// Aqui ela evita que /superadmin/painel (e afins) abra o painel de uma "loja" que não existe.
export const SLUGS_RESERVADOS = new Set([
  'superadmin',
  'api',
  'painel',
  'site',
  'docs',
  'redoc',
  'openapi',
  'admin',
  'login',
  'static',
  'assets',
  'app',
  'www',
  'saude',
  'health',
])
export const slugValido = (valor) => PADRAO_SLUG.test(valor ?? '') && !SLUGS_RESERVADOS.has(valor)

// "1 atendimento", "3 atendimentos"
export const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`

// "Limpeza", "Limpeza e Clareamento", "Avaliação, Limpeza e Clareamento"
const formatoLista = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' })
export const listaEmTexto = (nomes) => formatoLista.format(nomes)

// Datas da API: "AAAA-MM-DD" ou ISO com fuso (mostradas na hora da loja, ver data/api/conversao.js);
// dayjs também é aceito. Vazio ou inválido vira "—".
const paraDayjs = (data) => {
  if (!data) return null
  if (typeof data === 'string') return data.length <= 10 ? lerData(data) : lerDataHora(data)
  const d = dayjs(data)
  return d.isValid() ? d : null
}

export const dataBR = (data) => paraDayjs(data)?.format('DD/MM/YYYY') ?? '—'

export const dataHoraBR = (data) => paraDayjs(data)?.format('DD/MM/YYYY [às] HH:mm') ?? '—'

// "09:00" -> "9h", "14:30" -> "14h30" (como a recepção fala e escreve na agenda)
export function horaCurta(hora) {
  if (!hora) return '—'
  const [h, m] = hora.split(':')
  return `${Number(h)}h${m === '00' ? '' : m}`
}

// 45 -> "45 min", 90 -> "1h30", 120 -> "2h"
export function duracaoTexto(minutos) {
  if (minutos == null) return '—'
  if (minutos < 60) return `${minutos} min`
  const resto = minutos % 60
  return `${Math.floor(minutos / 60)}h${resto ? String(resto).padStart(2, '0') : ''}`
}
