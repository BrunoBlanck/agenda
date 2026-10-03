import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { aoExpirarSessao, foiCancelada, tokens } from '../api/cliente.js'

export const MSG_SESSAO_EXPIROU = 'Sua sessão expirou. Entre de novo para continuar.'

/**
 * Sessão de uma área (painel da loja ou SUPERADMIN): token + "quem sou eu" (INT-05 a INT-08).
 * entrarApi(credenciais) => token; euApi(sinal) => dados do usuário logado (já convertidos).
 * aoCarregar(eu): efeito ao receber o usuário (ex.: definir o fuso da loja).
 * Estados: verificando (token guardado, conferindo), anonimo, logado, falhou (sem conexão ao conferir).
 */
export function criarSessao(area, { entrarApi, euApi, aoCarregar }) {
  const Contexto = createContext(null)

  function Provider({ children }) {
    const temToken = !!tokens.ler(area)
    const [estado, setEstado] = useState(temToken ? 'verificando' : 'anonimo')
    const [eu, setEu] = useState(null)
    // Por que voltou ao login (sessão expirou, loja suspensa...): mostrado na tela de login
    const [motivo, setMotivo] = useState(null)
    const [erro, setErro] = useState(null)
    const controle = useRef(null)

    const carregarEu = useCallback(async () => {
      controle.current?.abort()
      const atual = new AbortController()
      controle.current = atual
      try {
        const dados = await euApi(atual.signal)
        if (atual.signal.aborted) return null
        aoCarregar?.(dados)
        setEu(dados)
        setErro(null)
        setEstado('logado')
        return dados
      } catch (e) {
        if (atual.signal.aborted || foiCancelada(e)) return null
        if (e.status === 401 || e.status === 403) {
          tokens.limpar(area)
          setEu(null)
          setMotivo(e.status === 403 ? e.mensagem : MSG_SESSAO_EXPIROU)
          setEstado('anonimo')
        } else {
          setErro(e)
          setEstado('falhou')
        }
        throw e
      }
    }, [])

    useEffect(() => {
      if (tokens.ler(area)) carregarEu().catch(() => {})
      return () => controle.current?.abort()
    }, [carregarEu])

    useEffect(
      () =>
        aoExpirarSessao((qual) => {
          if (qual !== area) return
          controle.current?.abort()
          setEu(null)
          setMotivo(MSG_SESSAO_EXPIROU)
          setEstado('anonimo')
        }),
      [],
    )

    const entrar = useCallback(
      async (credenciais) => {
        const token = await entrarApi(credenciais)
        tokens.gravar(area, token)
        setMotivo(null)
        try {
          return await carregarEu()
        } catch (e) {
          tokens.limpar(area)
          throw e
        }
      },
      [carregarEu],
    )

    const sair = useCallback(() => {
      controle.current?.abort()
      tokens.limpar(area)
      setEu(null)
      setMotivo(null)
      setEstado('anonimo')
    }, [])

    const tentarDeNovo = useCallback(() => {
      setEstado('verificando')
      carregarEu().catch(() => {})
    }, [carregarEu])

    const valor = useMemo(
      () => ({ estado, eu, motivo, erro, entrar, sair, recarregar: carregarEu, tentarDeNovo }),
      [estado, eu, motivo, erro, entrar, sair, carregarEu, tentarDeNovo],
    )
    return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
  }

  const useSessao = () => {
    const valor = useContext(Contexto)
    if (!valor) throw new Error(`Sessão "${area}" usada fora do Provider`)
    return valor
  }

  return { Provider, useSessao }
}
