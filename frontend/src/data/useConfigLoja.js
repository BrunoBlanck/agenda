import { useCallback } from 'react'
import { useConsulta } from './api/useConsulta.js'
import {
  enviarLogoLoja,
  obterCoresSite,
  obterDadosLoja,
  removerLogoLoja,
  salvarCoresSite,
  salvarDadosLoja,
} from './api/configuracoes.js'
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

/**
 * Configurações > Dados da loja > Cores do site (SIT-13, SIT-14): GET/PUT /api/loja/configuracoes/site.
 * Retorna { cores: CoresSite | null, carregando, erro, recarregar, salvar({ corTopo, corDestaque }) => Promise<CoresSite> }.
 * CoresSite: { corTopo: '#rrggbb' | null, corDestaque: '#rrggbb' | null, padrao: { corTopo, corDestaque },
 *   tipo: 'clinica' | 'barbearia' | 'escola', criadoEm, atualizadoEm, atualizadoPor, atualizadoPorNome }.
 * null = cor padrão do tipo. salvar rejeita com ErroApi { status, mensagem, campos: [{ campo: 'cor_topo' | 'cor_destaque', mensagem }] }.
 */
export function useCoresSite() {
  const { eu } = useSessaoLoja()
  const fuso = eu?.loja?.fusoHorario
  const consulta = useConsulta((sinal) => obterCoresSite(fuso, sinal), ['cores-site', fuso])
  const { definirDados } = consulta

  // A resposta do PUT já traz as cores gravadas e a última alteração (INT-22)
  const salvar = useCallback(
    async (valores) => {
      const cores = await salvarCoresSite(valores, fuso)
      definirDados(cores)
      return cores
    },
    [fuso, definirDados],
  )

  return { cores: consulta.dados, carregando: consulta.carregando, erro: consulta.erro, recarregar: consulta.recarregar, salvar }
}
