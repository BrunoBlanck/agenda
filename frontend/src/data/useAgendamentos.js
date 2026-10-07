import { useEffect, useState } from 'react'
import { useConsulta } from './api/useConsulta.js'
import {
  buscarClientesApoio,
  carregarApoioAgendamento,
  carregarFiltrosAgenda,
  consultarDisponibilidade,
  listarAgendamentos,
  obterAgendamento,
} from './api/agendamentos.js'

export { registrarPagamento } from './api/agendamentos.js'

// Hooks da área de agendamentos (lista, detalhe, listas de apoio, disponibilidade).
// As ações (criar, editar, mudar status, aceitar, recusar, materiais, excluir) ficam em
// data/api/agendamentos.js: a tela chama e trata o erro com useTratarErro.
// registrarPagamento (que conclui o atendimento, AGE-26) é reexportado daqui para a seção Pagamento do painel.

const POR_PAGINA = 20
const BUSCA_MINIMA = 2

// Status finais (AGE-18): só o Administrador reabre
export const STATUS_FINAIS = ['concluido', 'cancelado', 'nao_compareceu']
// Não ocupam o horário (mesma regra do banco)
export const LIBERAM_HORARIO = ['cancelado', 'nao_compareceu']
const TRANSICOES = {
  pendente: ['confirmado', 'cancelado'],
  agendado: ['confirmado', 'cancelado', 'nao_compareceu'],
  // Concluir não passa pela Situação: é registrar o pagamento (AGE-26)
  confirmado: ['cancelado', 'nao_compareceu'],
}

/**
 * Situações oferecidas no formulário (AGE-06, AGE-17, AGE-18). Só UX: quem decide é a API.
 * atual = null: agendamento novo. podeReabrir: perfil com acesso total (Administrador).
 */
export function opcoesDeStatus(atual, podeReabrir = false) {
  if (!atual) return ['agendado', 'confirmado']
  if (STATUS_FINAIS.includes(atual)) return podeReabrir ? [atual, 'agendado', 'confirmado'] : [atual]
  return [atual, ...(TRANSICOES[atual] ?? [])]
}

/** Valor que só muda depois de `ms` sem alterações (busca e disponibilidade). */
export function useAdiado(valor, ms = 300) {
  const [adiado, setAdiado] = useState(valor)
  useEffect(() => {
    const espera = setTimeout(() => setAdiado(valor), ms)
    return () => clearTimeout(espera)
  }, [valor, ms])
  return adiado
}

/**
 * Lista paginada de agendamentos, com filtros no servidor (INT-13).
 * filtros: { funcionarioId, localId, inicio, fim, ordem } (datas "AAAA-MM-DD"; ordem 'asc' | 'desc' pelo início).
 * Mudar filtro volta à página 1.
 * Retorna { itens, total, pagina, porPagina, mudarPagina, carregando, atualizando, erro, recarregar }.
 */
