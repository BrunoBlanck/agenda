import { api } from './cliente.js'
import { enviarDataHora, lerDataHora, lerHora, textoOuNulo } from './conversao.js'
import { conflitoNoCampo, lerControle } from './registro.js'

// Configurações › Perfis e horários: catálogo de recursos, perfis e níveis (perfis_acesso),
// jornada semanal e bloqueios (config_agendamentos).

// --- Catálogo de recursos -----------------------------------------------------------------------

// leitura/escrita: o que cada nível permite (texto pronto da API). descricao fica só como reserva
// para a tela, se os dois vierem vazios.
const textoOuNada = (v) => (typeof v === 'string' && v.trim() ? v.trim() : null)

export function converterRecurso(r) {
  return {
    codigo: r.codigo,
    nome: r.nome ?? r.codigo,
    descricao: textoOuNada(r.descricao),
    leitura: textoOuNada(r.leitura),
    escrita: textoOuNada(r.escrita),
    modulo: r.modulo ?? null,
    moduloAtivo: !!r.modulo_ativo,
    ordem: r.ordem ?? null,
  }
}

export async function listarRecursos(sinal) {
  const dados = await api.loja.get('/recursos', { sinal })
  return (Array.isArray(dados) ? dados : []).map(converterRecurso)
}

// --- Perfis -------------------------------------------------------------------------------------

/**
 * acessos: mapa código do recurso -> nível, como veio (null quando o usuário não tem leitura em
 * Perfis de acesso: a API não manda os níveis). funcionarios: [{ id, nome, ativo }].
 */
export const converterPerfil = (p) => ({
  id: p.id,
  nome: p.nome ?? '',
  descricao: p.descricao ?? null,
  padrao: !!p.padrao,
  acessoTotal: !!p.acesso_total,
  acessos: p.acessos && typeof p.acessos === 'object' ? p.acessos : null,
  funcionarios: (Array.isArray(p.funcionarios) ? p.funcionarios : []).map((f) => ({
    id: f.id,
    nome: f.nome ?? '',
    ativo: f.ativo ?? true,
  })),
  semJornada: !!p.sem_jornada,
  ...lerControle(p),
})

const CONFLITO_NOME = [['nome', 'nome']]

export async function listarPerfis(sinal) {
  const dados = await api.loja.get('/perfis', { sinal })
  return (Array.isArray(dados) ? dados : []).map(converterPerfil)
}

export const obterPerfil = async (id, sinal) => converterPerfil(await api.loja.get(`/perfis/${id}`, { sinal }))

/** Novo perfil; copiarDe copia os níveis e a jornada de outro perfil. */
export async function criarPerfil({ nome, descricao, copiarDe }) {
  try {
    const dados = await api.loja.post('/perfis', {
      nome: nome?.trim(),
      descricao: textoOuNulo(descricao),
      copiar_de: copiarDe ?? null,
    })
    return converterPerfil(dados)
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITO_NOME)
  }
}

/** Renomear / mudar a descrição. O PUT troca os dois: mande sempre nome e descrição. */
export async function editarPerfil(id, { nome, descricao }) {
  try {
    return converterPerfil(await api.loja.put(`/perfis/${id}`, { nome: nome?.trim(), descricao: textoOuNulo(descricao) }))
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITO_NOME)
  }
}

/** acessos: { codigo: 'nenhum' | 'leitura' | 'escrita' }; os não citados não mudam. Devolve o perfil. */
export const definirAcessos = async (id, acessos) =>
  converterPerfil(await api.loja.put(`/perfis/${id}/acessos`, { acessos }))

/** 409: perfil padrão ou com funcionários. Leva junto a jornada e os bloqueios do perfil. */
export const excluirPerfil = (id) => api.loja.delete(`/perfis/${id}`)

// --- Jornada semanal ----------------------------------------------------------------------------

/** dia_semana: 0 = domingo ... 6 = sábado. Horas "HH:mm". */
export const converterHorario = (h) => ({
  id: h.id,
  perfilId: h.perfil_id ?? null,
  diaSemana: Number(h.dia_semana),
  inicio: lerHora(h.hora_inicio) ?? '',
  fim: lerHora(h.hora_fim) ?? '',
  ...lerControle(h),
})

export async function listarHorarios(perfilId, sinal) {
  const dados = await api.loja.get('/horarios', { query: { perfil_id: perfilId }, sinal })
  return (Array.isArray(dados) ? dados : []).map(converterHorario)
}

export const adicionarHorario = async (perfilId, { diaSemana, inicio, fim }) =>
  converterHorario(
    await api.loja.post(`/perfis/${perfilId}/horarios`, { dia_semana: diaSemana, hora_inicio: inicio, hora_fim: fim }),
  )

export const removerHorario = (id) => api.loja.delete(`/horarios/${id}`)

// --- Bloqueios ----------------------------------------------------------------------------------

/**
 * inicio/fim: dayjs na hora da loja. alvo: 'loja' | 'perfil' | 'funcionario';
 * quem: nome do funcionário ou do perfil (null = loja inteira).
 */
export const converterBloqueio = (b) => ({
  id: b.id,
  perfilId: b.perfil_id ?? null,
  funcionarioId: b.funcionario_id ?? null,
  inicio: lerDataHora(b.inicio),
  fim: lerDataHora(b.fim),
  motivo: b.motivo ?? null,
  alvo: b.alvo ?? (b.funcionario_id ? 'funcionario' : b.perfil_id ? 'perfil' : 'loja'),
  quem: b.quem ?? null,
  ...lerControle(b),
})

/** Os da loja inteira, os do perfil e os de cada funcionário dele. */
export async function listarBloqueios(perfilId, sinal) {
  const dados = await api.loja.get('/bloqueios', { query: { perfil_id: perfilId }, sinal })
  return (Array.isArray(dados) ? dados : []).map(converterBloqueio)
}

/** perfilId e funcionarioId nulos = loja inteira. inicio/fim: dayjs na hora da loja. */
export const criarBloqueio = async ({ perfilId = null, funcionarioId = null, inicio, fim, motivo }) =>
  converterBloqueio(
    await api.loja.post('/bloqueios', {
      perfil_id: perfilId,
      funcionario_id: funcionarioId,
      inicio: enviarDataHora(inicio),
      fim: enviarDataHora(fim),
      motivo: textoOuNulo(motivo),
    }),
  )

export const removerBloqueio = (id) => api.loja.delete(`/bloqueios/${id}`)
