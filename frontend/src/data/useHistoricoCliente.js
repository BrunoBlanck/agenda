import { useState } from 'react'
import { useAcesso } from './useAcesso.js'
import { useConsulta } from './api/useConsulta.js'
import { historicoCliente } from './api/clientes.js'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/**
 * Histórico do cliente (GET /clientes/{id}/historico): resumo e agendamentos que o usuário logado
 * pode ver, do mais recente para o mais antigo. Quem só vê a própria agenda recebe só os atendimentos
 * dele (parcial = true). A API calcula tudo (números, último, próximo); o navegador só mostra.
 *
 * opcoes: { ativo, filtro: 'todos' | 'concluidos' | 'faltas', porPagina, abertura }.
 *   abertura: mudar o valor busca de novo (ex.: a cada vez que o painel abre).
 * Sem leitura em Clientes não busca (a API responderia 403).
 * Retorna { cliente, concluidos, faltas, cancelados, totalGasto, ultimo, proximo, parcial,
 *   agendamentos, total, listaAtual, carregando, erro, recarregar, carregarMais, carregandoMais }.
 * Cada atendimento: { id, inicio, fim (dayjs, hora da loja), data, hora, horaFim, servicoNome,
 *   funcionarioNome, cor, localNome, localTipo, preco, status, motivoCancelamento }.
 */
export function useHistoricoCliente(clienteId, { ativo = true, filtro = 'todos', porPagina = 10, abertura = 0 } = {}) {
  const { pode } = useAcesso()
  const permitido = pode('clientes')
  const habilitado = ativo && permitido && typeof clienteId === 'string' && UUID.test(clienteId)

  const consulta = useConsulta(
    async (sinal) => ({ clienteId, filtro, ...(await historicoCliente(clienteId, { filtro, pagina: 1, porPagina }, sinal)) }),
    ['historico-cliente', clienteId, filtro, porPagina, abertura],
    { ativo: habilitado },
  )
  // Enquanto a busca de outro cliente não chega, nada do anterior aparece
  const dados = consulta.dados?.clienteId === clienteId ? consulta.dados : null
  // Trocou o filtro: o resumo é o mesmo, a lista ainda é a do filtro anterior
  const listaAtual = dados?.filtro === filtro

  // "Ver mais": páginas seguintes, presas à primeira página que estão completando
  const [mais, setMais] = useState({ base: null, pagina: 1, itens: [] })
  const [carregandoMais, setCarregandoMais] = useState(false)
  const extras = dados && mais.base === consulta.dados ? mais : null

  const carregarMais = async () => {
    const base = consulta.dados
    if (!base || carregandoMais) return
    const proxima = (extras?.pagina ?? 1) + 1
    setCarregandoMais(true)
    try {
      const r = await historicoCliente(base.clienteId, { filtro: base.filtro, pagina: proxima, porPagina })
      setMais((atual) => ({
        base,
        pagina: proxima,
        itens: [...(atual.base === base ? atual.itens : []), ...r.agendamentos.itens],
      }))
    } finally {
      setCarregandoMais(false)
    }
  }

  // Um agendamento criado entre uma página e outra não aparece duas vezes
  const vistos = new Set()
  const agendamentos = [...(dados?.agendamentos.itens ?? []), ...(extras?.itens ?? [])].filter((a) => {
    if (vistos.has(a.id)) return false
    vistos.add(a.id)
    return true
  })

  return {
    permitido,
    cliente: dados?.cliente ?? null,
    concluidos: dados?.concluidos ?? 0,
    faltas: dados?.faltas ?? 0,
    cancelados: dados?.cancelados ?? 0,
    totalGasto: dados?.totalGasto ?? 0,
    ultimo: dados?.ultimo ?? null,
    proximo: dados?.proximo ?? null,
    parcial: !!dados?.parcial,
    agendamentos,
    total: dados?.agendamentos.total ?? 0,
    listaAtual,
    carregando: habilitado && !dados && !consulta.erro,
    atualizando: consulta.atualizando,
    erro: habilitado ? consulta.erro : null,
    recarregar: consulta.recarregar,
    carregarMais,
    carregandoMais,
  }
}
