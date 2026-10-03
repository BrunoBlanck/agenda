import { useSessaoLoja } from './sessao/sessoes.js'
import { useConsulta } from './api/useConsulta.js'
import {
  adicionarHorario,
  criarBloqueio,
  criarPerfil,
  definirAcessos,
  editarPerfil,
  excluirPerfil,
  listarBloqueios,
  listarHorarios,
  listarPerfis,
  listarRecursos,
  obterPerfil,
  removerBloqueio,
  removerHorario,
} from './api/perfis.js'

/**
 * Perfis da loja. Liberada para quem lê Perfis de acesso, Horários e bloqueios ou Funcionários;
 * os níveis (acessos) só vêm para quem lê Perfis de acesso (senão acessos = null).
 * Alterar o perfil do próprio usuário recarrega o "eu" da sessão (menu e permissões).
 */
export function usePerfis({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => listarPerfis(sinal), 'perfis', { ativo })
  const { eu, recarregar: recarregarEu } = useSessaoLoja()

  // Troca um perfil na lista pela versão que a API devolveu (sem buscar a lista inteira)
  const substituir = (perfil) => {
    consulta.definirDados((lista) => (lista ?? []).map((p) => (p.id === perfil.id ? perfil : p)))
    if (perfil.id === eu?.perfil?.id) recarregarEu().catch(() => {})
    return perfil
  }

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    /** Busca de novo um perfil só (ex.: depois de mexer na jornada, que muda o "sem jornada"). */
    atualizarPerfil: async (id) => substituir(await obterPerfil(id)),
    criar: async (valores) => {
      const novo = await criarPerfil(valores)
      // Já entra na lista (a tela seleciona o novo na hora); a ordem certa vem da API em seguida
      consulta.definirDados((lista) => [...(lista ?? []), novo])
      consulta.recarregar()
      return novo
    },
    editar: async (id, valores) => substituir(await editarPerfil(id, valores)),
    definirNivel: async (id, codigoRecurso, nivel) => substituir(await definirAcessos(id, { [codigoRecurso]: nivel })),
    excluir: async (id) => {
      await excluirPerfil(id)
      consulta.recarregar()
    },
  }
}

/** Catálogo de recursos (áreas com nível de acesso), com o módulo e se ele está ligado na loja. */
export function useRecursos({ ativo = true } = {}) {
  const consulta = useConsulta((sinal) => listarRecursos(sinal), 'recursos', { ativo })
  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}

/** Jornada semanal de um perfil (faixas por dia). */
export function useJornada(perfilId, { ativo = true } = {}) {
  const consulta = useConsulta(
    async (sinal) => ({ perfilId, itens: await listarHorarios(perfilId, sinal) }),
    ['jornada', perfilId],
    { ativo: ativo && !!perfilId },
  )
  // A jornada de outro perfil (troca de perfil em andamento) não aparece
  const atual = consulta.dados?.perfilId === perfilId ? consulta.dados.itens : null
  return {
    itens: atual ?? [],
    carregando: !!perfilId && ativo && !atual && !consulta.erro,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    adicionar: async (faixa) => {
      const nova = await adicionarHorario(perfilId, faixa)
      consulta.recarregar()
      return nova
    },
    remover: async (id) => {
      await removerHorario(id)
      consulta.recarregar()
    },
  }
}

/** Bloqueios que atingem o perfil: os da loja inteira, os do perfil e os de cada funcionário dele. */
export function useBloqueios(perfilId, { ativo = true } = {}) {
  const consulta = useConsulta(
    async (sinal) => ({ perfilId, itens: await listarBloqueios(perfilId, sinal) }),
    ['bloqueios', perfilId],
    { ativo: ativo && !!perfilId },
  )
  const atual = consulta.dados?.perfilId === perfilId ? consulta.dados.itens : null
  return {
    itens: atual ?? [],
    carregando: !!perfilId && ativo && !atual && !consulta.erro,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    criar: async (dados) => {
      const novo = await criarBloqueio(dados)
      consulta.recarregar()
      return novo
    },
    remover: async (id) => {
      await removerBloqueio(id)
      consulta.recarregar()
    },
  }
}
