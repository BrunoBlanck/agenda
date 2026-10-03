import { useCallback } from 'react'
import { useConsulta } from './api/useConsulta.js'
import { excluirServico, listarServicos, obterOpcoesServico, obterServico, salvarServico } from './api/servicos.js'
import { useAcesso } from './useAcesso.js'

/**
 * Serviços da loja, no formato de lista do CadastroTabela:
 * { itens, carregando, atualizando, erro, recarregar, salvar(valores, registro), excluir(registro), carregarRegistro(registro) }.
 * Depois de salvar ou excluir, a lista é relida do servidor.
 */
export function useServicos() {
  const { loja, moduloAtivo } = useAcesso()
  const fuso = loja?.fusoHorario
  const comLocais = moduloAtivo('locais')
  const comMateriais = moduloAtivo('materiais')
  const consulta = useConsulta((sinal) => listarServicos(fuso, sinal), ['servicos', fuso], { inicial: [] })
  const { recarregar } = consulta

  const salvar = useCallback(
    async (valores, registro) => {
      const salvo = await salvarServico(valores, registro?.id, { comLocais, comMateriais }, fuso)
      recarregar()
      return salvo
    },
    [comLocais, comMateriais, fuso, recarregar],
  )

  const excluir = useCallback(
    async (registro) => {
      await excluirServico(registro.id)
      recarregar()
    },
    [recarregar],
  )

  const carregarRegistro = useCallback((registro) => obterServico(registro.id, fuso), [fuso])

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    excluir,
    carregarRegistro,
  }
}

/**
 * Profissionais, locais e materiais ativos para o formulário de serviço (só quem edita serviços).
 * Retorna { profissionais, locais, materiais, carregando, erro, recarregar }; listas = null enquanto não carregaram,
 * e locais/materiais = null com o módulo desligado.
 */
export function useOpcoesServico({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => obterOpcoesServico(sinal), ['servicos-opcoes'], { ativo })
  return {
    // null enquanto não carregou (ou desligado): a tela usa só os já vinculados
    profissionais: consulta.dados?.profissionais ?? null,
    locais: consulta.dados?.locais ?? null,
    materiais: consulta.dados?.materiais ?? null,
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}
