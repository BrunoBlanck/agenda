import { api } from './cliente.js'
import { lerDataHora, lerNumero, lerPagina, textoOuNulo } from './conversao.js'
import { apontarCampo, conflitoNoCampo, lerControle } from './registro.js'

// Locais (/api/loja/locais) e como a loja os chama (/api/loja/locais/rotulos). Recurso: locais (módulo Locais).
// Local não é excluído: é inativado (PUT com ativo = false).

const lista = (v) => (Array.isArray(v) ? v : [])

export const converterLocal = (l, fuso) => ({
  id: l.id,
  nome: l.nome ?? '',
  tipo: l.tipo ?? 'presencial',
  linkPadrao: l.link_padrao ?? null,
  descricao: l.descricao ?? null,
  ativo: l.ativo !== false,
  // Serviços vinculados ao local, por nome (vazio com o módulo Serviços desligado). LOC-06
  servicos: lista(l.servicos).map((s) => ({ id: s.id, nome: s.nome ?? '—', ativo: s.ativo !== false })),
  servicoIds: lista(l.servicos).map((s) => s.id),
  proximosAgendamentos: lerNumero(l.proximos_agendamentos) ?? 0,
  ...lerControle(l, fuso),
})

// A API apaga o link de local presencial; a descrição só aparece no formulário do presencial.
// servico_ids só vai quando o campo está no formulário (opções carregadas, módulo Serviços ligado):
// ausente, a API não mexe nos vínculos. [] remove todos.
const corpoLocal = (v) => ({
  nome: (v.nome ?? '').trim(),
  tipo: v.tipo ?? 'presencial',
  link_padrao: v.tipo === 'online' ? textoOuNulo(v.linkPadrao) : null,
  descricao: textoOuNulo(v.descricao),
  ativo: v.ativo ?? true,
  ...(Array.isArray(v.servicoIds) && { servico_ids: [...new Set(v.servicoIds.filter(Boolean))] }),
})

export const listarLocais = async (fuso, sinal) => lista(await api.loja.get('/locais', { sinal })).map((l) => converterLocal(l, fuso))

export const obterLocal = async (id, fuso, sinal) => converterLocal(await api.loja.get(`/locais/${id}`, { sinal }), fuso)

// 409 de unicidade (backend/app/erros.py, locais_nome_uk): ao lado do campo
const CONFLITOS = [['local com este nome', 'nome']]

// 422 de regra sem erros[] ("Serviço não encontrado.": de outra loja, inexistente ou excluído)
const CAMPOS_DAS_REGRAS = [[/serviço/i, 'servico_ids']]

// 422 com erros[] por item da lista (servico_ids.0, servico_ids.3...) vai para o campo inteiro, sem repetir a mensagem
function errosNaLista(erro) {
  if (erro?.status !== 422 || !erro.campos?.length) return erro
  const vistos = new Set()
  erro.campos = erro.campos
    .map((c) => (/^servico_ids\.\d+$/.test(String(c?.campo)) ? { ...c, campo: 'servico_ids' } : c))
    .filter((c) => {
      const chave = `${c?.campo}|${c?.mensagem}`
      if (vistos.has(chave)) return false
      vistos.add(chave)
      return true
    })
  return erro
}

export async function salvarLocal(valores, id, fuso) {
  const corpo = corpoLocal(valores)
  try {
    const dados = id ? await api.loja.put(`/locais/${id}`, corpo) : await api.loja.post('/locais', corpo)
    return converterLocal(dados, fuso)
  } catch (erro) {
    throw apontarCampo(errosNaLista(conflitoNoCampo(erro, CONFLITOS)), CAMPOS_DAS_REGRAS)
  }
}

/** Serviços para o formulário do local (ativos e inativos). servicos = null com o módulo Serviços desligado. */
export async function obterOpcoesLocal(sinal) {
  const d = await api.loja.get('/locais/opcoes', { sinal })
  return {
    servicos:
      d?.servicos == null
        ? null
        : lista(d.servicos).map((s) => ({
            id: s.id,
            nome: s.nome ?? '—',
            ativo: s.ativo !== false,
            locaisVinculados: lerNumero(s.locais_vinculados) ?? 0,
          })),
  }
}

// --- Rótulos (Sala, Cadeira...) -----------------------------------------------------------------

const converterRotulos = (r, fuso) => ({
  singular: r?.rotulo_local ?? '',
  plural: r?.rotulo_local_plural ?? '',
  ...lerControle(r, fuso),
})

export const MAPA_ERROS_ROTULOS = { rotulo_local: 'singular', rotulo_local_plural: 'plural' }

export const obterRotulosLocal = async (fuso, sinal) => converterRotulos(await api.loja.get('/locais/rotulos', { sinal }), fuso)

export const salvarRotulosLocal = async ({ singular, plural }, fuso) =>
  converterRotulos(
    await api.loja.put('/locais/rotulos', { rotulo_local: (singular ?? '').trim(), rotulo_local_plural: (plural ?? '').trim() }),
    fuso,
  )

// --- Agendamentos do local (GET /api/loja/agendamentos?local_id=, só os que o usuário pode ver) ---

const converterAgendamentoDoLocal = (a) => {
  const inicio = lerDataHora(a.inicio)
  return {
    id: a.id,
    data: inicio?.format('YYYY-MM-DD') ?? null,
    hora: inicio?.format('HH:mm') ?? null,
    clienteNome: a.cliente_nome || '—',
    funcionarioNome: a.funcionario_nome || '—',
    servicoNome: a.servico_nome || 'Atendimento',
    status: a.status ?? null,
  }
}

/** De hoje em diante (dia da loja), do mais cedo ao mais tarde, paginado no servidor. */
export const listarAgendamentosDoLocal = async (localId, { desde, pagina, porPagina }, sinal) =>
  lerPagina(
    await api.loja.get('/agendamentos', {
      query: { local_id: localId, inicio: desde, pagina, por_pagina: porPagina },
      sinal,
    }),
    converterAgendamentoDoLocal,
  )
