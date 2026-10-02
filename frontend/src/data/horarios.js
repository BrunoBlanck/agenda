// Horários e bloqueios ficam no perfil (estrutura.md, 2.5 e 2.6): o funcionário é vinculado
// a um perfil uma vez só e herda dele os acessos e a jornada semanal.

// Faixas da jornada semanal de um funcionário (as do perfil dele)
export const jornadaDe = (funcionario, jornadas) =>
  funcionario ? jornadas.filter((j) => j.perfilId === funcionario.perfilId) : []

// Bloqueio sem perfil e sem funcionário vale para a loja inteira (ex.: feriado)
export const bloqueioDaLoja = (b) => b.perfilId == null && b.funcionarioId == null

// O bloqueio atinge o funcionário? Loja inteira, o perfil dele ou ele próprio (ex.: férias)
export const bloqueioAtinge = (b, funcionario) =>
  bloqueioDaLoja(b) ||
  (b.funcionarioId != null ? b.funcionarioId === funcionario?.id : b.perfilId === funcionario?.perfilId)

// Para quem é o bloqueio, em texto. null = loja inteira
export function alvoBloqueio(b, funcionarios, perfis) {
  if (b.funcionarioId != null) return funcionarios.find((f) => f.id === b.funcionarioId)?.nome ?? '—'
  if (b.perfilId != null) return `Perfil ${perfis.find((p) => p.id === b.perfilId)?.nome ?? '—'}`
  return null
}
