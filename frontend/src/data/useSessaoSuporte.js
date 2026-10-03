import { useSessaoLoja } from './sessao/sessoes.js'

/**
 * Sessão aberta pelo "Acessar loja" do SUPERADMIN (PLA-17), de GET /api/loja/eu (eu.sessao):
 * { suporte: bool, expiraEm: string|null, funcionarioNome: string|null }
 */
export function useSessaoSuporte() {
  const sessao = useSessaoLoja()
  return {
    suporte: sessao.suporte === true,
    expiraEm: sessao.expiraEm ?? null,
    funcionarioNome: sessao.eu?.funcionario?.nome ?? null,
  }
}
