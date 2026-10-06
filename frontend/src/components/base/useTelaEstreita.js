import { useSyncExternalStore } from 'react'

// Celular (abaixo de 768 px, o "md" do antd): listas viram cartões (DIR-004)
const consulta = window.matchMedia('(max-width: 767.98px)')

const assinar = (avisar) => {
  consulta.addEventListener('change', avisar)
  return () => consulta.removeEventListener('change', avisar)
}

export function useTelaEstreita() {
  return useSyncExternalStore(
    assinar,
    () => consulta.matches,
    () => false,
  )
}
