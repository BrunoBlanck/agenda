import { createContext, useContext, useRef, useState } from 'react'
import {
  lojaInicial,
  perfisIniciais,
  funcionariosIniciais,
  jornadasIniciais,
  bloqueiosIniciais,
  clientesIniciais,
  materiaisIniciais,
  servicosIniciais,
  locaisIniciais,
  agendamentosIniciais,
  pontosIniciais,
} from './mock.js'
import { historicoInicial, outrasLojas, planosIniciais, superadminsIniciais } from './plataforma.js'

// Estado em memória só para o esboço. Depois será substituído por chamadas à API.
const DataContext = createContext(null)

// Autor das alterações feitas pelo cliente final no site da loja (não é funcionário nem superadmin)
// eslint-disable-next-line react-refresh/only-export-components
export const SITE = 'site'

// Toda linha guarda quando foi criada, quando foi alterada e quem fez a última alteração
// (no banco: criado_em, atualizado_em e atualizado_por, preenchidos por trigger).
// autor = null quando quem altera é o superadmin.
// Nada é apagado de verdade: remover() marca excluidoEm/excluidoPor e a linha some de `itens`
// (continua em `todos`). Cada inserção, alteração e exclusão vai para o histórico (auditoria).
// lojaDe(item): loja dona da linha (null = tabela da plataforma).
function useLista(inicial, usuarioId, { tabela, lojaDe, registrar }) {
  const [todos, setTodos] = useState(inicial)
  const proximoId = useRef(1000) // acima dos ids dos dados de exemplo
  const carimbo = (autor) => ({ atualizadoEm: new Date().toISOString(), atualizadoPor: autor })
  const historico = (operacao, autor, antes, depois) =>
    registrar?.({ lojaId: lojaDe(depois ?? antes), tabela, registroId: (depois ?? antes).id, operacao, antes, depois, autor })

  const adicionar = (item, autor = usuarioId) => {
    const id = ++proximoId.current
    const controle = carimbo(autor)
    const novo = { ...item, id, criadoEm: controle.atualizadoEm, ...controle }
    setTodos((atual) => [...atual, novo])
    historico('inserir', autor, null, novo)
    return id
  }
  // semHistorico: quando quem chama registra a alteração de outra forma (ex.: módulos da loja)
  const atualizar = (id, dados, autor = usuarioId, { semHistorico = false } = {}) => {
    const antes = todos.find((i) => i.id === id)
    if (!antes) return
    const depois = { ...antes, ...dados, ...carimbo(autor) }
    setTodos((atual) => atual.map((i) => (i.id === id ? { ...i, ...dados, ...carimbo(autor) } : i)))
    if (!semHistorico) historico('alterar', autor, antes, depois)
  }
  const remover = (id, autor = usuarioId) => {
    const antes = todos.find((i) => i.id === id)
    if (!antes || antes.excluidoEm) return
    const marca = { excluidoEm: new Date().toISOString(), excluidoPor: autor }
    setTodos((atual) => atual.map((i) => (i.id === id ? { ...i, ...marca } : i)))
    historico('excluir', autor, antes, { ...antes, ...marca })
  }
  return { itens: todos.filter((i) => !i.excluidoEm), todos, adicionar, atualizar, remover }
}

export function DataProvider({ children }) {
  // Sem login ainda: o usuário logado é escolhido no painel de demonstração
  const [usuarioId, setUsuarioId] = useState(funcionariosIniciais[0].id)
  const superadminId = superadminsIniciais[0].id

  // Histórico de alterações de todas as tabelas (no banco: auditoria, preenchida por trigger)
  const [historico, setHistorico] = useState(historicoInicial)
  const proximoHistorico = useRef(historicoInicial.length)
  // autor: id do funcionário, SITE ou null (superadmin)
  const registrar = ({ autor, ...dados }) =>
    setHistorico((atual) => [
      ...atual,
      {
        ...dados,
        id: ++proximoHistorico.current,
        funcionarioId: autor === null || autor === SITE ? null : autor,
        superadminId: autor === null ? superadminId : null,
        site: autor === SITE,
        criadoEm: new Date().toISOString(),
      },
    ])

  const daLoja = (tabela) => ({ tabela, lojaDe: () => lojaInicial.id, registrar })
  const daPlataforma = (tabela) => ({ tabela, lojaDe: () => null, registrar })

  // Plataforma (SUPERADMIN)
  const lojas = useLista([lojaInicial, ...outrasLojas], usuarioId, { tabela: 'lojas', lojaDe: (l) => l.id, registrar })

  // A loja aberta no painel da loja é a loja 1 da lista da plataforma
  const lojaAtual = lojas.itens.find((l) => l.id === lojaInicial.id)

  // Módulos (no banco: loja_funcionalidades). Registra no histórico como tabela própria.
  const definirModulo = (loja, codigo, info, autor = null) => {
    const antes = { codigo, ativo: !!loja.modulos?.[codigo], ...loja.modulosInfo?.[codigo] }
    const { ativo, ...resto } = info
    const dados = {}
    if (ativo !== undefined) dados.modulos = { ...loja.modulos, [codigo]: ativo }
    if (Object.keys(resto).length) dados.modulosInfo = { ...loja.modulosInfo, [codigo]: { ...loja.modulosInfo?.[codigo], ...resto } }
    lojas.atualizar(loja.id, dados, autor, { semHistorico: true })
    registrar({ lojaId: loja.id, tabela: 'loja_funcionalidades', registroId: codigo, operacao: 'alterar', antes, depois: { ...antes, ...info }, autor })
  }

  const value = {
    lojas,
    lojaAtualId: lojaAtual.id,
    planos: useLista(planosIniciais, null, daPlataforma('planos')),
    superadmins: useLista(superadminsIniciais, null, daPlataforma('superadmin_usuarios')),
    historico,
    registrar,
    definirModulo,

    loja: { dados: lojaAtual, atualizar: (dados, autor) => lojas.atualizar(lojaAtual.id, dados, autor) },
    modulos: {
      ativos: lojaAtual.modulos,
      info: lojaAtual.modulosInfo ?? {},
      definir: (codigo, ativo) => definirModulo(lojaAtual, codigo, { ativo }),
    },
    sessao: { usuarioId, entrarComo: setUsuarioId, superadminId },
    perfis: useLista(perfisIniciais, usuarioId, daLoja('perfis')),
    funcionarios: useLista(funcionariosIniciais, usuarioId, daLoja('funcionarios')),
    jornadas: useLista(jornadasIniciais, usuarioId, daLoja('perfil_horarios')),
    bloqueios: useLista(bloqueiosIniciais, usuarioId, daLoja('bloqueios_agenda')),
    clientes: useLista(clientesIniciais, usuarioId, daLoja('clientes')),
    materiais: useLista(materiaisIniciais, usuarioId, daLoja('materiais')),
    servicos: useLista(servicosIniciais, usuarioId, daLoja('servicos')),
    locais: useLista(locaisIniciais, usuarioId, daLoja('locais')),
    agendamentos: useLista(agendamentosIniciais, usuarioId, daLoja('agendamentos')),
    pontos: useLista(pontosIniciais, usuarioId, daLoja('registros_ponto')),
  }
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useData() {
  return useContext(DataContext)
}
