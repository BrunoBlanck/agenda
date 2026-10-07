import { api } from './cliente.js'
import { enviarData, enviarDataHora, enviarNumero, lerDataHora, lerNumero, lerPagina, textoOuNulo } from './conversao.js'

// Agendamentos (/api/loja/agendamentos) e listas de apoio do formulário (/api/loja/apoio/...).
// Mapeamento explícito API -> tela (INT-09). Datas na hora de parede da loja (INT-11):
// "2030-01-07T09:00:00-03:00" vira data "2030-01-07" e hora "09:00".

const lista = (v) => (Array.isArray(v) ? v : [])

/**
 * Pagamento ativo do atendimento (AGE-26 a AGE-29): só em concluído; null nos demais e nos concluídos
 * antigos (AGE-29). pago_em vem no fuso da loja e é lido na hora da loja (INT-11).
 */
const lerPagamento = (p) =>
  p && typeof p === 'object'
    ? {
        id: p.id ?? null,
        forma: p.forma ?? null,
        valor: lerNumero(p.valor),
        pagoEm: lerDataHora(p.pago_em),
        registradoPorNome: p.registrado_por_nome ?? null,
      }
    : null

const lerMaterialUsado = (m) => ({
  materialId: m?.material_id ?? null,
  nome: m?.nome ?? '—',
  unidade: m?.unidade ?? '',
  quantidade: lerNumero(m?.quantidade) ?? 0,
})

/** AgendamentoSaida -> agendamento da tela. Campos que podem vir null ficam null (a tela mostra "—"). */
export function converterAgendamento(a) {
  const inicio = lerDataHora(a?.inicio)
  const fim = lerDataHora(a?.fim)
  return {
    id: a?.id,
    clienteId: a?.cliente_id ?? null,
    clienteNome: a?.cliente_nome ?? null,
    servicoId: a?.servico_id ?? null,
    servicoNome: a?.servico_nome ?? null,
    funcionarioId: a?.funcionario_id ?? null,
    funcionarioNome: a?.funcionario_nome ?? null,
    cor: a?.cor_agenda ?? null,
    localId: a?.local_id ?? null,
    localNome: a?.local_nome ?? null,
    localTipo: a?.local_tipo ?? null,
    linkReuniao: a?.link_reuniao ?? null,
    link: a?.link ?? null,
    // Hora da loja, sem fuso: "AAAA-MM-DDTHH:mm" (ordena como texto)
    inicio: inicio ? inicio.format('YYYY-MM-DDTHH:mm') : null,
    data: inicio ? inicio.format('YYYY-MM-DD') : null,
    hora: inicio ? inicio.format('HH:mm') : null,
    dataFim: fim ? fim.format('YYYY-MM-DD') : null,
    horaFim: fim ? fim.format('HH:mm') : null,
    duracao: lerNumero(a?.duracao_minutos) ?? 0,
    preco: lerNumero(a?.preco),
    status: a?.status ?? null,
    origem: a?.origem ?? null,
    observacoes: a?.observacoes ?? null,
    motivoCancelamento: a?.motivo_cancelamento ?? null,
    criadoPor: a?.criado_por ?? null,
    // Só no detalhe (GET /agendamentos/{id}) com o módulo Materiais ativo; null = não veio
    materiais: Array.isArray(a?.materiais) ? a.materiais.map(lerMaterialUsado) : null,
    // { id, forma, valor, pagoEm (dayjs na hora da loja), registradoPorNome } | null
    pagamento: lerPagamento(a?.pagamento),
    criadoEm: a?.criado_em ?? null,
    atualizadoEm: a?.atualizado_em ?? null,
    atualizadoPor: a?.atualizado_por ?? null,
    atualizadoPorNome: a?.atualizado_por_nome ?? null,
  }
}

export const converterAgendamentos = (itens) => lista(itens).map(converterAgendamento)

// ---------------------------------------------------------------------------------------------
// Lista, detalhe e gravação
// ---------------------------------------------------------------------------------------------

/**
 * GET /agendamentos (paginado; filtros no servidor). O servidor já devolve só o que o usuário pode ver.
 * filtros: { pagina, porPagina, funcionarioId, localId, clienteId, servicoId, status: [], inicio, fim, ordem }
 * (datas dayjs ou "AAAA-MM-DD"; ordem 'asc' | 'desc' pelo início, padrão da API 'asc').
 */
