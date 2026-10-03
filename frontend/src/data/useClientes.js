import { useEffect, useRef, useState } from 'react'
import { useConsulta } from './api/useConsulta.js'
import { excluirCliente, listarClientes, obterCliente, salvarCliente } from './api/clientes.js'

const POR_PAGINA = 20
const ESPERA_BUSCA = 300

/**
 * Lista de clientes para a tela Clientes (formato `lista` do CadastroTabela), paginada no servidor.
 * busca: nome, telefone ou CPF (com ou sem máscara), com espera de 300 ms entre as teclas.
 * filtros: { ativo: true | false | null, canal: 'loja' | 'whatsapp' | 'site' | null }.
 * ativo = false: não busca (sem permissão).
 */
export function useClientes({ ativo = true } = {}) {
  const [busca, setBusca] = useState('')
  const [termo, setTermo] = useState('')
  const [pagina, setPagina] = useState(1)
  const [filtros, setFiltros] = useState({ ativo: null, canal: null })
  const espera = useRef(null)
  useEffect(() => () => clearTimeout(espera.current), [])

  const consulta = useConsulta(
    (sinal) => listarClientes({ busca: termo, ...filtros, pagina, porPagina: POR_PAGINA }, sinal),
    ['clientes', termo, filtros, pagina],
    { ativo },
  )
  const dados = consulta.dados
  const total = dados?.total ?? 0

  // A página pedida deixou de existir (exclusões, outra pessoa mexendo): volta para a última que tem itens
  if (dados && !dados.itens.length && total > 0 && pagina > 1) {
    setPagina(Math.max(1, Math.ceil(total / POR_PAGINA)))
  }

  const mudarBusca = (texto) => {
    setBusca(texto)
    clearTimeout(espera.current)
    espera.current = setTimeout(() => {
      setTermo(texto.trim())
      setPagina(1)
    }, ESPERA_BUSCA)
  }

  const filtrar = (campo, valor) => {
    setFiltros((atual) => ({ ...atual, [campo]: valor ?? null }))
    setPagina(1)
  }

  return {
    itens: dados?.itens ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    paginacao: { pagina, porPagina: POR_PAGINA, total, mudarPagina: setPagina },
    busca: { valor: busca, mudar: mudarBusca },
    filtros,
    filtrar,
    carregarRegistro: (registro) => obterCliente(registro.id),
    salvar: async (valores, registro) => {
      const salvo = await salvarCliente(valores, registro?.id)
      consulta.recarregar()
      return salvo
    },
    excluir: async (registro) => {
      await excluirCliente(registro.id)
      consulta.recarregar()
    },
  }
}
