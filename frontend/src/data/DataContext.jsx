import { createContext, useContext, useState } from 'react'
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
import { auditoriaInicial, outrasLojas, planosIniciais, superadminsIniciais, tiposIniciais } from './plataforma.js'

// Estado em memória só para o esboço. Depois será substituído por chamadas à API.
const DataContext = createContext(null)

// Toda linha guarda quando foi criada, quando foi alterada e quem fez a última alteração
// (no banco: criado_em, atualizado_em e atualizado_por, preenchidos por trigger).
// autor = null quando quem altera é o superadmin.
function useLista(inicial, usuarioId) {
  const [itens, setItens] = useState(inicial)
  const carimbo = (autor) => ({ atualizadoEm: new Date().toISOString(), atualizadoPor: autor })
  const adicionar = (item, autor = usuarioId) => {
    const id = Date.now()
    const controle = carimbo(autor)
    setItens((atual) => [...atual, { ...item, id, criadoEm: controle.atualizadoEm, ...controle }])
    return id
  }
  const atualizar = (id, dados, autor = usuarioId) =>
    setItens((atual) => atual.map((i) => (i.id === id ? { ...i, ...dados, ...carimbo(autor) } : i)))
  const remover = (id) => setItens((atual) => atual.filter((i) => i.id !== id))
  return { itens, adicionar, atualizar, remover }
}

export function DataProvider({ children }) {
  // Sem login ainda: o usuário logado é escolhido no painel de demonstração
  const [usuarioId, setUsuarioId] = useState(funcionariosIniciais[0].id)
  const superadminId = superadminsIniciais[0].id

  // Plataforma (SUPERADMIN)
  const lojas = useLista([lojaInicial, ...outrasLojas], usuarioId)
  const auditoria = useLista(auditoriaInicial, null)
  const registrarAuditoria = (acao, lojaId = null, dados = {}) =>
    auditoria.adicionar({ superadminId, lojaId, acao, dados }, null)

  // A loja aberta no painel da loja é a loja 1 da lista da plataforma
  const lojaAtual = lojas.itens.find((l) => l.id === lojaInicial.id)

  const value = {
    lojas,
    lojaAtualId: lojaAtual.id,
    tipos: useLista(tiposIniciais, null),
    planos: useLista(planosIniciais, null),
    superadmins: useLista(superadminsIniciais, null),
    auditoria,
    registrarAuditoria,

    loja: { dados: lojaAtual, atualizar: (dados, autor) => lojas.atualizar(lojaAtual.id, dados, autor) },
    modulos: {
      ativos: lojaAtual.modulos,
      info: lojaAtual.modulosInfo ?? {},
      definir: (codigo, ativo) => lojas.atualizar(lojaAtual.id, { modulos: { ...lojaAtual.modulos, [codigo]: ativo } }, null),
    },
    sessao: { usuarioId, entrarComo: setUsuarioId, superadminId },
    perfis: useLista(perfisIniciais, usuarioId),
    funcionarios: useLista(funcionariosIniciais, usuarioId),
    jornadas: useLista(jornadasIniciais, usuarioId),
    bloqueios: useLista(bloqueiosIniciais, usuarioId),
    clientes: useLista(clientesIniciais, usuarioId),
    materiais: useLista(materiaisIniciais, usuarioId),
    servicos: useLista(servicosIniciais, usuarioId),
    locais: useLista(locaisIniciais, usuarioId),
    agendamentos: useLista(agendamentosIniciais, usuarioId),
    pontos: useLista(pontosIniciais, usuarioId),
  }
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useData() {
  return useContext(DataContext)
}
