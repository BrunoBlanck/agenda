import { api, urlDaApi } from './cliente.js'
import { textoOuNulo } from './conversao.js'
import { lerControle } from './registro.js'

// Configurações > Dados da loja (GET/PUT /api/loja/configuracoes/loja, PUT/DELETE .../logo). Recurso: config_loja.

// Campos que a própria loja edita (o resto é definido pela plataforma)
const CAMPOS_EDITAVEIS = [
  ['nomeFantasia', 'nome_fantasia'],
  ['nome', 'nome'],
  ['cnpj', 'cnpj'],
  ['telefone', 'telefone'],
  ['email', 'email'],
  ['cep', 'cep'],
  ['logradouro', 'logradouro'],
  ['numero', 'numero'],
  ['complemento', 'complemento'],
  ['bairro', 'bairro'],
  ['cidade', 'cidade'],
  ['uf', 'uf'],
]

export function converterDadosLoja(d, fuso) {
  const editaveis = Object.fromEntries(CAMPOS_EDITAVEIS.map(([tela, campoApi]) => [tela, d?.[campoApi] ?? null]))
  return {
    ...editaveis,
    // caminho relativo da API (/api/arquivos/logos/...) -> endereço utilizável no src da imagem
    logoUrl: urlDaApi(d?.logo_url),
    tipo: d?.tipo ?? null,
    slug: d?.slug ?? '',
    planoNome: d?.plano_nome ?? null,
    status: d?.status ?? null,
    fusoHorario: d?.fuso_horario ?? null,
    // mapa por código do módulo (controle_tempo...): fica como veio
    modulos: d?.modulos && typeof d.modulos === 'object' ? d.modulos : {},
    ...lerControle(d, fuso),
  }
}

const corpoDadosLoja = (valores) =>
  Object.fromEntries(
    CAMPOS_EDITAVEIS.map(([tela, campoApi]) => [
      campoApi,
      tela === 'nomeFantasia' || tela === 'nome' ? (valores[tela] ?? '').trim() : textoOuNulo(valores[tela]),
    ]),
  )

export const obterDadosLoja = async (fuso, sinal) =>
  converterDadosLoja(await api.loja.get('/configuracoes/loja', { sinal }), fuso)

export const salvarDadosLoja = async (valores, fuso) =>
  converterDadosLoja(await api.loja.put('/configuracoes/loja', corpoDadosLoja(valores)), fuso)

/** Multipart, campo "arquivo" (PNG, JPEG ou WebP, até 2 MB). Resolve com os dados da loja (já com a logo nova). */
export async function enviarLogoLoja(arquivo, fuso) {
  const corpo = new FormData()
  corpo.append('arquivo', arquivo)
  return converterDadosLoja(await api.loja.put('/configuracoes/loja/logo', corpo), fuso)
}

export const removerLogoLoja = () => api.loja.delete('/configuracoes/loja/logo')