export async function listarAgendamentos(filtros = {}, sinal) {
  const dados = await api.loja.get('/agendamentos', {
    query: {
      pagina: filtros.pagina,
      por_pagina: filtros.porPagina,
      funcionario_id: filtros.funcionarioId,
      local_id: filtros.localId,
      cliente_id: filtros.clienteId,
      servico_id: filtros.servicoId,
      status: filtros.status,
      inicio: filtros.inicio ? enviarData(filtros.inicio) : undefined,
      fim: filtros.fim ? enviarData(filtros.fim) : undefined,
      ordem: filtros.ordem === 'desc' ? 'desc' : undefined,
    },
    sinal,
  })
  return lerPagina(dados, converterAgendamento)
}

export const obterAgendamento = async (id, sinal) =>
  converterAgendamento(await api.loja.get(`/agendamentos/${id}`, { sinal }))

/**
 * Corpo de POST/PUT /agendamentos a partir dos valores do formulário (só os campos que a API espera).
 * valores: { clienteId, servicoId, funcionarioId, localId, linkReuniao, inicio (dayjs), duracao, preco,
 *            status, observacoes, motivoCancelamento }. status undefined = não muda.
 */
export function corpoAgendamento(valores) {
  const corpo = {
    cliente_id: valores.clienteId,
    servico_id: valores.servicoId ?? null,
    funcionario_id: valores.funcionarioId,
    local_id: valores.localId ?? null,
    link_reuniao: textoOuNulo(valores.linkReuniao),
    inicio: enviarDataHora(valores.inicio),
    duracao_minutos: valores.duracao == null || valores.duracao === '' ? null : Math.round(Number(valores.duracao)),
    preco: enviarNumero(valores.preco),
    observacoes: textoOuNulo(valores.observacoes),
  }
  if (valores.status) corpo.status = valores.status
  if (valores.status === 'cancelado') corpo.motivo_cancelamento = textoOuNulo(valores.motivoCancelamento)
  return corpo
}

export const criarAgendamento = async (valores) =>
  converterAgendamento(await api.loja.post('/agendamentos', corpoAgendamento(valores)))

export const editarAgendamento = async (id, valores) =>
  converterAgendamento(await api.loja.put(`/agendamentos/${id}`, corpoAgendamento(valores)))

export const excluirAgendamento = (id) => api.loja.delete(`/agendamentos/${id}`)

/** POST /agendamentos/{id}/status. Cancelar exige o motivo. */
export const mudarStatusAgendamento = async (id, status, motivoCancelamento) =>
  converterAgendamento(
    await api.loja.post(`/agendamentos/${id}/status`, {
      status,
      ...(status === 'cancelado' && { motivo_cancelamento: textoOuNulo(motivoCancelamento) }),
    }),
  )

/**
 * POST /agendamentos/{id}/pagamento: registra o pagamento e conclui o atendimento (AGE-26), só a partir
 * de Confirmado. { forma: 'credito'|'debito'|'dinheiro'|'pix', valor: number } -> agendamento Concluído
 * (detalhe, com materiais e `pagamento`). Rejeita com ErroApi; 422 traz campos [{ campo: 'forma'|'valor', mensagem }].
 */
export const registrarPagamento = async (id, { forma, valor }) =>
  converterAgendamento(await api.loja.post(`/agendamentos/${id}/pagamento`, { forma, valor: enviarNumero(valor) }))

/** Pedido do site: aceitar (vira confirmado) ou recusar (vira cancelado; sem motivo = "Recusado pela loja"). */
export const aceitarSolicitacao = async (id) => converterAgendamento(await api.loja.post(`/agendamentos/${id}/aceitar`))

export const recusarSolicitacao = async (id, motivo) =>
  converterAgendamento(
    await api.loja.post(`/agendamentos/${id}/recusar`, { motivo_cancelamento: textoOuNulo(motivo) }),
  )

