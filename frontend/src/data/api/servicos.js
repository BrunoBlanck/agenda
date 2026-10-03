import { api } from './cliente.js'
import { enviarNumero, lerNumero, textoOuNulo } from './conversao.js'
import { apontarCampo, conflitoNoCampo, lerControle } from './registro.js'

// Serviços (/api/loja/servicos). Recurso: servicos (módulo Serviços).
// Os vínculos (profissionais, locais e materiais) vêm com o nome junto: a tela não precisa de outras listas.

const lista = (v) => (Array.isArray(v) ? v : [])

export const converterServico = (s, fuso) => ({
  id: s.id,
  nome: s.nome ?? '',
  descricao: s.descricao ?? null,
  duracao: lerNumero(s.duracao_minutos),
  preco: lerNumero(s.preco),
  ativo: s.ativo !== false,
  funcionarioIds: lista(s.funcionario_ids),
  profissionais: lista(s.profissionais).map((p) => ({ id: p.id, nome: p.nome ?? '—' })),
  // [] = qualquer local ativo
  localIds: lista(s.local_ids),
  locais: lista(s.locais).map((l) => ({ id: l.id, nome: l.nome ?? '—', tipo: l.tipo })),
  materiais: lista(s.materiais).map((m) => ({
    materialId: m.material_id,
    nome: m.nome ?? '—',
    unidade: m.unidade ?? '',
    quantidade: lerNumero(m.quantidade),
  })),
  ...lerControle(s, fuso),
})

// comLocais/comMateriais: módulo ligado na loja. Desligado, o campo não vai (a API mantém o que havia).
const corpoServico = (v, { comLocais, comMateriais }) => ({
  nome: (v.nome ?? '').trim(),
  descricao: textoOuNulo(v.descricao),
  duracao_minutos: v.duracao ?? null,
  preco: enviarNumero(v.preco),
  ativo: v.ativo ?? true,
  funcionario_ids: lista(v.funcionarioIds),
  ...(comLocais && { local_ids: lista(v.localIds) }),
  ...(comMateriais && {
    materiais: lista(v.materiais)
      .filter((m) => m?.materialId)
      .map((m) => ({ material_id: m.materialId, quantidade: enviarNumero(m.quantidade) ?? 1 })),
  }),
})

// Mensagens de regra (422 sem erros[]) que pertencem a um campo
const CAMPOS_DAS_REGRAS = [
  [/profissional/i, 'funcionario_ids'],
  [/local/i, 'local_ids'],
  [/material/i, 'materiais'],
]

// 409 de unicidade (backend/app/erros.py, servicos_nome_uk): ao lado do campo
const CONFLITOS = [['serviço com este nome', 'nome']]

// Nomes da API que mudam na tela (o resto converte sozinho: funcionario_ids -> funcionarioIds)
export const MAPA_ERROS_SERVICO = { duracao_minutos: 'duracao' }

export const listarServicos = async (fuso, sinal) =>
  lista(await api.loja.get('/servicos', { sinal })).map((s) => converterServico(s, fuso))

export const obterServico = async (id, fuso, sinal) => converterServico(await api.loja.get(`/servicos/${id}`, { sinal }), fuso)

export async function salvarServico(valores, id, modulos, fuso) {
  const corpo = corpoServico(valores, modulos)
  try {
    const dados = id ? await api.loja.put(`/servicos/${id}`, corpo) : await api.loja.post('/servicos', corpo)
    return converterServico(dados, fuso)
  } catch (erro) {
    throw apontarCampo(conflitoNoCampo(erro, CONFLITOS), CAMPOS_DAS_REGRAS)
  }
}

export const excluirServico = (id) => api.loja.delete(`/servicos/${id}`)

/** Opções do formulário (só ativos). locais/materiais = null com o módulo desligado. */
export async function obterOpcoesServico(sinal) {
  const d = await api.loja.get('/servicos/opcoes', { sinal })
  return {
    profissionais: lista(d?.profissionais).map((p) => ({ id: p.id, nome: p.nome ?? '—' })),
    locais: d?.locais == null ? null : lista(d.locais).map((l) => ({ id: l.id, nome: l.nome ?? '—', tipo: l.tipo })),
    materiais:
      d?.materiais == null ? null : lista(d.materiais).map((m) => ({ id: m.id, nome: m.nome ?? '—', unidade: m.unidade ?? '' })),
  }
}
