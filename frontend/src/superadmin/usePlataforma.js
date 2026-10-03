import { useCallback, useEffect, useState } from 'react'
import { useConsulta } from '../data/api/useConsulta.js'
import {
  criarLoja,
  definirModuloLoja,
  enviarLogoDaLoja,
  excluirLoja,
  excluirPlano,
  excluirUsuario,
  listarAuditoria,
  listarFuncionariosLoja,
  listarLojas,
  listarModulosLoja,
  listarOpcoesLojas,
  listarPerfisLoja,
  listarPessoasAuditoria,
  listarPlanos,
  listarTabelasAuditoria,
  listarUsuarios,
  mudarStatusLoja,
  obterLoja,
  obterPlano,
  obterUsuario,
  obterVisaoGeral,
  redefinirSenhaFuncionario,
  removerLogoDaLoja,
  salvarFuncionarioLoja,
  salvarLoja,
  salvarPlano,
  salvarUsuario,
} from '../data/api/plataforma.js'

// Hooks do SUPERADMIN, todos ligados à API (/api/superadmin). Cada um expõe carregando/erro/recarregar
// para os estados da tela; as ações devolvem Promise e rejeitam com ErroApi { status, mensagem, campos }.

const VAZIO = []

/** Valor que só muda depois de `ms` sem alteração (busca no servidor sem uma requisição por tecla). */
export function useAtrasado(valor, ms = 300) {
  const [atrasado, setAtrasado] = useState(valor)
  useEffect(() => {
    const relogio = setTimeout(() => setAtrasado(valor), ms)
    return () => clearTimeout(relogio)
  }, [valor, ms])
  return atrasado
}

// --- Visão geral ---------------------------------------------------------------------------------

/** Números da plataforma + lojas suspensas (para "Precisa de atenção"). */
export function useVisaoGeral() {
  const consulta = useConsulta(
    async (sinal) => {
      const [visao, suspensas] = await Promise.all([
        obterVisaoGeral(sinal),
        listarLojas({ status: 'suspensa', porPagina: 10 }, sinal),
      ])
      return { ...visao, suspensas: suspensas.itens, totalSuspensas: suspensas.total }
    },
    'visao-geral',
  )
  return { visao: consulta.dados, carregando: consulta.carregando, erro: consulta.erro, recarregar: consulta.recarregar }
}

// --- Lojas ---------------------------------------------------------------------------------------

/** Lista paginada no servidor. filtros: { busca, tipo, status, pagina }. */
export function useLojas({ busca = '', tipo = null, status = null, pagina = 1 } = {}) {
  const filtros = { busca: busca.trim(), tipo, status, pagina }
  const consulta = useConsulta((sinal) => listarLojas(filtros, sinal), ['lojas', filtros])
  const dados = consulta.dados
  return {
    itens: dados?.itens ?? VAZIO,
    total: dados?.total ?? 0,
    pagina: dados?.pagina ?? pagina,
    porPagina: dados?.porPagina ?? 20,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    /** Resolve com { loja, admin, senhaProvisoria }. */
    criar: criarLoja,
  }
}

// Senha provisória do primeiro Administrador de uma loja recém-criada, entregue da tela Lojas ao detalhe.
// Fica só na memória desta aba (nunca em history.state, URL ou sessionStorage): some no F5, no voltar/avançar
// e depois de mostrada uma vez.
const senhasDeLojaNova = new Map()

/** Guarda a senha provisória para o detalhe da loja mostrar uma única vez. dados: { nome, email, senha }. */
export function entregarSenhaDaLojaNova(lojaId, dados) {
  if (lojaId && dados?.senha) senhasDeLojaNova.set(lojaId, dados)
}

/**
 * Senha provisória da loja recém-criada ({ nome, email, senha } ou null), retirada da memória ao aparecer:
 * sair e voltar ao detalhe não mostra de novo. Retorna [senha, esquecer].
 */
export function useSenhaDaLojaNova(lojaId) {
  const [senha, setSenha] = useState(() => senhasDeLojaNova.get(lojaId) ?? null)
  useEffect(() => {
    senhasDeLojaNova.delete(lojaId)
  }, [lojaId])
  return [senha, useCallback(() => setSenha(null), [])]
}

/** Todas as lojas (id e nome), para listas de escolha. */
export function useOpcoesLojas() {
  const consulta = useConsulta((sinal) => listarOpcoesLojas(sinal), 'lojas-opcoes')
  return { opcoes: consulta.dados ?? VAZIO, carregando: consulta.carregando, erro: consulta.erro, recarregar: consulta.recarregar }
}

/** Uma loja: dados, edição, logo, situação e exclusão. A resposta da API atualiza a tela. */
export function useLoja(lojaId) {
  const consulta = useConsulta((sinal) => obterLoja(lojaId, sinal), ['loja', lojaId], { ativo: !!lojaId })
  const { definirDados } = consulta

  const salvar = useCallback(
    async (valores) => {
      const loja = await salvarLoja(lojaId, valores)
      definirDados(loja)
      return loja
    },
    [lojaId, definirDados],
  )

  const mudarStatus = useCallback(
    async (status) => {
      const loja = await mudarStatusLoja(lojaId, status)
      definirDados(loja)
      return loja
    },
    [lojaId, definirDados],
  )

  const excluir = useCallback(() => excluirLoja(lojaId), [lojaId])

  /** arquivo: File (PNG, JPEG ou WebP, até 2 MB). Resolve com a loja atualizada. */
  const enviarLogo = useCallback(
    async (arquivo) => {
      const loja = await enviarLogoDaLoja(lojaId, arquivo)
      definirDados(loja)
      return loja
    },
    [lojaId, definirDados],
  )

  const { recarregar } = consulta
  const removerLogo = useCallback(async () => {
    await removerLogoDaLoja(lojaId) // 204
    definirDados((atual) => (atual ? { ...atual, logoUrl: null } : atual))
    recarregar() // última alteração vem do servidor
  }, [lojaId, definirDados, recarregar])

  return {
    loja: consulta.dados,
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar,
    salvar,
    mudarStatus,
    excluir,
    enviarLogo,
    removerLogo,
  }
}

