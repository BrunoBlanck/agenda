import { useCallback, useState } from 'react'
import { useConsulta } from './api/useConsulta.js'
import { agoraNaLoja } from './api/conversao.js'
import {
  listarAgendamentosDoLocal,
  listarLocais,
  obterLocal,
  obterRotulosLocal,
  salvarLocal,
  salvarRotulosLocal,
} from './api/locais.js'
import { useAcesso } from './useAcesso.js'
import { useSessaoLoja } from './sessao/sessoes.js'

/**
 * Locais da loja, no formato de lista do CadastroTabela (sem excluir: local é inativado).
 * { itens, carregando, atualizando, erro, recarregar, salvar(valores, registro), carregarRegistro(registro) }.
 */
export function useLocais() {
  const { loja } = useAcesso()
  const fuso = loja?.fusoHorario
  const consulta = useConsulta((sinal) => listarLocais(fuso, sinal), ['locais', fuso], { inicial: [] })
  const { recarregar } = consulta

  const salvar = useCallback(
    async (valores, registro) => {
      const salvo = await salvarLocal(valores, registro?.id, fuso)
      recarregar()
      return salvo
    },
    [fuso, recarregar],
  )

  const carregarRegistro = useCallback((registro) => obterLocal(registro.id, fuso), [fuso])

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    carregarRegistro,
  }
}

/**
 * Como a loja chama os locais (Sala, Cadeira...). Retorna { rotulos: {singular, plural, atualizadoEm...} | null,
 * carregando, erro, recarregar, salvar({singular, plural}) }. Salvar recarrega a sessão (o menu muda).
 */
export function useRotulosLocal() {
  const { eu, recarregar: recarregarSessao } = useSessaoLoja()
  const fuso = eu?.loja?.fusoHorario
  const consulta = useConsulta((sinal) => obterRotulosLocal(fuso, sinal), ['locais-rotulos', fuso])
  const { definirDados } = consulta

  const salvar = useCallback(
    async (valores) => {
      const salvos = await salvarRotulosLocal(valores, fuso)
      definirDados(salvos)
      recarregarSessao().catch(() => {}) // o menu e os títulos leem o nome do GET /eu
      return salvos
    },
    [fuso, definirDados, recarregarSessao],
  )

  return {
    rotulos: consulta.dados,
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    salvar,
  }
}

const POR_PAGINA_LOCAL = 5

/** Próximos agendamentos de um local (linha expandida), paginados no servidor. */
export function useAgendamentosDoLocal(localId) {
  const [pagina, setPagina] = useState(1)
  // Dia da loja, fixado ao abrir: "de hoje em diante"
  const [desde] = useState(() => agoraNaLoja().format('YYYY-MM-DD'))
  const consulta = useConsulta(
    (sinal) => listarAgendamentosDoLocal(localId, { desde, pagina, porPagina: POR_PAGINA_LOCAL }, sinal),
    ['agendamentos-local', localId, desde, pagina],
  )
  return {
    itens: consulta.dados?.itens ?? [],
    total: consulta.dados?.total ?? 0,
    pagina,
    porPagina: POR_PAGINA_LOCAL,
    mudarPagina: setPagina,
    carregando: consulta.carregando || consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}
