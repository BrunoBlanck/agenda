import { useSessaoLoja } from './sessao/sessoes.js'
import { useConsulta } from './api/useConsulta.js'
import {
  excluirCargo,
  listarCargos,
  listarFuncionarios,
  obterFuncionario,
  salvarCargo,
  salvarFuncionario,
} from './api/funcionarios.js'

// O próprio usuário mudou (nome, cor, cargo): o "eu" da sessão é recarregado para o menu e a agenda
function useRecarregarSeForEu() {
  const { eu, recarregar } = useSessaoLoja()
  return (funcionarioId) => {
    if (funcionarioId && funcionarioId === eu?.funcionario?.id) recarregar().catch(() => {})
  }
}

/**
 * Funcionários da loja (formato `lista` do CadastroTabela). A lista não é paginada na API.
 * Funcionário não é excluído: é inativado (ativo = false) no próprio cadastro.
 * ativo = false: não busca (sem permissão).
 */
export function useFuncionarios({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => listarFuncionarios(sinal), 'funcionarios', { ativo })
  const recarregarSeForEu = useRecarregarSeForEu()

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    carregarRegistro: (registro) => obterFuncionario(registro.id),
    salvar: async (valores, registro) => {
      const salvo = await salvarFuncionario(valores, registro?.id)
      consulta.recarregar()
      recarregarSeForEu(salvo.id)
      return salvo
    },
  }
}

/** Cargos da loja (informativos; quem define o acesso é o perfil). */
export function useCargos({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => listarCargos(sinal), 'cargos', { ativo })

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    /** valores: { nome, ativo }; cargo presente = edição */
    salvar: async (valores, cargo) => {
      const salvo = await salvarCargo({ nome: cargo?.nome, ativo: cargo?.ativo ?? true, ...valores }, cargo?.id)
      consulta.recarregar()
      return salvo
    },
    excluir: async (cargo) => {
      await excluirCargo(cargo.id)
      consulta.recarregar()
    },
  }
}
