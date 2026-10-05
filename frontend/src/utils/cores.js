// Cores escolhidas pela loja para o site (SIT-13, SIT-14). Só ajuda a tela a avisar antes de salvar:
// quem decide é a API (GER-02), com a mesma fórmula de contraste (WCAG 2, luminância relativa).

/** Contraste mínimo do texto branco sobre a cor (WCAG AA, texto normal). */
export const CONTRASTE_MINIMO = 4.5

const HEX = /^#[0-9a-f]{6}$/

/**
 * Texto digitado → '#rrggbb' em minúsculas, ou null se não for uma cor completa.
 * Aceita espaços em volta, maiúsculas e falta do '#' ("0D4B4F").
 */
export function lerHex(texto) {
  if (typeof texto !== 'string') return null
  let valor = texto.trim().toLowerCase()
  if (!valor.startsWith('#')) valor = `#${valor}`
  return HEX.test(valor) ? valor : null
}

/** Luminância relativa (0 a 1) de '#rrggbb'. */
export function luminancia(hex) {
  const canais = [1, 3, 5].map((i) => {
    const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]
}

/** Razão de contraste (1 a 21) entre duas cores '#rrggbb'. */
export function contraste(a, b) {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (claro + 0.05) / (escuro + 0.05)
}

/** Contraste do texto branco sobre a cor, ou null se o texto não for uma cor válida. */
export function contrasteComBranco(texto) {
  const hex = lerHex(texto)
  return hex ? contraste(hex, '#ffffff') : null
}

/** true quando a cor é válida e o texto branco fica legível sobre ela. */
export const legivelComBranco = (texto) => (contrasteComBranco(texto) ?? 0) >= CONTRASTE_MINIMO

/** Contraste para exibir: 4,48:1 → "4,4:1" (arredonda para baixo, para nunca parecer que passou). */
export const contrasteTexto = (razao) => `${(Math.floor(razao * 10) / 10).toLocaleString('pt-BR')}:1`
