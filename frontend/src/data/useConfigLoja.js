import { useCallback } from 'react'
import { useConsulta } from './api/useConsulta.js'
import { enviarLogoLoja, obterDadosLoja, removerLogoLoja, salvarDadosLoja } from './api/configuracoes.js'
import { useSessaoLoja } from './sessao/sessoes.js'

/**
 * Configurações > Dados da loja.
 * Retorna { dados, carregando, atualizando, erro, recarregar, salvar(valores) => Promise<dados>,
 *   enviarLogo(arquivo: File) => Promise<dados>, removerLogo() => Promise }.
 * Nome e logo aparecem no menu (GET /eu): depois de gravar, a sessão é recarregada.
 */
export function useConfigLoja() {
  const { eu, recarregar: recarregarSessao } = useSessaoLoja()
  const fuso = eu?.loja?.fusoHorario
  const consulta = useConsulta((sinal) => obterDadosLoja(fuso, sinal), ['config-loja', fuso])
  const { definirDados, recarregar } = consulta

  const atualizarSessao = useCallback(() => {
    recarregarSessao().catch(() => {}) // falha ao reler o menu não desfaz o que foi salvo
  }, [recarregarSessao])

  const salvar = useCallback(
    async (valores) => {
      const dados = await salvarDadosLoja(valores, fuso)
      definirDados(dados)
      atualizarSessao()
      return dados
    },
    [fuso, definirDados, atualizarSessao],
  )

  const enviarLogo = useCallback(
    async (arquivo) => {
      const dados = await enviarLogoLoja(arquivo, fuso)
      definirDados(dados)
      atualizarSessao()
      return dados
    },
    [fuso, definirDados, atualizarSessao],
  )

  const removerLogo = useCallback(async () => {
    await removerLogoLoja()
    definirDados((atual) => (atual ? { ...atual, logoUrl: null } : atual))
    recarregar()
    atualizarSessao()
  }, [definirDados, recarregar, atualizarSessao])

  return {
    dados: consulta.dados,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    enviarLogo,
    removerLogo,
  }
}
