import { useState } from 'react'
import { useAcesso } from './useAcesso.js'
import { useConsulta } from './api/useConsulta.js'
import { listarCodigosSite } from './api/clientes.js'

/**
 * Códigos de confirmação do site ainda pendentes na loja (GET /api/loja/clientes/codigos-site),
 * mais novo primeiro, no máximo 100. Só para quem tem escrita em Clientes (sem ela não busca).
 * Só busca com ativo = true, e busca de novo cada vez que ativo volta a ser true (o painel reabriu:
 * códigos vencem em 15 minutos, dado guardado não serve). Fechado, a última lista continua (o painel
 * fecha com animação sem trocar de conteúdo).
 *
 * Retorna { itens, carregando, atualizando, erro, recarregar }.
 *   itens: [{ telefone: string, codigo: string, expiraEm: dayjs, criadoEm: dayjs,
 *             clientes: [{ id, nome }] (vazio = telefone ainda sem cadastro) }]
 *   atualizando: recarga em andamento com a lista já na tela.
 *   erro: ErroApi { status, mensagem, campos } | null
 */
export function useCodigosSite(ativo) {
  const { pode } = useAcesso()
  const permitido = pode('clientes', 'escrita')

  // Cada abertura é uma busca nova (chave nova)
  const [aberturas, setAberturas] = useState(ativo ? 1 : 0)
  const [ativoAntes, setAtivoAntes] = useState(ativo)
  if (ativo !== ativoAntes) {
    setAtivoAntes(ativo)
    if (ativo) setAberturas((n) => n + 1)
  }

  const habilitado = permitido && aberturas > 0
  const consulta = useConsulta(listarCodigosSite, ['codigos-site', aberturas], { ativo: habilitado })

  // Reabriu: a lista da abertura anterior não aparece enquanto a nova não chega
  const itens = habilitado && consulta.atual && Array.isArray(consulta.dados) ? consulta.dados : null
  const erro = habilitado ? consulta.erro : null

  return {
    itens: itens ?? [],
    carregando: !!ativo && permitido && !itens && !erro,
    atualizando: !!itens && consulta.atualizando,
    erro,
    recarregar: consulta.recarregar,
  }
}
