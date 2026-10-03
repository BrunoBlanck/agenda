// Único lugar do front-end que chama fetch (skill integracao-api, INT-01).
// Três áreas com caminhos e tokens próprios: painel da loja, SUPERADMIN e site do consumidor (público).
// Toda falha vira ErroApi { status, mensagem, campos, tentarEm }; status 0 = sem conexão ou tempo esgotado.

const ORIGEM = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')
const BASE = `${ORIGEM}/api`
const TEMPO_LIMITE = 15_000
// Envio de arquivo (logo até 2 MB) numa conexão lenta passa de 15 s
const TEMPO_LIMITE_ARQUIVO = 120_000

export const MSG_SEM_CONEXAO = 'Sem conexão com o servidor. Tente de novo.'
const MSG_GENERICA = 'Não foi possível concluir a operação. Tente novamente em instantes.'
const MSG_POR_STATUS = {
  400: 'Requisição inválida.',
  401: 'Faça login para continuar.',
  403: 'Você não tem permissão para esta ação.',
  404: 'Não encontrado.',
  409: 'Conflito com dados existentes.',
  413: 'O envio passou do tamanho máximo permitido.',
  422: 'Verifique os dados informados.',
  429: 'Muitas requisições. Aguarde um pouco e tente novamente.',
}

export class ErroApi extends Error {
  constructor({ status, mensagem, campos = [], tentarEm = null }) {
    super(mensagem)
    this.name = 'ErroApi'
    this.status = status
    this.mensagem = mensagem
    // [{ campo: 'telefone' | 'itens.0.quantidade', mensagem }] (nomes da API, snake_case)
    this.campos = campos
    // 429: segundos até poder tentar de novo (header Retry-After)
    this.tentarEm = tentarEm
  }
}

// Endereço de um arquivo servido pela API (ex.: logo_url "/api/arquivos/logos/..."), também quando a API
// fica em outra origem (VITE_API_URL). Endereço absoluto ou vazio volta como veio.
export const urlDaApi = (caminho) =>
  typeof caminho === 'string' && caminho.startsWith('/api/') ? `${ORIGEM}${caminho}` : caminho || null

// Requisição cancelada por quem chamou (tela desmontou, busca mais nova): quem chamou ignora
export const foiCancelada = (erro) => erro?.name === 'AbortError'

// ---------------------------------------------------------------------------------------------
// Tokens: em memória + sessionStorage (sobrevive ao F5, some ao fechar a aba). Um por área.
// ---------------------------------------------------------------------------------------------

const CHAVE = { loja: 'agenda.sessao.loja', superadmin: 'agenda.sessao.superadmin' }
const memoria = {}

function armazenamento() {
  try {
    return window.sessionStorage
  } catch {
    return null // navegação privada com storage bloqueado: fica só em memória
  }
}

export const tokens = {
  ler(area) {
    if (!(area in CHAVE)) return null
    if (memoria[area] === undefined) memoria[area] = armazenamento()?.getItem(CHAVE[area]) ?? null
    return memoria[area]
  },
  gravar(area, token) {
    memoria[area] = token
    try {
      armazenamento()?.setItem(CHAVE[area], token)
    } catch {
      // cota cheia ou storage bloqueado: segue só em memória
    }
  },
  limpar(area) {
    memoria[area] = null
    try {
      armazenamento()?.removeItem(CHAVE[area])
    } catch {
      // nada a limpar
    }
  },
}

// Sessão expirada (401 com token): a área limpa o estado e leva ao login
const ouvintesExpirou = new Set()
export function aoExpirarSessao(fn) {
  ouvintesExpirou.add(fn)
  return () => ouvintesExpirou.delete(fn)
}

// ---------------------------------------------------------------------------------------------

