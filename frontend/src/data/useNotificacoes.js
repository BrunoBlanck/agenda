import { useCallback, useEffect, useState } from 'react'
import { useConsulta } from './api/useConsulta.js'
import {
  NOTIFICACOES_POR_PAGINA,
  listarNotificacoes,
  obterResumoNotificacoes,
  visualizarNotificacoes,
} from './api/notificacoes.js'
import { useSessaoSuporte } from './useSessaoSuporte.js'

// Sino do painel (NOT-06): GET /api/loja/notificacoes, GET .../resumo, POST .../visualizar.

const INTERVALO_RESUMO = 60_000

/**
 * Quantas notificações do usuário logado ainda não foram visualizadas (sino do cabeçalho).
 * Consulta a cada 60 s (com a aba visível) e ao voltar o foco para a aba.
 * Retorna { naoVisualizadas: number | null, carregando, erro, recarregar }.
 *   naoVisualizadas: null enquanto carrega ou depois de uma falha (o sino fica sem número).
 */
export function useNotificacoesResumo() {
  const consulta = useConsulta(obterResumoNotificacoes, ['notificacoes-resumo'])
  const { recarregar } = consulta

  useEffect(() => {
    const visivel = () => document.visibilityState === 'visible'
    const intervalo = setInterval(() => {
      if (visivel()) recarregar()
    }, INTERVALO_RESUMO)
    const aoVoltar = () => {
      if (visivel()) recarregar()
    }
    window.addEventListener('focus', aoVoltar)
    document.addEventListener('visibilitychange', aoVoltar)
    return () => {
      clearInterval(intervalo)
      window.removeEventListener('focus', aoVoltar)
      document.removeEventListener('visibilitychange', aoVoltar)
    }
  }, [recarregar])

  return {
    naoVisualizadas: consulta.erro ? null : (consulta.dados?.naoVisualizadas ?? null),
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar,
  }
}

/**
 * Notificações do usuário logado, mais novas primeiro, 20 por página.
 * Só busca com aberto = true, e busca de novo (da primeira página) cada vez que aberto volta a ser true.
 * Fechado, a última lista continua (o painel fecha com animação sem trocar de conteúdo).
 *
 * Retorna { itens: Notificacao[], total, temMais, carregando, erro, recarregar,
 *           carregarMais() => Promise<void>, marcarVisualizadas(ids) => Promise<{ naoVisualizadas }> }.
 *   Notificacao: { id, evento, titulo, mensagem, agendamentoId: string | null, inicioAgendamento: dayjs | null,
 *                  visualizada: bool, visualizadaEm: dayjs | null, statusEmail: 1-4, statusWhatsapp: 1-4, criadoEm: dayjs }
 *   carregarMais rejeita com ErroApi { status, mensagem, campos }; marcarVisualizadas também
 *   (a tela ignora a falha: tenta de novo na próxima abertura). marcarVisualizadas não muda os itens já carregados.
 *   No acesso de suporte (SUPERADMIN acessando a loja) nada é marcado: só devolve a contagem atual.
 */
export function useNotificacoes(aberto) {
  const { suporte } = useSessaoSuporte()

  // Cada abertura (e cada "recarregar") é uma busca nova a partir da primeira página
  const [aberturas, setAberturas] = useState(aberto ? 1 : 0)
  const [abertoAntes, setAbertoAntes] = useState(aberto)
  if (aberto !== abertoAntes) {
    setAbertoAntes(aberto)
    if (aberto) setAberturas((n) => n + 1)
  }
  const [versao, setVersao] = useState(0)
  const chave = `${aberturas}-${versao}`

  const habilitado = aberturas > 0
  const primeira = useConsulta((sinal) => listarNotificacoes(1, sinal), ['notificacoes', chave], { ativo: habilitado })

  // Páginas seguintes ("Carregar mais") da busca atual
  const [mais, setMais] = useState({ chave: null, itens: [], pagina: 1, total: null })
  const daBusca = mais.chave === chave ? mais : { itens: [], pagina: 1, total: null }

  const pronta = habilitado && primeira.atual && !!primeira.dados
  // Notificação nova empurra a lista entre uma página e outra: a mesma pode vir duas vezes
  const vistos = new Set()
  const itens = pronta
    ? [...(primeira.dados.itens ?? []), ...daBusca.itens].filter((n) => (vistos.has(n.id) ? false : vistos.add(n.id)))
    : []
  const total = pronta ? (daBusca.total ?? primeira.dados.total) : 0
  const erro = habilitado ? primeira.erro : null

  const carregarMais = useCallback(async () => {
    const pagina = daBusca.pagina + 1
    const resposta = await listarNotificacoes(pagina)
    // A resposta fica guardada com a chave da busca que a pediu: se o painel reabriu nesse meio tempo, é descartada
    setMais((atual) => {
      const anteriores = atual.chave === chave ? atual.itens : []
      return { chave, itens: [...anteriores, ...resposta.itens], pagina, total: resposta.total }
    })
  }, [chave, daBusca.pagina])

  const marcarVisualizadas = useCallback(
    async (ids) => {
      if (suporte) return obterResumoNotificacoes()
      const { naoVisualizadas } = await visualizarNotificacoes(ids)
      return { naoVisualizadas }
    },
    [suporte],
  )

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])

  return {
    itens,
    total,
    temMais: pronta ? daBusca.pagina * NOTIFICACOES_POR_PAGINA < total : false,
    carregando: !!aberto && !pronta && !erro,
    erro,
    recarregar,
    carregarMais,
    marcarVisualizadas,
  }
}
