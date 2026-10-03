import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { aoExpirarSessao, chaveSessao, ErroApi, foiCancelada, tokens, usarSessaoDaLoja } from '../api/cliente.js'

export const MSG_SESSAO_EXPIROU = 'Sua sessão expirou. Entre de novo para continuar.'
export const MSG_SESSAO_OUTRA_LOJA = 'A sessão guardada era de outra loja. Entre de novo para continuar.'

/**
 * Sessão de uma área (painel da loja ou SUPERADMIN): token + "quem sou eu" (INT-05 a INT-08).
 * entrarApi(credenciais, slug) => token; euApi(sinal) => dados do usuário logado (já convertidos).
 * aoCarregar(eu): efeito ao receber o usuário (ex.: definir o fuso da loja).
 * slugDoEu(eu): no painel da loja, a loja do usuário logado; diferente do slug da URL = sessão de outra loja.
 * Provider: no painel da loja recebe `slug` (da URL) e guarda o token só daquela loja (chave 'loja.<slug>').
 * Estados: verificando (token guardado, conferindo), anonimo, logado, falhou (sem conexão ao conferir).
 */
export function criarSessao(area, { entrarApi, euApi, aoCarregar, slugDoEu }) {
  const Contexto = createContext(null)

  // slug fixo durante a vida do Provider (AreaLoja usa key={slug}: trocar de loja monta outro)
  function Provider({ slug, children }) {
    const chave = chaveSessao(area, slug)
    // api.loja passa a usar o token desta loja já na primeira renderização (os filhos buscam antes dos efeitos do pai)
    useState(() => area === 'loja' && usarSessaoDaLoja(chave))
    useLayoutEffect(() => {
      if (area === 'loja') usarSessaoDaLoja(chave)
    }, [chave])
    const temToken = !!tokens.ler(chave)
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
        // Token de outra loja nesta chave (colado à mão, por exemplo): não vale aqui
        if (slugDoEu && slugDoEu(dados) !== slug) {
          throw new ErroApi({ status: 401, mensagem: MSG_SESSAO_OUTRA_LOJA })
        }
        aoCarregar?.(dados)
        setEu(dados)
        setErro(null)
        setEstado('logado')
        return dados
      } catch (e) {
        if (atual.signal.aborted || foiCancelada(e)) return null
        if (e.status === 401 || e.status === 403) {
          tokens.limpar(chave)
          setEu(null)
          setMotivo(e.status === 403 || e.mensagem === MSG_SESSAO_OUTRA_LOJA ? e.mensagem : MSG_SESSAO_EXPIROU)
          setEstado('anonimo')
        } else {
          setErro(e)
          setEstado('falhou')
        }
        throw e
      }
    }, [chave, slug])

    useEffect(() => {
      if (tokens.ler(chave)) carregarEu().catch(() => {})
      return () => controle.current?.abort()
    }, [chave, carregarEu])

    useEffect(
      () =>
        aoExpirarSessao((qual) => {
          if (qual !== chave) return
          controle.current?.abort()
          setEu(null)
          setMotivo(MSG_SESSAO_EXPIROU)
          setEstado('anonimo')
        }),
      [chave],
    )

    const entrar = useCallback(
      async (credenciais) => {
        const token = await entrarApi(credenciais, slug)
        tokens.gravar(chave, token)
        setMotivo(null)
        try {
          return await carregarEu()
        } catch (e) {
          tokens.limpar(chave)
          throw e
        }
      },
      [chave, slug, carregarEu],
    )

    // Sai só desta sessão: as outras lojas (em outras abas) e o SUPERADMIN continuam
    const sair = useCallback(() => {
      controle.current?.abort()
      tokens.limpar(chave)
      setEu(null)
      setMotivo(null)
      setEstado('anonimo')
    }, [chave])

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