/** Módulos da loja (base e opcionais). definir(codigo, { habilitado | observacao | expiraEm }). */
export function useModulosLoja(lojaId) {
  const consulta = useConsulta((sinal) => listarModulosLoja(lojaId, sinal), ['modulos', lojaId], { ativo: !!lojaId })
  const { definirDados } = consulta

  const definir = useCallback(
    async (codigo, campos) => {
      const modulo = await definirModuloLoja(lojaId, codigo, campos)
      definirDados((atual) => (atual ?? []).map((m) => (m.codigo === codigo ? modulo : m)))
      return modulo
    },
    [lojaId, definirDados],
  )

  return {
    itens: consulta.dados ?? VAZIO,
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    definir,
  }
}

export function usePerfisLoja(lojaId) {
  const consulta = useConsulta((sinal) => listarPerfisLoja(lojaId, sinal), ['perfis', lojaId], { ativo: !!lojaId })
  return { perfis: consulta.dados ?? VAZIO, carregando: consulta.carregando, erro: consulta.erro, recarregar: consulta.recarregar }
}

/** Funcionários da loja (ativos e inativos), cadastrados pelo suporte. */
export function useFuncionariosLoja(lojaId) {
  const consulta = useConsulta((sinal) => listarFuncionariosLoja(lojaId, sinal), ['funcionarios', lojaId], {
    ativo: !!lojaId,
  })
  const { recarregar } = consulta

  /** Resolve com { funcionario, senhaProvisoria? }; a lista é recarregada do servidor. */
  const salvar = useCallback(
    async (valores, registro) => {
      const resposta = await salvarFuncionarioLoja(lojaId, valores, registro?.id)
      recarregar()
      return resposta
    },
    [lojaId, recarregar],
  )

  /** senha vazia = provisória gerada. Resolve com { mensagem, senhaProvisoria }. */
  const redefinirSenha = useCallback(
    (funcionario, senha) => redefinirSenhaFuncionario(lojaId, funcionario.id, senha),
    [lojaId],
  )

  return {
    itens: consulta.dados ?? VAZIO,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    redefinirSenha,
  }
}

// --- Planos e usuários admin (formato da `lista` do CadastroTabela) ------------------------------

export function usePlanos() {
  const consulta = useConsulta((sinal) => listarPlanos(sinal), 'planos')
  const { recarregar } = consulta

  const salvar = useCallback(
    async (valores, registro) => {
      const plano = await salvarPlano(valores, registro?.id)
      recarregar()
      return plano
    },
    [recarregar],
  )

  const excluir = useCallback(
    async (registro) => {
      await excluirPlano(registro.id)
      recarregar()
    },
    [recarregar],
  )

  return {
    itens: consulta.dados ?? VAZIO,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    excluir,
    carregarRegistro: (registro) => obterPlano(registro.id),
  }
}

/** Usuários admin. senhaGerada: { nome, email, senha } da última senha provisória (mostrar uma vez). */
export function useUsuarios() {
  const consulta = useConsulta((sinal) => listarUsuarios(sinal), 'usuarios')
  const { recarregar } = consulta
  const [senhaGerada, setSenhaGerada] = useState(null)

  const salvar = useCallback(
    async (valores, registro) => {
      const { usuario, senhaProvisoria } = await salvarUsuario(valores, registro?.id)
      setSenhaGerada(senhaProvisoria ? { nome: usuario.nome, email: usuario.email, senha: senhaProvisoria } : null)
      recarregar()
      return usuario
    },
    [recarregar],
  )

  const excluir = useCallback(
    async (registro) => {
      await excluirUsuario(registro.id)
      recarregar()
    },
    [recarregar],
  )

  return {
    itens: consulta.dados ?? VAZIO,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    excluir,
    carregarRegistro: (registro) => obterUsuario(registro.id),
    senhaGerada,
    esquecerSenha: () => setSenhaGerada(null),
  }
}

// --- Auditoria -----------------------------------------------------------------------------------

export function useTabelasAuditoria() {
  const consulta = useConsulta((sinal) => listarTabelasAuditoria(sinal), 'auditoria-tabelas')
  return {
    tabelas: consulta.dados ?? { loja: {}, plataforma: {} },
    carregando: consulta.carregando,
    erro: consulta.erro,
  }
}

/** Alterações paginadas no servidor. filtros: { loja, tabela, periodo, inicio, fim, quem, pagina }. */
export function useAuditoria(filtros) {
  const consulta = useConsulta((sinal) => listarAuditoria(filtros, sinal), ['auditoria', filtros], {
    ativo: !!filtros.loja,
  })
  const dados = consulta.dados
  return {
    itens: dados?.itens ?? VAZIO,
    total: dados?.total ?? 0,
    pagina: dados?.pagina ?? filtros.pagina ?? 1,
    porPagina: dados?.porPagina ?? 20,
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}

/** Quem fez alterações com os mesmos filtros (sem "quem"), para o filtro de pessoa. */
export function usePessoasAuditoria({ loja, tabela, periodo, inicio, fim }) {
  const filtros = { loja, tabela, periodo, inicio, fim }
  const consulta = useConsulta((sinal) => listarPessoasAuditoria(filtros, sinal), ['auditoria-pessoas', filtros], {
    ativo: !!loja,
  })
  return { pessoas: consulta.dados ?? VAZIO, carregando: consulta.carregando }
}
