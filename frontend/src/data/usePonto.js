import { useCallback } from 'react'
import { useConsulta } from './api/useConsulta.js'
import {
  corrigirPonto,
  lancarPonto,
  listarFuncionariosPonto,
  listarPonto,
  obterPontoAberto,
  registrarPonto,
} from './api/ponto.js'
import { useAcesso } from './useAcesso.js'

/**
 * Registros de ponto de um período e o total por dia (só os próprios sem Ponto da equipe; a API filtra).
 * filtros: { inicio, fim (dayjs, fim inclusive), funcionarioId? }.
 * Retorna { registros, totais, carregando, atualizando, erro, recarregar, lancar(valores), corrigir(id, valores) }.
 */
export function usePonto({ inicio, fim, funcionarioId }) {
  const { loja } = useAcesso()
  const fuso = loja?.fusoHorario
  const de = inicio?.format('YYYY-MM-DD') ?? null
  const ate = fim?.format('YYYY-MM-DD') ?? de
  const consulta = useConsulta(
    (sinal) => listarPonto({ inicio: de, fim: ate, funcionarioId }, fuso, sinal),
    ['ponto', de, ate, funcionarioId ?? null, fuso],
  )
  const { recarregar } = consulta

  const lancar = useCallback(
    async (valores) => {
      const registro = await lancarPonto(valores, fuso)
      recarregar()
      return registro
    },
    [fuso, recarregar],
  )

  const corrigir = useCallback(
    async (id, valores) => {
      const registro = await corrigirPonto(id, valores, fuso)
      recarregar()
      return registro
    },
    [fuso, recarregar],
  )

  return {
    registros: consulta.dados?.registros ?? [],
    totais: consulta.dados?.totais ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    lancar,
    corrigir,
  }
}

/**
 * Situação do ponto de um funcionário (em serviço ou não) e o registro de entrada/saída agora.
 * funcionarioId vazio = o próprio usuário. ativo = false: não consulta (sem permissão de registrar).
 * Retorna { aberto (registro em aberto ou null), carregando, atualizando, erro, recarregar,
 *   registrar() => Promise<{acao, registro}> }.
 * carregando: a situação deste funcionário ainda não chegou (ao trocar de funcionário, a do anterior não vale:
 *   aberto fica null e carregando true até o GET do novo responder). atualizando: relendo do servidor.
 * Se a situação mudou em outro lugar (409), a consulta é refeita para o botão voltar a bater.
 */
export function usePontoAberto(funcionarioId, { ativo = true, aoRegistrar } = {}) {
  const { loja, usuario } = useAcesso()
  const fuso = loja?.fusoHorario
  // O próprio usuário vai sem funcionario_id (vale para quem só tem Ponto próprio)
  const alvo = funcionarioId && funcionarioId !== usuario?.id ? funcionarioId : undefined
  const chaveAlvo = alvo ?? 'eu'
  const consulta = useConsulta(
    async (sinal) => ({ alvo: chaveAlvo, registro: await obterPontoAberto(alvo, fuso, sinal) }),
    ['ponto-aberto', chaveAlvo, fuso],
    { ativo },
  )
  const { recarregar } = consulta
  // A resposta guardada pode ser do funcionário anterior (useConsulta mantém os dados enquanto busca)
  const doAlvo = consulta.dados?.alvo === chaveAlvo
  const aberto = doAlvo ? consulta.dados.registro : null
  const carregando = ativo && !consulta.erro && (!doAlvo || consulta.carregando)

  const registrar = useCallback(async () => {
    if (!doAlvo) throw new Error('A situação do ponto ainda não foi carregada.')
    try {
      return await registrarPonto(aberto ? 'saida' : 'entrada', alvo, fuso)
    } finally {
      // Deu certo ou não (409: a situação mudou em outro lugar), relê a situação e a lista do servidor
      recarregar()
      aoRegistrar?.()
    }
  }, [doAlvo, aberto, alvo, fuso, recarregar, aoRegistrar])

  return {
    aberto: aberto ?? null,
    carregando,
    atualizando: ativo && (carregando || consulta.atualizando),
    erro: consulta.erro,
    recarregar,
    registrar,
  }
}

/** Funcionários para o ponto da equipe ({ itens: [{id, nome, cor, ativo}], carregando, erro, recarregar }). */
export function useFuncionariosPonto({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => listarFuncionariosPonto(sinal), ['ponto-funcionarios'], { ativo, inicial: [] })
  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}
