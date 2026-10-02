import { useState } from 'react'

// Estado de um painel lateral: o registro aberto fica guardado enquanto o painel anima o fechamento
// (aberto e registro separados), e destaqueId marca a origem (linha ou cartão) só enquanto está aberto.
// abrir({}) = registro novo; abrir(item) = edição.
export function usePainel() {
  const [aberto, setAberto] = useState(false)
  const [registro, setRegistro] = useState(null)
  return {
    aberto,
    registro,
    destaqueId: aberto ? registro?.id : undefined,
    abrir: (item = {}) => {
      setRegistro(item)
      setAberto(true)
    },
    fechar: () => setAberto(false),
  }
}
