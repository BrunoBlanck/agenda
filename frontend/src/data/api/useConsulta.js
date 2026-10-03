import { useCallback, useEffect, useRef, useState } from 'react'
import { foiCancelada } from './cliente.js'

/**
 * Carrega dados da API para uma tela (INT-20, INT-21).
 * buscar(sinal) => Promise<dados>. chave: string/array que, ao mudar, busca de novo (filtros, página, id).
 * ativo = false: não busca (ex.: painel fechado, sem permissão) e zera o estado.
 * Resposta de uma busca antiga nunca sobrescreve a mais nova; ao desmontar, cancela.
 * Retorna { dados, carregando, atualizando, atual, erro, recarregar, definirDados }.
 *   carregando: true só enquanto ainda não há dados (recarregar mantém os dados na tela; ver "atualizando").
 *   atual: os dados são da chave atual. Ao trocar a chave, os dados da chave anterior continuam em
 *   "dados" até a nova resposta chegar (atual = false): não os use para decidir uma ação (ex.: botão).
 */
export function useConsulta(buscar, chave, { ativo = true, inicial = null } = {}) {
  const [inicialFixo] = useState(inicial)
  const [estado, setEstado] = useState({ dados: inicial, chave: null, erro: null, buscando: ativo })
  const [versao, setVersao] = useState(0)
  const buscarRef = useRef(buscar)
  useEffect(() => {
    buscarRef.current = buscar
  })

  const chaveTexto = JSON.stringify(chave ?? null)

  useEffect(() => {
    if (!ativo) {
      setEstado({ dados: inicialFixo, chave: null, erro: null, buscando: false })
      return undefined
    }
    const controle = new AbortController()
    setEstado((atual) => ({ ...atual, erro: null, buscando: true }))
    buscarRef.current(controle.signal).then(
      (dados) => {
        if (!controle.signal.aborted) setEstado({ dados, chave: chaveTexto, erro: null, buscando: false })
      },
      (erro) => {
        if (controle.signal.aborted || foiCancelada(erro)) return
        if (import.meta.env.DEV) console.warn('[api]', erro?.status, erro?.mensagem ?? erro)
        setEstado((atual) => ({ ...atual, erro, buscando: false }))
      },
    )
    return () => controle.abort()
    // chaveTexto representa a chave (arrays e objetos comparados pelo conteúdo)
  }, [ativo, chaveTexto, versao, inicialFixo])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])
  const definirDados = useCallback(
    (atualizar) =>
      setEstado((atual) => ({ ...atual, dados: typeof atualizar === 'function' ? atualizar(atual.dados) : atualizar })),
    [],
  )

  return {
    dados: estado.dados,
    erro: estado.erro,
    carregando: estado.buscando && estado.dados === inicialFixo,
    atualizando: estado.buscando,
    atual: estado.chave === chaveTexto,
    recarregar,
    definirDados,
  }
}
