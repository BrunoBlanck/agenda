import { useEffect, useState } from 'react'
import { foiCancelada } from './api/cliente.js'
import { buscarLojaPublica } from './api/site.js'

/**
 * Nome e logo públicos da loja (GET /api/site/{slug}), para o cabeçalho do login do painel.
 * 404 (loja inexistente, suspensa ou cancelada) e falha de conexão vêm em `erro`: a tela segue com o slug
 * como nome e o formulário de login continua (quem diz o motivo certo é a resposta do próprio login).
 * @returns {{ loja: { nome: string, logoUrl: string|null } | null, carregando: boolean, erro: { status: number, mensagem: string } | null }}
 */
export function useLojaPublica(slug) {
  // Guardada com o slug: ao trocar de loja, a resposta da anterior não aparece nem por um instante
  const [resposta, setResposta] = useState({ slug: null, loja: null, erro: null })

  useEffect(() => {
    if (!slug) return undefined
    const controle = new AbortController()
    buscarLojaPublica(slug, controle.signal)
      .then((loja) => {
        if (controle.signal.aborted) return
        // Sem nome (não deveria acontecer): trata como se não tivesse vindo, a tela usa o slug
        setResposta({ slug, loja: loja.nome ? loja : null, erro: null })
      })
      .catch((e) => {
        if (controle.signal.aborted || foiCancelada(e)) return
        setResposta({ slug, loja: null, erro: { status: e?.status ?? 0, mensagem: e?.mensagem ?? 'Não foi possível carregar.' } })
      })
    return () => controle.abort()
  }, [slug])

  const pronta = !!slug && resposta.slug === slug
  return {
    loja: pronta ? resposta.loja : null,
    carregando: !!slug && !pronta,
    erro: pronta ? resposta.erro : null,
  }
}
