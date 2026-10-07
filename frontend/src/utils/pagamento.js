import { formasPagamento } from '../data/dominio.js'
import { agoraNaLoja } from '../data/api/conversao.js'
import { horaCurta, moeda } from './formatos.js'

// Textos do pagamento do atendimento (AGE-27). Forma desconhecida (enum novo na API) não quebra.

export const formaPagamento = (forma) => formasPagamento[forma] ?? { label: String(forma ?? '—'), frase: `em ${forma ?? '—'}` }

// "Pix · R$ 50,00" (lista de agendamentos)
export const resumoPagamento = (p) => `${formaPagamento(p.forma).label} · ${moeda(p.valor)}`

// "Pago no Pix · R$ 50,00" (painel do agendamento)
export const fraseDoPagamento = (p) => `Pago ${formaPagamento(p.forma).frase} · ${moeda(p.valor)}`

// "em ter 07/10 às 14h30 por Ana" (ano só quando não é o atual; sem quem registrou, sem o "por")
export function quandoFoiPago(p, agora = agoraNaLoja()) {
  const d = p.pagoEm
  if (!d?.isValid?.()) return p.registradoPorNome ? `por ${p.registradoPorNome}` : null
  const dia = d.format(d.isSame(agora, 'year') ? 'ddd DD/MM' : 'ddd DD/MM/YYYY').replace('.', '')
  const quando = `em ${dia} às ${horaCurta(d.format('HH:mm'))}`
  return p.registradoPorNome ? `${quando} por ${p.registradoPorNome}` : quando
}
