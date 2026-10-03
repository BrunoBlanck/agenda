import { api } from './cliente.js'
import { enviarNumero, lerNumero, lerPagina, textoOuNulo } from './conversao.js'
import { apontarCampo, conflitoNoCampo, lerControle, lerMomentoNaLoja } from './registro.js'

// Materiais, categorias e estoque (/api/loja/materiais, /api/loja/categorias-material). Recurso: materiais.
// O estoque (quantidade_atual) só muda por movimentação: o cadastro lança a quantidade inicial como
// entrada; entradas, ajustes e perdas são lançados à parte; a saída por atendimento é automática.

const lista = (v) => (Array.isArray(v) ? v : [])

export const converterMaterial = (m, fuso) => ({
  id: m.id,
  nome: m.nome ?? '',
  categoriaId: m.categoria_id ?? null,
  categoriaNome: m.categoria_nome ?? null,
  unidade: m.unidade ?? '',
  quantidade: lerNumero(m.quantidade_atual) ?? 0,
  minimo: lerNumero(m.estoque_minimo) ?? 0,
  ativo: m.ativo !== false,
  // Abaixo do mínimo (calculado pela API)
  repor: m.repor === true,
  ...lerControle(m, fuso),
})

const corpoMaterial = (v, novo) => ({
  nome: (v.nome ?? '').trim(),
  categoria_id: v.categoriaId ?? null,
  unidade: textoOuNulo(v.unidade) ?? 'un',
  estoque_minimo: enviarNumero(v.minimo) ?? 0,
  ativo: v.ativo ?? true,
  ...(novo && { quantidade_inicial: enviarNumero(v.quantidadeInicial) ?? 0 }),
})

// Nomes da API que mudam na tela (categoria_id e quantidade_inicial convertem sozinhos)
export const MAPA_ERROS_MATERIAL = { estoque_minimo: 'minimo' }

// 409 de unicidade (backend/app/erros.py, materiais_nome_uk e categorias_material_nome_uk): ao lado do campo
const CONFLITO_MATERIAL = [['material com este nome', 'nome']]
const CONFLITO_CATEGORIA = [['categoria com este nome', 'nome']]

const CAMPOS_DAS_REGRAS_MATERIAL = [
  [/categoria/i, 'categoria_id'],
  [/estoque passaria/i, 'quantidade_inicial'],
]

export const listarMateriais = async (fuso, sinal) =>
  lista(await api.loja.get('/materiais', { sinal })).map((m) => converterMaterial(m, fuso))

export const obterMaterial = async (id, fuso, sinal) => converterMaterial(await api.loja.get(`/materiais/${id}`, { sinal }), fuso)

export async function salvarMaterial(valores, id, fuso) {
  const corpo = corpoMaterial(valores, !id)
  try {
    const dados = id ? await api.loja.put(`/materiais/${id}`, corpo) : await api.loja.post('/materiais', corpo)
    return converterMaterial(dados, fuso)
  } catch (erro) {
    throw apontarCampo(conflitoNoCampo(erro, CONFLITO_MATERIAL), CAMPOS_DAS_REGRAS_MATERIAL)
  }
}

export const excluirMaterial = (id) => api.loja.delete(`/materiais/${id}`)

// --- Categorias -------------------------------------------------------------------------------

export const converterCategoria = (c, fuso) => ({ id: c.id, nome: c.nome ?? '', ...lerControle(c, fuso) })

export const listarCategorias = async (fuso, sinal) =>
  lista(await api.loja.get('/categorias-material', { sinal })).map((c) => converterCategoria(c, fuso))

export async function salvarCategoria({ nome }, id, fuso) {
  const corpo = { nome: (nome ?? '').trim() }
  try {
    const dados = id ? await api.loja.put(`/categorias-material/${id}`, corpo) : await api.loja.post('/categorias-material', corpo)
    return converterCategoria(dados, fuso)
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITO_CATEGORIA)
  }
}

export const excluirCategoria = (id) => api.loja.delete(`/categorias-material/${id}`)

// --- Movimentações de estoque ------------------------------------------------------------------

export const converterMovimentacao = (m, fuso) => ({
  id: m.id,
  materialId: m.material_id,
  // entrada | saida_atendimento | ajuste | perda
  tipo: m.tipo ?? null,
  // Com sinal: negativa = saiu do estoque
  quantidade: lerNumero(m.quantidade) ?? 0,
  agendamentoId: m.agendamento_id ?? null,
  motivo: m.motivo ?? null,
  quem: m.funcionario_nome ?? m.atualizado_por_nome ?? null,
  quando: lerMomentoNaLoja(m.criado_em, fuso),
})

export const listarMovimentacoes = async (materialId, { pagina, porPagina }, fuso, sinal) =>
  lerPagina(
    await api.loja.get(`/materiais/${materialId}/movimentacoes`, { query: { pagina, por_pagina: porPagina }, sinal }),
    (m) => converterMovimentacao(m, fuso),
  )

export async function lancarMovimentacao(materialId, { tipo, quantidade, motivo }, fuso) {
  try {
    const dados = await api.loja.post(`/materiais/${materialId}/movimentacoes`, {
      tipo,
      quantidade: enviarNumero(quantidade),
      motivo: textoOuNulo(motivo),
    })
    return converterMovimentacao(dados, fuso)
  } catch (erro) {
    // Validações do modelo (erros[] com campo "corpo") e regras sem campo: para o campo certo
    if (erro?.status === 422 && erro.campos?.length) {
      erro.campos = erro.campos.map((c) =>
        c.campo === 'corpo' || !c.campo
          ? { ...c, campo: /motivo/i.test(c.mensagem) ? 'motivo' : 'quantidade' }
          : c,
      )
    }
    throw apontarCampo(erro, [
      [/motivo/i, 'motivo'],
      [/quantidade|estoque/i, 'quantidade'],
    ])
  }
}
