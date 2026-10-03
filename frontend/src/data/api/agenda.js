import { api } from './cliente.js'
import { enviarData, lerDataHora, lerHora } from './conversao.js'
import { converterAgendamentos } from './agendamentos.js'

// Agenda (/api/loja/agenda): agendamentos, profissionais, jornada e bloqueios de um período.
// Quem só tem Minha agenda recebe só os próprios (o servidor ignora o filtro de profissional).

const lista = (v) => (Array.isArray(v) ? v : [])
// Hora de parede da loja, sem fuso ("AAAA-MM-DDTHH:mm:ss"): dayjs lê no fuso do navegador sem deslocar
const momento = (iso) => lerDataHora(iso)?.format('YYYY-MM-DDTHH:mm:ss') ?? null

/** { inicio, fim, funcionarioId } (datas dayjs ou "AAAA-MM-DD"; até 62 dias). */
export async function carregarAgenda({ inicio, fim, funcionarioId }, sinal) {
  const dados = await api.loja.get('/agenda', {
    query: { inicio: enviarData(inicio), fim: enviarData(fim), funcionario_id: funcionarioId },
    sinal,
  })
  return {
    soPropria: !!dados?.so_propria,
    profissionais: lista(dados?.profissionais).map((p) => ({
      id: p?.id,
      nome: p?.nome ?? '—',
      cor: p?.cor_agenda ?? null,
      perfilId: p?.perfil_id ?? null,
      ativo: p?.ativo ?? true,
    })),
    // Sem data válida não há onde posicionar na grade
    agendamentos: converterAgendamentos(dados?.agendamentos).filter((a) => a.data && a.hora),
    jornadas: lista(dados?.jornadas)
      .map((j) => ({
        id: j?.id,
        perfilId: j?.perfil_id ?? null,
        diaSemana: j?.dia_semana,
        inicio: lerHora(j?.hora_inicio),
        fim: lerHora(j?.hora_fim),
      }))
      .filter((j) => j.inicio && j.fim),
    bloqueios: lista(dados?.bloqueios)
      .map((b) => ({
        id: b?.id,
        perfilId: b?.perfil_id ?? null,
        funcionarioId: b?.funcionario_id ?? null,
        inicio: momento(b?.inicio),
        fim: momento(b?.fim),
        motivo: b?.motivo || 'sem motivo informado',
        alvo: b?.alvo ?? 'loja',
        // Para quem é o bloqueio, em texto. null = loja inteira
        quem: b?.alvo === 'loja' || b?.alvo == null ? null : (b?.quem ?? '—'),
      }))
      .filter((b) => b.inicio && b.fim),
  }
}
