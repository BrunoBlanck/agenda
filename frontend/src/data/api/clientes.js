import { api } from './cliente.js'
import { lerDataHora, lerNumero, lerPagina, textoOuNulo } from './conversao.js'
import { conflitoNoCampo, lerControle } from './registro.js'

// Clientes (/api/loja/clientes) e histórico do cliente (/api/loja/clientes/{id}/historico).

/** API -> tela. data_nascimento vira `nascimento` ("AAAA-MM-DD", nunca Date). */
export const converterCliente = (c) => ({
  id: c.id,
  nome: c.nome ?? '',
  sobrenome: c.sobrenome ?? '',
  cpf: c.cpf ?? null,
  telefone: c.telefone ?? '',
  email: c.email ?? null,
  nascimento: c.data_nascimento ?? null,
  observacoes: c.observacoes ?? null,
  canais: Array.isArray(c.canais) ? c.canais : [],
  ativo: c.ativo ?? true,
  ...lerControle(c),
})

/** Tela -> API. PUT troca o cadastro inteiro: todo campo do formulário vai, vazio como null. */
const paraApi = (v) => ({
  nome: v.nome?.trim(),
  sobrenome: v.sobrenome?.trim(),
  cpf: textoOuNulo(v.cpf),
  telefone: v.telefone,
  email: textoOuNulo(v.email),
  data_nascimento: textoOuNulo(v.nascimento),
  observacoes: textoOuNulo(v.observacoes),
  canais: Array.isArray(v.canais) ? v.canais : [],
  ativo: v.ativo ?? true,
})

// 422 com nome de campo diferente na tela
export const MAPA_ERROS_CLIENTE = { data_nascimento: 'nascimento' }
const CONFLITOS = [['CPF', 'cpf']]

/** filtros: { busca, ativo: true|false|null, canal, pagina, porPagina } */
export async function listarClientes({ busca, ativo, canal, pagina = 1, porPagina = 20 } = {}, sinal) {
  const dados = await api.loja.get('/clientes', {
    query: { busca: busca?.trim().slice(0, 100), ativo, canal, pagina, por_pagina: porPagina },
    sinal,
  })
  return lerPagina(dados, converterCliente)
}

export const obterCliente = async (id, sinal) => converterCliente(await api.loja.get(`/clientes/${id}`, { sinal }))

export async function salvarCliente(valores, id) {
  try {
    const dados = id ? await api.loja.put(`/clientes/${id}`, paraApi(valores)) : await api.loja.post('/clientes', paraApi(valores))
    return converterCliente(dados)
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITOS)
  }
}

/** 409 quando o cliente tem agendamentos (a tela oferece inativar). */
export const excluirCliente = (id) => api.loja.delete(`/clientes/${id}`)

// ---------------------------------------------------------------------------------------------
// Histórico
// ---------------------------------------------------------------------------------------------

/**
 * Agendamento do histórico. inicio/fim chegam com o fuso da loja e são lidos na hora da loja.
 * Módulos desligados deixam servico_nome / local_* nulos.
 */
export function converterAtendimento(a) {
  const inicio = lerDataHora(a.inicio)
  const fim = lerDataHora(a.fim)
  return {
    id: a.id,
    inicio,
    fim,
    data: inicio?.format('YYYY-MM-DD') ?? null,
    hora: inicio?.format('HH:mm') ?? null,
    horaFim: fim?.format('HH:mm') ?? null,
    servicoNome: a.servico_nome ?? null,
    funcionarioId: a.funcionario_id ?? null,
    funcionarioNome: a.funcionario_nome ?? null,
    cor: a.cor_agenda ?? null,
    localNome: a.local_nome ?? null,
    localTipo: a.local_tipo ?? null,
    preco: lerNumero(a.preco),
    status: a.status ?? null,
    motivoCancelamento: a.motivo_cancelamento ?? null,
  }
}

const atendimentoOuNulo = (a) => (a ? converterAtendimento(a) : null)

/** filtro: 'todos' | 'concluidos' | 'faltas'. Os números do resumo não dependem do filtro. */
export async function historicoCliente(id, { filtro = 'todos', pagina = 1, porPagina = 10 } = {}, sinal) {
  const d = await api.loja.get(`/clientes/${id}/historico`, { query: { filtro, pagina, por_pagina: porPagina }, sinal })
  return {
    cliente: d?.cliente ? converterCliente(d.cliente) : null,
    concluidos: Number(d?.concluidos) || 0,
    faltas: Number(d?.faltas) || 0,
    cancelados: Number(d?.cancelados) || 0,
    totalGasto: lerNumero(d?.total_gasto) ?? 0,
    ultimo: atendimentoOuNulo(d?.ultimo),
    proximo: atendimentoOuNulo(d?.proximo),
    parcial: !!d?.parcial,
    agendamentos: lerPagina(d?.agendamentos, converterAtendimento),
  }
}

// ---------------------------------------------------------------------------------------------
// Acesso ao site (CLI-06): conta do cliente pelo telefone e códigos de confirmação pendentes.
// Só com escrita em Clientes. Datas chegam com o fuso da loja e são lidas na hora da loja.
// ---------------------------------------------------------------------------------------------

/** codigo_pendente -> { codigo, expiraEm } | null (sem código, ou código vazio = nenhum). */
const converterCodigoPendente = (c) =>
  c && typeof c.codigo === 'string' && c.codigo ? { codigo: c.codigo, expiraEm: lerDataHora(c.expira_em) } : null

/** API -> tela. criada_em/ultimo_acesso_em/codigo_pendente podem vir null. */
export const converterContaSite = (d) => ({
  possuiConta: d?.possui_conta === true,
  criadaEm: lerDataHora(d?.criada_em),
  ultimoAcessoEm: lerDataHora(d?.ultimo_acesso_em),
  codigoPendente: converterCodigoPendente(d?.codigo_pendente),
})

/** Item de GET /clientes/codigos-site. clientes vazio = telefone ainda sem cadastro. */
export const converterCodigoSite = (c) => ({
  telefone: c?.telefone ?? '',
  codigo: c?.codigo ?? '',
  expiraEm: lerDataHora(c?.expira_em),
  criadoEm: lerDataHora(c?.criado_em),
  clientes: Array.isArray(c?.clientes)
    ? c.clientes.filter((x) => x?.id).map((x) => ({ id: String(x.id), nome: x.nome ?? '' }))
    : [],
})

/** Códigos pendentes da loja, mais novo primeiro (até 100, sem paginação). */
export async function listarCodigosSite(sinal) {
  const dados = await api.loja.get('/clientes/codigos-site', { sinal })
  return Array.isArray(dados) ? dados.filter((c) => c?.codigo).map(converterCodigoSite) : []
}

export const obterContaSite = async (clienteId, sinal) =>
  converterContaSite(await api.loja.get(`/clientes/${clienteId}/conta-site`, { sinal }))

/** 204. 404 "Cliente não encontrado." ou "Este cliente não tem acesso ao site.". */
export const removerContaSite = (clienteId) => api.loja.delete(`/clientes/${clienteId}/conta-site`)
