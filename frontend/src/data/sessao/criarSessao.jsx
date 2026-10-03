import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { aoExpirarSessao, chaveSessao, ErroApi, foiCancelada, tokens, usarSessaoDaLoja } from '../api/cliente.js'

export const MSG_SESSAO_EXPIROU = 'Sua sessão expirou. Entre de novo para continuar.'
export const MSG_SESSAO_OUTRA_LOJA = 'A sessão guardada era de outra loja. Entre de novo para continuar.'

/**
 * Sessão de uma área (painel da loja ou SUPERADMIN): token + "quem sou eu" (INT-05 a INT-08).
 * entrarApi(credenciais, slug) => token; euApi(sinal) => dados do usuário logado (já convertidos).
 * aoCarregar(eu): efeito ao receber o usuário (ex.: definir o fuso da loja).
 * slugDoEu(eu): no painel da loja, a loja do usuário logado; diferente do slug da URL = sessão de outra loja.
 * entrarComToken(token): entra com um token pronto (acesso de suporte, PLA-17); expõe suporte/expiraEm de eu.sessao.
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

    // Confere o token guardado (GET /eu) e aplica o resultado. Cancelada pelo sinal = null, sem mexer no estado
    const conferir = useCallback(async (sinal) => {
      try {
        const dados = await euApi(sinal)
        if (sinal.aborted) return null
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
        if (sinal.aborted || foiCancelada(e)) return null
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

    // Só a conferência mais nova vale; desmontar cancela
    const carregarEu = useCallback(() => {
      controle.current?.abort()
      const atual = new AbortController()
      controle.current = atual
      return conferir(atual.signal)
    }, [conferir])

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

    // Acesso de suporte (PLA-17): o token chega pronto (entregue pelo SUPERADMIN no sessionStorage desta aba).
    // Antes de tudo apaga desta aba as outras sessões (a cópia do sessionStorage traz a do SUPERADMIN).
    // A conferência tem sinal próprio: a do efeito de montagem (mesmo token) não a cancela. Rejeita com ErroApi.
    const entrarComToken = useCallback(
      async (token) => {
        tokens.manterSo(chave)
        if (typeof token !== 'string' || !token) {
          tokens.limpar(chave)
          throw new ErroApi({ status: 401, mensagem: MSG_SESSAO_EXPIROU })
        }
        controle.current?.abort()
        tokens.gravar(chave, token)
        setMotivo(null)
        try {
          const dados = await conferir(new AbortController().signal)
          if (!dados) throw new ErroApi({ status: 401, mensagem: MSG_SESSAO_EXPIROU })
          // Só token de suporte entra por aqui: um token comum de funcionário plantado na entrega
          // (login forçado por outra página) é recusado como inválido
          if (dados.sessao?.suporte !== true) throw new ErroApi({ status: 401, mensagem: MSG_SESSAO_EXPIROU })
          return dados
        } catch (e) {
          // Sem conexão: a tela oferece "Tentar de novo" com o mesmo token; até lá, ninguém logado aqui.
          // Cancela também a conferência do efeito de montagem (roda depois do efeito da tela, já com este
          // token): sem o abort, ela terminaria depois e marcaria 'logado' um token recusado aqui.
          controle.current?.abort()
          if (tokens.ler(chave) === token) tokens.limpar(chave)
          setEu(null)
          setErro(null)
          setEstado('anonimo')
          throw e
        }
      },
      [chave, conferir],
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

    // eu.sessao (só no painel da loja): sessão aberta pelo suporte e quando o token vence
    const suporte = eu?.sessao?.suporte === true
    const expiraEm = eu?.sessao?.expiraEm ?? null

    const valor = useMemo(
      () => ({
        estado,
        eu,
        motivo,
        erro,
        suporte,
        expiraEm,
        entrar,
        entrarComToken,
        sair,
        recarregar: carregarEu,
        tentarDeNovo,
      }),
      [estado, eu, motivo, erro, suporte, expiraEm, entrar, entrarComToken, sair, carregarEu, tentarDeNovo],
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
