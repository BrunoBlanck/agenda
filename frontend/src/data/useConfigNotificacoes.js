import { useCallback } from 'react'
import { useConsulta } from './api/useConsulta.js'
import { obterConfigNotificacoes, salvarConfigNotificacoes, testarEmailLoja } from './api/notificacoes.js'
import { useSessaoLoja } from './sessao/sessoes.js'

/**
 * Configurações > Dados da loja > Avisos e e-mail (CFG-05, CFG-06):
 * GET/PUT /api/loja/configuracoes/notificacoes e POST .../testar-email.
 * Retorna { config: ConfigNotificacoes | null, carregando, erro, recarregar,
 *           salvar(dados) => Promise<ConfigNotificacoes>, testarEmail(destino) => Promise<{ enviado, erro }> }.
 * ConfigNotificacoes: { antecedenciaClienteMinutos: int,
 *   email: { ativo, servidor, porta, seguranca: 'ssl' | 'starttls' | null, usuario, senhaDefinida, remetenteEmail, remetenteNome },
 *   whatsappDisponivel: bool, criadoEm, atualizadoEm, atualizadoPor, atualizadoPorNome } (controle como em UltimaAlteracao).
 * salvar: dados.email.senha ausente = mantém a senha salva; null = apaga; texto = troca.
 * Erros: ErroApi { status, mensagem, campos: [{ campo: 'email.servidor' | 'antecedencia_cliente_minutos' | ..., mensagem }] }.
 * testarEmail usa a configuração salva; 409 sem e-mail ativo, 429 depois de 5 testes em 10 min, 422 destino inválido.
 */
export function useConfigNotificacoes() {
  const { eu } = useSessaoLoja()
  const fuso = eu?.loja?.fusoHorario
  const consulta = useConsulta((sinal) => obterConfigNotificacoes(fuso, sinal), ['config-notificacoes', fuso])
  const { definirDados } = consulta

  // A resposta do PUT já traz o que foi gravado e a última alteração (INT-22)
  const salvar = useCallback(
    async (dados) => {
      const config = await salvarConfigNotificacoes(dados, fuso)
      definirDados(config)
      return config
    },
    [fuso, definirDados],
  )

  const testarEmail = useCallback((destino) => testarEmailLoja(destino), [])

  return {
    config: consulta.dados,
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    salvar,
    testarEmail,
  }
}
