import { useCallback, useState } from 'react'
import { useConsulta } from './api/useConsulta.js'
import {
  excluirCategoria,
  excluirMaterial,
  lancarMovimentacao,
  listarCategorias,
  listarMateriais,
  listarMovimentacoes,
  obterMaterial,
  salvarCategoria,
  salvarMaterial,
} from './api/materiais.js'
import { useAcesso } from './useAcesso.js'

/**
 * Materiais e estoque, no formato de lista do CadastroTabela:
 * { itens, carregando, atualizando, erro, recarregar, salvar(valores, registro), excluir(registro), carregarRegistro(registro) }.
 */
export function useMateriais() {
  const { loja } = useAcesso()
  const fuso = loja?.fusoHorario
  const consulta = useConsulta((sinal) => listarMateriais(fuso, sinal), ['materiais', fuso], { inicial: [] })
  const { recarregar } = consulta

  const salvar = useCallback(
    async (valores, registro) => {
      const salvo = await salvarMaterial(valores, registro?.id, fuso)
      recarregar()
      return salvo
    },
    [fuso, recarregar],
  )

  const excluir = useCallback(
    async (registro) => {
      await excluirMaterial(registro.id)
      recarregar()
    },
    [recarregar],
  )

  const carregarRegistro = useCallback((registro) => obterMaterial(registro.id, fuso), [fuso])

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    excluir,
    carregarRegistro,
  }
}

/**
 * Categorias de material. { itens, carregando, atualizando, erro, recarregar, salvar({nome}, id?), excluir(id) }.
 * aoMudar: chamado depois de renomear ou excluir (a lista de materiais mostra o nome da categoria).
 */
export function useCategoriasMaterial({ aoMudar } = {}) {
  const { loja } = useAcesso()
  const fuso = loja?.fusoHorario
  const consulta = useConsulta((sinal) => listarCategorias(fuso, sinal), ['categorias-material', fuso], { inicial: [] })
  const { recarregar } = consulta

  const salvar = useCallback(
    async (valores, id) => {
      const salva = await salvarCategoria(valores, id, fuso)
      recarregar()
      if (id) aoMudar?.()
      return salva
    },
    [fuso, recarregar, aoMudar],
  )

  const excluir = useCallback(
    async (id) => {
      await excluirCategoria(id)
      recarregar()
      aoMudar?.()
    },
    [recarregar, aoMudar],
  )

  return {
    itens: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar,
    salvar,
    excluir,
  }
}

const POR_PAGINA_MOVIMENTACOES = 10

/**
 * Estoque de um material (painel): o material atualizado, o histórico paginado e o lançamento.
 * { material, movimentacoes: {itens, total, pagina, porPagina, mudarPagina, carregando, erro, recarregar},
 *   carregandoMaterial, erroMaterial, lancar({tipo, quantidade, motivo}) => Promise }.
 * ativo = false (painel fechado): não busca. aoLancar: depois de lançar (ex.: atualizar a lista de materiais).
 */
export function useEstoqueMaterial(materialId, { ativo = true, aoLancar } = {}) {
  const { loja } = useAcesso()
  const fuso = loja?.fusoHorario
  const [pagina, setPagina] = useState(1)
  const [idAnterior, setIdAnterior] = useState(materialId)
  if (idAnterior !== materialId) {
    // Outro material: volta para a primeira página (estado anterior, sem efeito)
    setIdAnterior(materialId)
    setPagina(1)
  }
  const ligado = ativo && !!materialId

  const material = useConsulta((sinal) => obterMaterial(materialId, fuso, sinal), ['material', materialId, fuso], { ativo: ligado })
  const historico = useConsulta(
    (sinal) => listarMovimentacoes(materialId, { pagina, porPagina: POR_PAGINA_MOVIMENTACOES }, fuso, sinal),
    ['movimentacoes', materialId, pagina, fuso],
    { ativo: ligado },
  )
  const recarregarMaterial = material.recarregar
  const recarregarHistorico = historico.recarregar

  const lancar = useCallback(
    async (valores) => {
      const lancada = await lancarMovimentacao(materialId, valores, fuso)
      recarregarMaterial()
      if (pagina === 1) recarregarHistorico()
      else setPagina(1) // a mais nova aparece no topo da primeira página
      aoLancar?.()
      return lancada
    },
    [materialId, fuso, pagina, recarregarMaterial, recarregarHistorico, aoLancar],
  )

  return {
    material: material.dados,
    carregandoMaterial: material.carregando,
    erroMaterial: material.erro,
    recarregarMaterial,
    movimentacoes: {
      itens: historico.dados?.itens ?? [],
      total: historico.dados?.total ?? 0,
      pagina,
      porPagina: POR_PAGINA_MOVIMENTACOES,
      mudarPagina: setPagina,
      carregando: historico.carregando || historico.atualizando,
      erro: historico.erro,
      recarregar: recarregarHistorico,
    },
    lancar,
  }
}
