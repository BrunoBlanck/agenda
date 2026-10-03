import { ErroApi } from './cliente.js'
import { lerDataHora } from './conversao.js'

// Ajudantes das funções de área para registros do painel (clientes, funcionários, serviços...).

/**
 * Momento da API (colunas de controle, histórico de estoque) na hora de parede da loja,
 * como texto "AAAA-MM-DDTHH:mm:ss" (o que utils/formatos.js e UltimaAlteracao esperam).
 * Regras de fuso em conversao.js (lerDataHora); fuso: o da loja, se a resposta vier em UTC.
 */
export const lerMomentoNaLoja = (iso, fuso) => lerDataHora(iso, fuso || undefined)?.format('YYYY-MM-DDTHH:mm:ss') ?? null

/** Colunas de controle de todo registro da API (componente UltimaAlteracao). */
export const lerControle = (r, fuso) => ({
  criadoEm: lerMomentoNaLoja(r?.criado_em, fuso),
  atualizadoEm: lerMomentoNaLoja(r?.atualizado_em, fuso),
  atualizadoPor: r?.atualizado_por ?? null,
  atualizadoPorNome: r?.atualizado_por_nome ?? null,
})

/**
 * 409 de unicidade (nome, e-mail ou CPF repetido) vai para o lado do campo, não só num aviso solto
 * (skill integracao-api, tabela de status: "409 ... ao lado do campo"). A mensagem continua a do
 * servidor; o erro passa a ter `campos` (como um 422), que o useTratarErro aplica no Form.
 * regras: [[trecho da mensagem do servidor, campo da API], ...]. Sem correspondência, o erro segue como veio.
 */
export function conflitoNoCampo(erro, regras) {
  if (erro?.status !== 409) return erro
  const texto = String(erro.mensagem ?? '').toLowerCase()
  const regra = regras.find(([trecho]) => texto.includes(trecho.toLowerCase()))
  if (!regra) return erro
  return new ErroApi({ status: 422, mensagem: erro.mensagem, campos: [{ campo: regra[1], mensagem: erro.mensagem }] })
}

/**
 * Erro 422 de regra de negócio (só "detail", sem erros[]) apontado para um campo do formulário,
 * para a mensagem aparecer ao lado dele. regras: [[/texto da mensagem/i, 'campo_da_api'], ...].
 */
export function apontarCampo(erro, regras) {
  if (erro?.status !== 422 || erro.campos?.length || !erro.mensagem) return erro
  const regra = regras.find(([padrao]) => padrao.test(erro.mensagem))
  if (regra) erro.campos = [{ campo: regra[1], mensagem: erro.mensagem }]
  return erro
}
