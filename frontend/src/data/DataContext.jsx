import { createContext, useContext, useState } from 'react'
import {
  funcionariosIniciais,
  clientesIniciais,
  materiaisIniciais,
  servicosIniciais,
  agendamentosIniciais,
  pontosIniciais,
} from './mock.js'

// Estado em memória só para o esboço. Depois será substituído por chamadas à API.
const DataContext = createContext(null)

function useLista(inicial) {
  const [itens, setItens] = useState(inicial)
  const adicionar = (item) => setItens((atual) => [...atual, { ...item, id: Date.now() }])
  const atualizar = (id, dados) =>
    setItens((atual) => atual.map((i) => (i.id === id ? { ...i, ...dados } : i)))
  const remover = (id) => setItens((atual) => atual.filter((i) => i.id !== id))
  return { itens, adicionar, atualizar, remover }
}

export function DataProvider({ children }) {
  const value = {
    funcionarios: useLista(funcionariosIniciais),
    clientes: useLista(clientesIniciais),
    materiais: useLista(materiaisIniciais),
    servicos: useLista(servicosIniciais),
    agendamentos: useLista(agendamentosIniciais),
    pontos: useLista(pontosIniciais),
  }
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useData() {
  return useContext(DataContext)
}
