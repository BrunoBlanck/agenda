import { api } from './cliente.js'
import { lerDataHora, lerNumero, lerPagina, textoOuNulo } from './conversao.js'
import { conflitoNoCampo, lerControle } from './registro.js'

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
  // Serviços que citam o local (vazio com o módulo Serviços desligado)
  servicos: lista(l.servicos).map((s) => ({ id: s.id, nome: s.nome ?? '—' })),
  proximosAgendamentos: lerNumero(l.proximos_agendamentos) ?? 0,
  ...lerControle(l, fuso),
})

// A API apaga o link de local presencial; a descrição só aparece no formulário do presencial
const corpoLocal = (v) => ({
  nome: (v.nome ?? '').trim(),
  tipo: v.tipo ?? 'presencial',
  link_padrao: v.tipo === 'online' ? textoOuNulo(v.linkPadrao) : null,
  descricao: textoOuNulo(v.descricao),
  ativo: v.ativo ?? true,
})

export const listarLocais = async (fuso, sinal) => lista(await api.loja.get('/locais', { sinal })).map((l) => converterLocal(l, fuso))

export const obterLocal = async (id, fuso, sinal) => converterLocal(await api.loja.get(`/locais/${id}`, { sinal }), fuso)

// 409 de unicidade (backend/app/erros.py, locais_nome_uk): ao lado do campo
const CONFLITOS = [['local com este nome', 'nome']]

export async function salvarLocal(valores, id, fuso) {
  const corpo = corpoLocal(valores)
  try {
    const dados = id ? await api.loja.put(`/locais/${id}`, corpo) : await api.loja.post('/locais', corpo)
    return converterLocal(dados, fuso)
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITOS)
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
