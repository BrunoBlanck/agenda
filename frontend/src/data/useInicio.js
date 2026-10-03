import { useConsulta } from './api/useConsulta.js'
import { carregarInicio } from './api/inicio.js'

/**
 * Resumo do dia (GET /api/loja/inicio). Cada bloco é null quando o usuário não pode vê-lo.
 * Retorna { resumo, carregando, atualizando, erro, recarregar }.
 */
export function useInicio() {
  const consulta = useConsulta(carregarInicio, ['inicio'])
  return {
    resumo: consulta.dados,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}
