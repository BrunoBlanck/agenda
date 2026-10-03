// 409 (unicidade) com campo certo no formulário: a mensagem do servidor vai para o lado do campo e o
// formulário continua preenchido. regras: [{ trecho: 'endereço de acesso', campo: 'slug' }], comparando
// com o `detail` da API (mensagens de backend/app/erros.py). Retorna true se tratou.
export function erroNoCampo(erro, form, regras) {
  if (erro?.status !== 409 || !form || !erro.mensagem) return false
  const regra = regras.find((r) => erro.mensagem.toLowerCase().includes(r.trecho.toLowerCase()))
  if (!regra) return false
  const caminho = Array.isArray(regra.campo) ? regra.campo : [regra.campo]
  const registrado = form.getFieldsError().some((f) => JSON.stringify(f.name) === JSON.stringify(caminho))
  if (!registrado) return false
  form.setFields([{ name: caminho, errors: [erro.mensagem] }])
  form.scrollToField(caminho)
  return true
}
