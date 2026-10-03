import dayjs from 'dayjs'

// Conversões entre o formato da API e o da tela (funções puras; INT-09 a INT-12).
// API em snake_case, tela em camelCase. Nomes que mudam de verdade (ex.: estoque_minimo -> minimo)
// são mapeados à mão nas funções de cada área; estas aqui cobrem o caso trivial.

const paraCamelChave = (chave) => chave.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase())
const paraSnakeChave = (chave) => chave.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)

const objetoSimples = (v) => v !== null && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype

/**
 * Converte as chaves para camelCase, em profundidade.
 * preservar: chaves cujo valor fica como veio (mapas indexados por código, ex.: modulos, acessos,
 * antes/depois da auditoria), para não virar "controleTempo" o que é o código "controle_tempo".
 */
export function paraCamel(valor, preservar = []) {
  if (Array.isArray(valor)) return valor.map((v) => paraCamel(v, preservar))
  if (!objetoSimples(valor)) return valor
  const saida = {}
  for (const [chave, v] of Object.entries(valor)) {
    saida[paraCamelChave(chave)] = preservar.includes(chave) ? v : paraCamel(v, preservar)
  }
  return saida
}

/** Converte as chaves para snake_case, em profundidade (use só com os campos que a API espera). */
export function paraSnake(valor) {
  if (Array.isArray(valor)) return valor.map(paraSnake)
  if (!objetoSimples(valor)) return valor
  return Object.fromEntries(Object.entries(valor).map(([k, v]) => [paraSnakeChave(k), paraSnake(v)]))
}

/** Só os campos listados (nomes da tela), já em snake_case; undefined fica de fora. */
export function escolher(valores, campos) {
  const saida = {}
  for (const campo of campos) {
    if (valores?.[campo] !== undefined) saida[paraSnakeChave(campo)] = paraSnake(valores[campo])
  }
  return saida
}

/** Texto vazio (ou só espaços) vira null: a API trata null como "sem valor". */
export const textoOuNulo = (v) => (typeof v === 'string' ? v.trim() || null : (v ?? null))

/** Nome do campo do erro 422 ("itens.0.estoque_minimo") no caminho do Form da tela (['itens', 0, 'estoqueMinimo']). */
export const caminhoDoCampo = (campo) =>
  String(campo)
    .split('.')
    .map((parte) => (/^\d+$/.test(parte) ? Number(parte) : paraCamelChave(parte)))

// ---------------------------------------------------------------------------------------------
// Datas (INT-11). A API responde com o fuso da loja (2030-01-07T09:00:00-03:00) e lê hora sem fuso
// como hora da loja. Na tela trabalhamos sempre na "hora de parede" da loja: ao ler, vale a hora escrita
// na string (lerDataHora) e ao gravar vai sem fuso. Assim a tela mostra o horário da loja
// em qualquer fuso do navegador, e "date" puro (AAAA-MM-DD) nunca passa por Date/UTC.
// ---------------------------------------------------------------------------------------------

let fusoLoja = 'America/Sao_Paulo'

/** Chamado pela sessão ao carregar a loja (eu.loja.fuso_horario). */
export function definirFusoLoja(fuso) {
  if (fuso) fusoLoja = fuso
}

/** Agora, na hora de parede da loja. */
export function agoraNaLoja() {
  return naHoraDoFuso(new Date(), fusoLoja)
}

const EM_UTC = /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]00:?00)$/i

/** Instante (Date) na hora de parede de um fuso, como dayjs. */
function naHoraDoFuso(instante, fuso) {
  try {
    const texto = new Intl.DateTimeFormat('sv-SE', {
      timeZone: fuso,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    }).format(instante)
    return dayjs(texto.replace(' ', 'T'))
  } catch {
    return dayjs(instante) // fuso desconhecido no navegador
  }
}

/**
 * Data e hora da API -> dayjs na hora de parede da loja. null/inválido -> null.
 * A API manda no fuso da própria loja ("2030-01-07T09:00:00-03:00", ou -04:00 numa loja de Manaus):
 * vale a hora escrita na string (09:00), sem reconverter para outro fuso — assim uma loja de outro
 * fuso aparece certa até no SUPERADMIN, e reenviar sem fuso devolve o mesmo valor.
 * Só UTC ("Z" ou +00:00, de alguma rota sem loja) é levado ao fuso da sessão (fuso = outro, se informado).
 * Sem fuso, é lido como hora da loja.
 */
export function lerDataHora(iso, fuso = fusoLoja) {
  if (!iso || typeof iso !== 'string') return null
  if (EM_UTC.test(iso) && fuso !== 'UTC' && fuso !== 'Etc/UTC') {
    const instante = new Date(iso)
    return Number.isNaN(instante.getTime()) ? null : naHoraDoFuso(instante, fuso)
  }
  const d = dayjs(iso.slice(0, 19))
  return d.isValid() ? d : null
}

/** "2030-01-07" -> dayjs local do dia (sem passar por UTC). */
export function lerData(texto) {
  if (!texto || typeof texto !== 'string') return null
  const d = dayjs(texto.slice(0, 10))
  return d.isValid() ? d : null
}

/** dayjs/Date/texto -> "AAAA-MM-DDTHH:mm:ss" (hora da loja, sem fuso). */
export const enviarDataHora = (valor) => (valor ? dayjs(valor).format('YYYY-MM-DDTHH:mm:ss') : null)

/** dayjs/Date/texto -> "AAAA-MM-DD". */
export const enviarData = (valor) => (valor ? dayjs(valor).format('YYYY-MM-DD') : null)

/** "09:00:00" -> "09:00" (campos time da API). */
export const lerHora = (texto) => (typeof texto === 'string' && texto.length >= 5 ? texto.slice(0, 5) : null)

// ---------------------------------------------------------------------------------------------
// Dinheiro e quantidades (INT-12): número com no máximo 2 casas
// ---------------------------------------------------------------------------------------------

export function enviarNumero(valor, casas = 2) {
  if (valor === null || valor === undefined || valor === '') return null
  const n = Number(valor)
  if (!Number.isFinite(n)) return null
  const fator = 10 ** casas
  return Math.round(n * fator) / fator
}

export const lerNumero = (valor) => {
  if (valor === null || valor === undefined || valor === '') return null
  const n = Number(valor)
  return Number.isFinite(n) ? n : null
}

// ---------------------------------------------------------------------------------------------
// Paginação (INT-13): { itens, total, pagina, por_pagina } -> { itens, total, pagina, porPagina }
// ---------------------------------------------------------------------------------------------

export function lerPagina(dados, converter = (x) => x) {
  return {
    itens: (dados?.itens ?? []).map(converter),
    total: Number(dados?.total) || 0,
    pagina: Number(dados?.pagina) || 1,
    porPagina: Number(dados?.por_pagina) || 20,
  }
}
