import { api } from './cliente.js'
import { textoOuNulo } from './conversao.js'
import { conflitoNoCampo, lerControle } from './registro.js'

// Funcionários (/api/loja/funcionarios) e cargos (/api/loja/cargos). Recurso: funcionarios.

/** API -> tela. cor_agenda vira `cor`; perfil e cargo chegam também pelo nome. */
export const converterFuncionario = (f) => ({
  id: f.id,
  nome: f.nome ?? '',
  email: f.email ?? '',
  perfilId: f.perfil_id ?? null,
  perfilNome: f.perfil_nome ?? null,
  perfilAcessoTotal: !!f.perfil_acesso_total,
  cargoId: f.cargo_id ?? null,
  cargoNome: f.cargo_nome ?? null,
  cpf: f.cpf ?? null,
  telefone: f.telefone ?? null,
  cor: f.cor_agenda ?? null,
  ativo: f.ativo ?? true,
  ultimoLoginEm: f.ultimo_login_em ?? null,
  ...lerControle(f),
})

/**
 * Tela -> API. O PUT troca o cadastro inteiro: todo campo vai (vazio = null).
 * senha: obrigatória no cadastro; na edição só vai quando preenchida (troca a senha).
 */
const paraApi = (v) => ({
  nome: v.nome?.trim(),
  email: v.email?.trim(),
  perfil_id: v.perfilId,
  cargo_id: v.cargoId ?? null,
  cpf: textoOuNulo(v.cpf),
  telefone: textoOuNulo(v.telefone),
  cor_agenda: textoOuNulo(v.cor),
  ativo: v.ativo ?? true,
  ...(v.senha ? { senha: v.senha } : {}),
})

export const MAPA_ERROS_FUNCIONARIO = { cor_agenda: 'cor' }
const CONFLITOS = [
  ['e-mail', 'email'],
  ['CPF', 'cpf'],
]

export async function listarFuncionarios(sinal) {
  const dados = await api.loja.get('/funcionarios', { sinal })
  return (Array.isArray(dados) ? dados : []).map(converterFuncionario)
}

export const obterFuncionario = async (id, sinal) =>
  converterFuncionario(await api.loja.get(`/funcionarios/${id}`, { sinal }))

export async function salvarFuncionario(valores, id) {
  try {
    const corpo = paraApi(valores)
    const dados = id ? await api.loja.put(`/funcionarios/${id}`, corpo) : await api.loja.post('/funcionarios', corpo)
    return converterFuncionario(dados)
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITOS)
  }
}

// --- Cargos -----------------------------------------------------------------------------------

export const converterCargo = (c) => ({ id: c.id, nome: c.nome ?? '', ativo: c.ativo ?? true, ...lerControle(c) })

export async function listarCargos(sinal) {
  const dados = await api.loja.get('/cargos', { sinal })
  return (Array.isArray(dados) ? dados : []).map(converterCargo)
}

export async function salvarCargo({ nome, ativo = true }, id) {
  try {
    const corpo = { nome: nome?.trim(), ativo }
    return converterCargo(id ? await api.loja.put(`/cargos/${id}`, corpo) : await api.loja.post('/cargos', corpo))
  } catch (erro) {
    throw conflitoNoCampo(erro, [['nome', 'nome']])
  }
}

/** 409 quando há funcionários com o cargo. */
export const excluirCargo = (id) => api.loja.delete(`/cargos/${id}`)
