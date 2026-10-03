import { useCallback } from 'react'
import { App } from 'antd'
import { foiCancelada } from './cliente.js'
import { caminhoDoCampo } from './conversao.js'

const mesmoCaminho = (a, b) => JSON.stringify(a) === JSON.stringify(b)

/**
 * Mostra o erro da API do jeito certo para cada status (skill integracao-api, seção 5).
 * tratar(erro, opcoes):
 *   form: Form do antd; o 422 vai para os campos (form.setFields) e o que não mapear vira mensagem geral.
 *   mapa: { campo_da_api: 'campoDaTela' | ['caminho', 0, 'campo'] } quando o nome muda entre API e tela.
 *   aoNaoEncontrado: 404 (registro excluído ou de outra loja): fechar o painel e atualizar a lista.
 *   aoConflito: 409, depois da mensagem (ex.: recarregar a disponibilidade).
 * A mensagem é sempre a do servidor (já em português). Cancelamento é ignorado; 401 é tratado pela sessão.
 */
export function useTratarErro() {
  const { message } = App.useApp()

  return useCallback(
    (erro, { form, mapa = {}, aoNaoEncontrado, aoConflito } = {}) => {
      if (!erro || foiCancelada(erro)) return
      if (import.meta.env.DEV) console.warn('[api]', erro.status, erro.mensagem ?? erro)
      const status = erro.status
      const mensagem = erro.mensagem ?? 'Não foi possível concluir a operação.'

      if (status === 401) return // a sessão já leva ao login

      if (status === 422 && form && erro.campos?.length) {
        const registrados = form.getFieldsError().map((f) => f.name)
        const soltos = []
        const porCampo = new Map()
        for (const { campo, mensagem: msg } of erro.campos) {
          const destino = mapa[campo] ?? caminhoDoCampo(campo)
          const caminho = Array.isArray(destino) ? destino : [destino]
          const nome = registrados.find((r) => mesmoCaminho(r, caminho))
          if (!nome) {
            soltos.push(msg)
            continue
          }
          const chave = JSON.stringify(nome)
          porCampo.set(chave, { name: nome, errors: [...(porCampo.get(chave)?.errors ?? []), msg] })
        }
        if (porCampo.size) {
          form.setFields([...porCampo.values()])
          form.scrollToField([...porCampo.values()][0].name)
        }
        if (soltos.length) message.error(soltos.join(' '))
        else if (!porCampo.size) message.error(mensagem)
        return
      }

      if (status === 422 && erro.campos?.length) {
        message.error(erro.campos.map((c) => c.mensagem).join(' '))
        return
      }

      message.error(mensagem)
      if (status === 404) aoNaoEncontrado?.()
      if (status === 409) aoConflito?.()
    },
    [message],
  )
}
