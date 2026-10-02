import { inativo, minutosDe } from '../components/agenda/util.js'

// Regras dos locais (estrutura.md, 2.19 e 2.20). No sistema real o back-end valida e o banco
// impede dois agendamentos no mesmo local e horário.

// Como a loja chama os locais na tela (Sala, Cadeira, Consultório...)
export const rotulosLocal = (loja) => ({
  singular: loja?.rotuloLocal || 'Local',
  plural: loja?.rotuloLocalPlural || 'Locais',
})

// Locais ativos onde o serviço pode acontecer. Serviço sem nenhum vínculo (ou sem serviço) = qualquer local ativo
export const locaisDoServico = (servico, locais) => {
  const vinculados = servico?.localIds ?? []
  return locais.filter((l) => l.ativo && (vinculados.length === 0 || vinculados.includes(l.id)))
}

// Algum agendamento ativo já usa o local nesse intervalo? (minutos do dia)
export const localOcupado = (localId, data, ini, fim, agendamentos, ignorarId = null) =>
  agendamentos.some(
    (a) =>
      a.localId === localId &&
      a.id !== ignorarId &&
      a.data === data &&
      !inativo(a) &&
      ini < minutosDe(a.hora) + (a.duracao ?? 0) &&
      fim > minutosDe(a.hora),
  )
