// Entrega do token de suporte (PLA-17) da aba do SUPERADMIN para a aba nova do painel, sem passar pela URL:
// quem abre grava no sessionStorage da aba about:blank (mesma origem); a tela /suporte lê e apaga na hora.
export const CHAVE_ENTREGA_SUPORTE = 'agenda.entrega.suporte'

/** Lê o token entregue a esta aba e apaga a chave na hora (lê uma vez só). null se não houver. */
export function retirarEntregaSuporte() {
  try {
    const storage = window.sessionStorage
    const token = storage.getItem(CHAVE_ENTREGA_SUPORTE)
    storage.removeItem(CHAVE_ENTREGA_SUPORTE)
    return token || null
  } catch {
    return null // storage bloqueado: não há entrega
  }
}