function montarUrl(area, caminho, query) {
  const url = `${BASE}/${area}${caminho}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [chave, valor] of Object.entries(query)) {
    if (valor === undefined || valor === null || valor === '') continue
    if (Array.isArray(valor)) valor.forEach((v) => params.append(chave, v))
    else params.append(chave, valor)
  }
  const texto = params.toString()
  return texto ? `${url}?${texto}` : url
}

async function lerCorpo(resposta) {
  if (resposta.status === 204) return null
  const texto = await resposta.text()
  if (!texto) return null
  try {
    return JSON.parse(texto)
  } catch {
    return undefined // não é JSON (página de erro de proxy, por exemplo)
  }
}

/**
 * area: 'loja' | 'superadmin' | 'site'. caminho: a partir da área ('/clientes').
 * corpo: objeto já no formato da API (snake_case), ou FormData para envio de arquivo (multipart).
 * query: filtros (vazios são omitidos).
 * sinal: AbortSignal de quem chamou (cancelar não vira erro de conexão).
 */
export async function requisitar(area, metodo, caminho, { corpo, query, sinal } = {}) {
  const token = tokens.ler(area)
  const arquivo = typeof FormData !== 'undefined' && corpo instanceof FormData
  const controle = new AbortController()
  let esgotou = false
  const relogio = setTimeout(() => {
    esgotou = true
    controle.abort()
  }, arquivo ? TEMPO_LIMITE_ARQUIVO : TEMPO_LIMITE)
  const cancelarJunto = () => controle.abort()
  if (sinal?.aborted) controle.abort()
  sinal?.addEventListener('abort', cancelarJunto, { once: true })

  let resposta
  try {
    resposta = await fetch(montarUrl(area, caminho, query), {
      method: metodo,
      headers: {
        Accept: 'application/json',
        // FormData: o navegador põe o Content-Type multipart com o boundary
        ...(corpo !== undefined && !arquivo && { 'Content-Type': 'application/json' }),
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: corpo === undefined ? undefined : arquivo ? corpo : JSON.stringify(corpo),
      signal: controle.signal,
    })
  } catch (erro) {
    if (!esgotou && (sinal?.aborted || erro?.name === 'AbortError')) throw erro
    throw new ErroApi({ status: 0, mensagem: MSG_SEM_CONEXAO })
  } finally {
    clearTimeout(relogio)
    sinal?.removeEventListener('abort', cancelarJunto)
  }

  let dados
  try {
    dados = await lerCorpo(resposta)
  } catch (erro) {
    if (sinal?.aborted) throw erro
    throw new ErroApi({ status: 0, mensagem: MSG_SEM_CONEXAO })
  }

  if (resposta.ok) {
    if (dados === undefined) throw new ErroApi({ status: resposta.status, mensagem: MSG_GENERICA })
    return dados
  }

  const status = resposta.status
  // 401 com token = sessão vencida ou revogada. Sem token (login errado) é só a mensagem.
  if (status === 401 && token) {
    tokens.limpar(area)
    ouvintesExpirou.forEach((fn) => fn(area))
  }
  const detalhe = typeof dados?.detail === 'string' ? dados.detail : null
  const tentarEm = Number(resposta.headers.get('Retry-After')) || null
  throw new ErroApi({
    status,
    mensagem: detalhe ?? MSG_POR_STATUS[status] ?? MSG_GENERICA,
    campos: Array.isArray(dados?.erros) ? dados.erros : [],
    tentarEm,
  })
}

const metodos = (area) => ({
  get: (caminho, opcoes) => requisitar(area, 'GET', caminho, opcoes),
  post: (caminho, corpo, opcoes) => requisitar(area, 'POST', caminho, { ...opcoes, corpo: corpo ?? {} }),
  put: (caminho, corpo, opcoes) => requisitar(area, 'PUT', caminho, { ...opcoes, corpo: corpo ?? {} }),
  patch: (caminho, corpo, opcoes) => requisitar(area, 'PATCH', caminho, { ...opcoes, corpo: corpo ?? {} }),
  delete: (caminho, opcoes) => requisitar(area, 'DELETE', caminho, opcoes),
})

export const api = {
  loja: metodos('loja'),
  superadmin: metodos('superadmin'),
  site: metodos('site'),
}
