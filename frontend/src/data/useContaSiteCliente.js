import { useCallback } from 'react'
import { useAcesso } from './useAcesso.js'
import { useConsulta } from './api/useConsulta.js'
import { obterContaSite, removerContaSite } from './api/clientes.js'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const SEM_CONTA = { possuiConta: false, criadaEm: null, ultimoAcessoEm: null, codigoPendente: null }

/**
 * Acesso do cliente ao site da loja (GET e DELETE /api/loja/clientes/{id}/conta-site), sempre pelo
 * telefone salvo do cliente. Só para quem tem escrita em Clientes (sem ela não busca: a API daria 403).
 * Não busca com clienteId nulo; busca de novo a cada montagem (a seção é recriada quando o painel abre).
 *
 * Retorna { conta, carregando, atualizando, erro, recarregar, removerAcesso }.
 *   conta: { possuiConta: bool, criadaEm: dayjs | null, ultimoAcessoEm: dayjs | null,
 *            codigoPendente: { codigo: string, expiraEm: dayjs } | null } | null (ainda não carregou ou falhou)
 *   atualizando: recarga em andamento com a conta já na tela.
 *   erro: ErroApi { status, mensagem, campos } | null
 *   removerAcesso() → Promise<void>: remove a conta e invalida os códigos pendentes do telefone;
 *     rejeita com ErroApi (404 = cliente excluído ou sem acesso: a tela recarrega).
 */
export function useContaSiteCliente(clienteId) {
  const { pode } = useAcesso()
  const habilitado = pode('clientes', 'escrita') && typeof clienteId === 'string' && UUID.test(clienteId)

  const consulta = useConsulta(
    async (sinal) => ({ clienteId, conta: await obterContaSite(clienteId, sinal) }),
    ['conta-site', clienteId],
    { ativo: habilitado },
  )
  const { recarregar, definirDados } = consulta

  // Nada do cliente anterior aparece enquanto o novo carrega; a última busca falhou: a conta guardada
  // pode estar errada (cliente excluído, acesso removido), a tela mostra o erro
  const erro = habilitado ? consulta.erro : null
  const conta = habilitado && !erro && consulta.dados?.clienteId === clienteId ? consulta.dados.conta : null

  const removerAcesso = useCallback(async () => {
    await removerContaSite(clienteId)
    // A remoção também invalida os códigos do telefone: o servidor confirma na recarga
    definirDados((atual) => (atual?.clienteId === clienteId ? { clienteId, conta: SEM_CONTA } : atual))
    recarregar()
  }, [clienteId, definirDados, recarregar])

  return {
    conta,
    carregando: habilitado && !conta && !erro,
    atualizando: !!conta && consulta.atualizando,
    erro,
    recarregar,
    removerAcesso,
  }
}