export function useListaAgendamentos(filtros) {
  const chaveFiltros = JSON.stringify(filtros ?? {})
  const [estadoPagina, setEstadoPagina] = useState({ chave: chaveFiltros, pagina: 1 })
  // Filtro novo: página 1 (calculado na renderização, sem efeito)
  const pagina = estadoPagina.chave === chaveFiltros ? estadoPagina.pagina : 1
  const consulta = useConsulta(
    (sinal) => listarAgendamentos({ ...filtros, pagina, porPagina: POR_PAGINA }, sinal),
    ['agendamentos', chaveFiltros, pagina],
  )
  const dados = consulta.dados
  return {
    itens: dados?.itens ?? [],
    total: dados?.total ?? 0,
    pagina,
    porPagina: dados?.porPagina ?? POR_PAGINA,
    mudarPagina: (p) => setEstadoPagina({ chave: chaveFiltros, pagina: p }),
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}

/** Um agendamento completo (com os materiais). ativo = false não busca (painel fechado ou registro novo). */
export function useAgendamento(id, { ativo = true } = {}) {
  const consulta = useConsulta((sinal) => obterAgendamento(id, sinal), ['agendamento', id], { ativo: ativo && !!id })
  return {
    agendamento: consulta.dados,
    carregando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    // Troca o detalhe pela resposta de uma ação (ex.: registrarPagamento), sem buscar de novo
    definir: consulta.definirDados,
  }
}

/** Serviços, profissionais, locais e materiais do formulário. Exige escrita na agenda: ativo = false para quem só lê. */
export function useApoioAgendamento({ ativo = true } = {}) {
  const consulta = useConsulta(carregarApoioAgendamento, ['apoio-agendamento'], { ativo })
  return { apoio: consulta.dados, carregando: consulta.atualizando, erro: consulta.erro, recarregar: consulta.recarregar }
}

/** Profissionais e locais para os filtros da agenda e da lista (leitura na agenda basta). */
export function useFiltrosAgenda({ ativo = true } = {}) {
  const consulta = useConsulta(carregarFiltrosAgenda, ['filtros-agenda'], { ativo })
  return {
    profissionais: consulta.dados?.profissionais ?? [],
    locais: consulta.dados?.locais ?? null,
    soPropria: consulta.dados?.soPropria ?? false,
    carregando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}

/**
 * Busca de clientes do formulário (GET /apoio/clientes): mínimo de 2 caracteres, com espera de 300 ms.
 * Retorna { buscar(texto), termo, curto, itens, total, buscando, erro }.
 */
export function useBuscaClientes({ ativo = true } = {}) {
  const [termo, setTermo] = useState('')
  const limpo = termo.trim()
  const adiado = useAdiado(limpo, 300)
  const valido = ativo && adiado.length >= BUSCA_MINIMA
  const consulta = useConsulta((sinal) => buscarClientesApoio(adiado, {}, sinal), ['apoio-clientes', adiado], {
    ativo: valido,
  })
  return {
    buscar: setTermo,
    termo,
    curto: limpo.length < BUSCA_MINIMA,
    itens: valido ? (consulta.dados?.itens ?? []) : [],
    total: valido ? (consulta.dados?.total ?? 0) : 0,
    buscando: limpo.length >= BUSCA_MINIMA && (limpo !== adiado || consulta.atualizando),
    erro: valido ? consulta.erro : null,
  }
}

/**
 * O horário está livre? Consulta a API ao mudar profissional, data, hora ou duração (espera 400 ms;
 * a consulta antiga é cancelada). params: { funcionarioId, inicio (dayjs), duracao, agendamentoId }.
 * Retorna { disponibilidade: { aviso, profissionalOcupado, locaisOcupados } | null, consultando, erro, recarregar }.
 */
export function useDisponibilidade(params, { ativo = true } = {}) {
  const completo = !!(params?.funcionarioId && params?.inicio?.isValid?.() && Number(params?.duracao) > 0)
  const chave = completo
    ? JSON.stringify([
        params.funcionarioId,
        params.inicio.format('YYYY-MM-DDTHH:mm'),
        Math.round(Number(params.duracao)),
        params.agendamentoId ?? null,
      ])
    : null
  const adiada = useAdiado(chave, 400)
  const consulta = useConsulta(
    (sinal) => {
      const [funcionarioId, inicio, duracao, agendamentoId] = JSON.parse(adiada)
      return consultarDisponibilidade({ funcionarioId, inicio, duracao, agendamentoId }, sinal)
    },
    ['disponibilidade', adiada],
    { ativo: ativo && !!adiada && adiada === chave },
  )
  // Resposta de um horário que não é mais o do formulário não vale
  const atual = ativo && adiada === chave && chave != null
  return {
    disponibilidade: atual ? consulta.dados : null,
    consultando: ativo && chave != null && (adiada !== chave || consulta.atualizando),
    erro: atual ? consulta.erro : null,
    recarregar: consulta.recarregar,
  }
}