/** PUT /agendamentos/{id}/materiais: o que foi usado no atendimento (antes de concluir). */
export const ajustarMateriais = async (id, materiais) =>
  converterAgendamento(
    await api.loja.put(`/agendamentos/${id}/materiais`, {
      materiais: lista(materiais).map((m) => ({ material_id: m.materialId, quantidade: enviarNumero(m.quantidade) })),
    }),
  )

// ---------------------------------------------------------------------------------------------
// Listas de apoio
// ---------------------------------------------------------------------------------------------

/** GET /apoio/clientes: busca de clientes ativos (mínimo 2 caracteres), paginada. */
export async function buscarClientesApoio(busca, { pagina = 1, porPagina = 20 } = {}, sinal) {
  const dados = await api.loja.get('/apoio/clientes', { query: { busca, pagina, por_pagina: porPagina }, sinal })
  return lerPagina(dados, (c) => ({
    id: c?.id,
    nome: c?.nome ?? '',
    sobrenome: c?.sobrenome ?? '',
    telefone: c?.telefone ?? null,
  }))
}

const lerServicoApoio = (s) => ({
  id: s?.id,
  nome: s?.nome ?? '—',
  duracao: lerNumero(s?.duracao_minutos),
  preco: lerNumero(s?.preco),
  ativo: s?.ativo ?? true,
  funcionarioIds: lista(s?.funcionario_ids),
  // Vazio = qualquer local ativo (AGE-12)
  localIds: lista(s?.local_ids),
  materiais: lista(s?.materiais).map(lerMaterialUsado),
})

/**
 * GET /apoio/agendamento: serviços, profissionais, locais e materiais do formulário.
 * servicos/locais/materiais = null quando o módulo está desligado na loja.
 */
export async function carregarApoioAgendamento(sinal) {
  const dados = await api.loja.get('/apoio/agendamento', { sinal })
  return {
    servicos: Array.isArray(dados?.servicos) ? dados.servicos.map(lerServicoApoio) : null,
    profissionais: lista(dados?.profissionais).map((p) => ({
      id: p?.id,
      nome: p?.nome ?? '—',
      cor: p?.cor_agenda ?? null,
      perfilId: p?.perfil_id ?? null,
      cargo: p?.cargo_nome ?? null,
    })),
    locais: Array.isArray(dados?.locais)
      ? dados.locais.map((l) => ({
          id: l?.id,
          nome: l?.nome ?? '—',
          tipo: l?.tipo ?? null,
          linkPadrao: l?.link_padrao ?? null,
          ativo: true,
        }))
      : null,
    materiais: Array.isArray(dados?.materiais)
      ? dados.materiais.map((m) => ({ id: m?.id, nome: m?.nome ?? '—', unidade: m?.unidade ?? '' }))
      : null,
  }
}

/** GET /apoio/filtros-agenda: profissionais e locais para os filtros (leitura na agenda basta). */
export async function carregarFiltrosAgenda(sinal) {
  const dados = await api.loja.get('/apoio/filtros-agenda', { sinal })
  return {
    soPropria: !!dados?.so_propria,
    profissionais: lista(dados?.profissionais).map((p) => ({
      id: p?.id,
      nome: p?.nome ?? '—',
      cor: p?.cor_agenda ?? null,
      ativo: p?.ativo ?? true,
    })),
    locais: Array.isArray(dados?.locais)
      ? dados.locais.map((l) => ({ id: l?.id, nome: l?.nome ?? '—', tipo: l?.tipo ?? null, ativo: l?.ativo ?? true }))
      : null,
  }
}

/**
 * GET /apoio/disponibilidade: o horário está livre? Quem decide é a API (INT-23).
 * { funcionarioId, inicio (dayjs), duracao (min), agendamentoId? } -> { aviso, profissionalOcupado, locaisOcupados }
 */
export async function consultarDisponibilidade({ funcionarioId, inicio, duracao, agendamentoId }, sinal) {
  const dados = await api.loja.get('/apoio/disponibilidade', {
    query: {
      funcionario_id: funcionarioId,
      inicio: enviarDataHora(inicio),
      duracao_minutos: duracao,
      agendamento_id: agendamentoId,
    },
    sinal,
  })
  return {
    aviso: dados?.aviso ?? null,
    profissionalOcupado: !!dados?.profissional_ocupado,
    locaisOcupados: lista(dados?.locais_ocupados),
  }
}
