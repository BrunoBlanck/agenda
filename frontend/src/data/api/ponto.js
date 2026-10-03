import { api } from './cliente.js'
import { enviarData, enviarDataHora, lerData, lerDataHora, lerNumero } from './conversao.js'
import { apontarCampo, conflitoNoCampo, lerControle } from './registro.js'

// Controle de Tempo (/api/loja/ponto). Recursos: ponto_proprio e ponto_equipe (módulo controle_tempo).
// Entrada e saída do "registrar" usam a hora do servidor. Horários na hora de parede da loja.

const lista = (v) => (Array.isArray(v) ? v : [])

export const converterRegistro = (r, fuso) => {
  const entrada = lerDataHora(r.entrada)
  const saida = lerDataHora(r.saida)
  return {
    id: r.id,
    funcionarioId: r.funcionario_id,
    funcionarioNome: r.funcionario_nome ?? '—',
    // Dia da entrada, no fuso da loja ("AAAA-MM-DD")
    data: r.data ?? entrada?.format('YYYY-MM-DD') ?? null,
    entrada, // dayjs na hora da loja
    saida, // dayjs ou null (em serviço)
    entradaHora: entrada?.format('HH:mm') ?? null,
    saidaHora: saida?.format('HH:mm') ?? null,
    // Saída em outro dia (virada da meia-noite)
    saidaOutroDia: !!(entrada && saida && !saida.isSame(entrada, 'day')),
    // Tempo trabalhado (calculado pela API); null = em serviço
    minutos: lerNumero(r.minutos),
    origem: r.origem ?? 'sistema',
    justificativa: r.justificativa ?? null,
    editadoPor: r.editado_por ?? null,
    editadoPorNome: r.editado_por_nome ?? null,
    ...lerControle(r, fuso),
  }
}

const converterTotal = (t) => ({
  id: `${t.funcionario_id}-${t.data}`,
  funcionarioId: t.funcionario_id,
  funcionarioNome: t.funcionario_nome ?? '—',
  data: t.data ?? null,
  minutos: lerNumero(t.minutos) ?? 0,
})

/** Período (inicio e fim são dayjs/datas; fim inclusive; até 62 dias). funcionarioId: só dele (equipe). */
export async function listarPonto({ inicio, fim, funcionarioId }, fuso, sinal) {
  const d = await api.loja.get('/ponto', {
    query: { inicio: enviarData(inicio), fim: enviarData(fim), funcionario_id: funcionarioId },
    sinal,
  })
  return {
    inicio: lerData(d?.inicio),
    fim: lerData(d?.fim),
    registros: lista(d?.registros).map((r) => converterRegistro(r, fuso)),
    totais: lista(d?.totais).map(converterTotal),
  }
}

/** Registro em aberto (em serviço) do funcionário; sem funcionarioId = o próprio usuário. null = nenhum. */
export async function obterPontoAberto(funcionarioId, fuso, sinal) {
  const d = await api.loja.get('/ponto/aberto', { query: { funcionario_id: funcionarioId }, sinal })
  return d ? converterRegistro(d, fuso) : null
}

/** acao: 'entrada' | 'saida'. funcionarioId vazio = o próprio usuário. Retorna { acao, registro }. */
export async function registrarPonto(acao, funcionarioId, fuso) {
  const d = await api.loja.post('/ponto/registrar', { acao, ...(funcionarioId && { funcionario_id: funcionarioId }) })
  return { acao: d?.acao ?? acao, registro: d?.registro ? converterRegistro(d.registro, fuso) : null }
}

// Mensagens de regra (422 sem erros[]) que pertencem a um campo
const CAMPOS_DAS_REGRAS = [
  [/saída/i, 'saida'],
  [/futuro/i, 'entrada'],
  [/funcionário/i, 'funcionario_id'],
]

// 409 do lançamento/correção (routers/loja/ponto.py MSG_SOBREPOSTO e MSG_JA_ABERTO; erros.py registros_ponto_*):
// "nesse período" é culpa da entrada e da saída juntas; "em aberto" é a saída vazia (outro registro já está aberto).
const CONFLITOS = [
  ['registro de ponto nesse período', 'entrada'],
  ['registro de ponto em aberto', 'saida'],
]

/** 409 ao lado dos campos; período sobreposto com saída informada marca a saída também (só a borda, sem repetir o texto). */
function conflitoDoPonto(erro, valores) {
  const convertido = conflitoNoCampo(erro, CONFLITOS)
  if (convertido !== erro && convertido.campos?.[0]?.campo === 'entrada' && valores?.saida) {
    convertido.campos.push({ campo: 'saida', mensagem: '' })
  }
  return convertido
}

const corpoCorrecao = (v) => ({
  entrada: enviarDataHora(v.entrada),
  saida: v.saida ? enviarDataHora(v.saida) : null,
  justificativa: (v.justificativa ?? '').trim(),
})

/** Lançamento manual (escrita em Ponto da equipe): { funcionarioId, entrada, saida?, justificativa }. */
export async function lancarPonto(valores, fuso) {
  try {
    return converterRegistro(
      await api.loja.post('/ponto', { funcionario_id: valores.funcionarioId, ...corpoCorrecao(valores) }),
      fuso,
    )
  } catch (erro) {
    throw apontarCampo(conflitoDoPonto(erro, valores), CAMPOS_DAS_REGRAS)
  }
}

/** Correção (escrita em Ponto da equipe): { entrada, saida?, justificativa }. */
export async function corrigirPonto(id, valores, fuso) {
  try {
    return converterRegistro(await api.loja.put(`/ponto/${id}`, corpoCorrecao(valores)), fuso)
  } catch (erro) {
    throw apontarCampo(conflitoDoPonto(erro, valores), CAMPOS_DAS_REGRAS)
  }
}

/** Funcionários para o ponto da equipe (inclui inativos, para filtrar o histórico). */
export const listarFuncionariosPonto = async (sinal) =>
  lista(await api.loja.get('/ponto/funcionarios', { sinal })).map((f) => ({
    id: f.id,
    nome: f.nome ?? '—',
    cor: f.cor_agenda ?? null,
    ativo: f.ativo !== false,
  }))
