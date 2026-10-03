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
// Tokens: em memória + sessionStorage (sobrevive ao F5, some ao fechar a aba). Um por sessão:
// 'superadmin' e uma por loja ('loja.clinica-sorriso'), para duas lojas em abas diferentes não se misturarem.
// ---------------------------------------------------------------------------------------------

const PREFIXO = 'agenda.sessao.'
const memoria = {}
// Chave de sessão das requisições api.loja: a loja do painel aberto nesta aba (o slug da URL)
let sessaoDaLoja = null

/** Chave de sessão da área: 'superadmin', ou 'loja.<slug>' no painel da loja. */
export const chaveSessao = (area, slug) => (area === 'loja' ? (slug ? `loja.${slug}` : null) : area)

/** O painel da loja da URL passa a ser o dono do token usado por api.loja (chamado pela sessão da loja). */
export function usarSessaoDaLoja(chave) {
  sessaoDaLoja = chave
}

function armazenamento() {
  try {
    return window.sessionStorage
  } catch {
    return null // navegação privada com storage bloqueado: fica só em memória
  }
}

// Restos da versão com a loja digitada no login (uma sessão de loja por aba e a última loja lembrada)
try {
  armazenamento()?.removeItem('agenda.sessao.loja')
  window.localStorage?.removeItem('agenda.ultimaLoja')
} catch {
  // storage bloqueado: nada a limpar
}

export const tokens = {
  ler(chave) {
    if (!chave) return null
    if (memoria[chave] === undefined) memoria[chave] = armazenamento()?.getItem(PREFIXO + chave) ?? null
    return memoria[chave]
  },
  gravar(chave, token) {
    if (!chave) return
    memoria[chave] = token
    try {
      armazenamento()?.setItem(PREFIXO + chave, token)
    } catch {
      // cota cheia ou storage bloqueado: segue só em memória
    }
  },
  limpar(chave) {
    if (!chave) return
    memoria[chave] = null
    try {
      armazenamento()?.removeItem(PREFIXO + chave)
    } catch {
      // nada a limpar
    }
  },
}

// Sessão expirada (401 com token): a sessão daquela chave limpa o estado e leva ao login
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
  // O site é público: nunca leva token. A loja usa o token da loja aberta nesta aba.
  const sessao = area === 'loja' ? sessaoDaLoja : area === 'superadmin' ? 'superadmin' : null
  const token = tokens.ler(sessao)
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
  // Só se o token ainda é o mesmo: um login novo feito nesse meio tempo não é desfeito
  if (status === 401 && token && tokens.ler(sessao) === token) {
    tokens.limpar(sessao)
    ouvintesExpirou.forEach((fn) => fn(sessao))
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
