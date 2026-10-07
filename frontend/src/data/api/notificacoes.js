import { api } from './cliente.js'
import { lerDataHora, lerNumero, lerPagina, textoOuNulo } from './conversao.js'
import { lerControle } from './registro.js'

// Notificações (docs/funcionalidades/notificacoes.md, seção 4).
// Sino do painel: GET /api/loja/notificacoes, GET .../resumo, POST .../visualizar (pessoais, sem recurso).
// Configurações › Avisos e e-mail: GET/PUT /api/loja/configuracoes/notificacoes e POST .../testar-email (config_loja).

export const NOTIFICACOES_POR_PAGINA = 20

// O servidor espera o SMTP até 15 s por etapa (DNS, conexão, TLS, login): o teste pode passar dos 15 s padrão
const TEMPO_TESTE_EMAIL = 60_000

const inteiro = (v) => {
  const n = lerNumero(v)
  return n === null ? 0 : Math.max(0, Math.trunc(n))
}

/** Notificacao da API -> tela. agendamento_id/inicio_agendamento nulos quando o agendamento foi excluído. */
export function lerNotificacao(n) {
  return {
    id: String(n?.id ?? ''),
    evento: n?.evento ?? '',
    titulo: n?.titulo ?? '',
    mensagem: n?.mensagem ?? '',
    agendamentoId: n?.agendamento_id ? String(n.agendamento_id) : null,
    inicioAgendamento: lerDataHora(n?.inicio_agendamento),
    visualizada: n?.visualizada === true,
    visualizadaEm: lerDataHora(n?.visualizada_em),
    statusEmail: lerNumero(n?.status_email),
    statusWhatsapp: lerNumero(n?.status_whatsapp),
    criadoEm: lerDataHora(n?.criado_em),
  }
}

/** Página do sino (mais novas primeiro): { itens, total, pagina, porPagina, naoVisualizadas }. */
export async function listarNotificacoes(pagina, sinal) {
  const dados = await api.loja.get('/notificacoes', { query: { pagina, por_pagina: NOTIFICACOES_POR_PAGINA }, sinal })
  return {
    ...lerPagina(dados, lerNotificacao),
    naoVisualizadas: inteiro(dados?.nao_visualizadas),
  }
}

/** { naoVisualizadas: int | null } (null se a resposta não trouxer um número: o sino fica sem contador). */
export async function obterResumoNotificacoes(sinal) {
  const dados = await api.loja.get('/notificacoes/resumo', { sinal })
  const n = lerNumero(dados?.nao_visualizadas)
  return { naoVisualizadas: n === null ? null : Math.max(0, Math.trunc(n)) }
}

/** Marca como visualizadas (1 a 100 ids; os que não são do usuário são ignorados pela API). */
export async function visualizarNotificacoes(ids) {
  const dados = await api.loja.post('/notificacoes/visualizar', { ids: ids.map(String) })
  return { marcadas: inteiro(dados?.marcadas), naoVisualizadas: inteiro(dados?.nao_visualizadas) }
}

// --- Configurações › Avisos e e-mail (CFG-05, CFG-06) -----------------------------------------------

const SEGURANCAS = ['ssl', 'starttls']

/** ConfigNotificacoes da API -> tela. A senha nunca vem (só senha_definida). */
export function lerConfigNotificacoes(d, fuso) {
  const e = d?.email ?? {}
  return {
    antecedenciaClienteMinutos: lerNumero(d?.antecedencia_cliente_minutos) ?? 120,
    email: {
      ativo: e.ativo === true,
      servidor: e.servidor ?? null,
      porta: lerNumero(e.porta),
      seguranca: SEGURANCAS.includes(e.seguranca) ? e.seguranca : null,
      usuario: e.usuario ?? null,
      senhaDefinida: e.senha_definida === true,
      remetenteEmail: e.remetente_email ?? null,
      remetenteNome: e.remetente_nome ?? null,
    },
    whatsappDisponivel: d?.whatsapp_disponivel === true,
    ...lerControle(d, fuso),
  }
}

/**
 * Corpo do PUT (ConfigNotificacoesEntrada): só os campos que a API espera (extra = 422).
 * email.senha: ausente = mantém a salva (fica fora do corpo); null = apaga; texto = troca.
 */
export function corpoConfigNotificacoes(dados) {
  const e = dados?.email ?? {}
  const minutos = lerNumero(dados?.antecedenciaClienteMinutos)
  const email = {
    ativo: e.ativo === true,
    servidor: textoOuNulo(e.servidor),
    porta: lerNumero(e.porta),
    seguranca: e.seguranca || null,
    usuario: textoOuNulo(e.usuario),
    remetente_email: textoOuNulo(e.remetenteEmail),
    remetente_nome: textoOuNulo(e.remetenteNome),
  }
  if (Object.hasOwn(e, 'senha') && e.senha !== undefined) email.senha = e.senha === null ? null : String(e.senha)
  return {
    // A API só aceita minutos inteiros; null deixa a API responder 422 no campo
    antecedencia_cliente_minutos: minutos === null ? null : Math.round(minutos),
    email,
  }
}

export const obterConfigNotificacoes = async (fuso, sinal) =>
  lerConfigNotificacoes(await api.loja.get('/configuracoes/notificacoes', { sinal }), fuso)

export const salvarConfigNotificacoes = async (dados, fuso) =>
  lerConfigNotificacoes(await api.loja.put('/configuracoes/notificacoes', corpoConfigNotificacoes(dados)), fuso)

/** Envio de teste com a configuração salva: { enviado, erro: string | null }. 409/422/429 rejeitam com ErroApi. */
export async function testarEmailLoja(destino) {
  const dados = await api.loja.post(
    '/configuracoes/notificacoes/testar-email',
    { destino: (destino ?? '').trim() },
    { tempoLimite: TEMPO_TESTE_EMAIL },
  )
  return { enviado: dados?.enviado === true, erro: typeof dados?.erro === 'string' && dados.erro ? dados.erro : null }
}
