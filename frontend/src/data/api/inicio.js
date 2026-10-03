import { api } from './cliente.js'
import { lerData, lerDataHora, lerNumero } from './conversao.js'
import { converterAgendamentos } from './agendamentos.js'

// Início (/api/loja/inicio): resumo do dia. Cada bloco vem null quando o usuário não pode vê-lo
// (o servidor decide pelo acesso); null continua null aqui para a tela esconder o bloco.

const ouNulo = (valor, converter) => (Array.isArray(valor) ? converter(valor) : null)

export async function carregarInicio(sinal) {
  const dados = await api.loja.get('/inicio', { sinal })
  return {
    // Hoje no fuso da loja (dayjs) ou null se não veio
    data: lerData(dados?.data),
    soPropria: !!dados?.so_propria,
    agendaHoje: ouNulo(dados?.agenda_hoje, converterAgendamentos),
    solicitacoesSite: ouNulo(dados?.solicitacoes_site, converterAgendamentos),
    clientesCadastrados: lerNumero(dados?.clientes_cadastrados),
    funcionariosEmServico: lerNumero(dados?.funcionarios_em_servico),
    equipeEmServico: ouNulo(dados?.equipe_em_servico, (itens) =>
      itens.map((p) => ({
        id: p?.registro_id ?? p?.funcionario_id,
        funcionarioId: p?.funcionario_id ?? null,
        nome: p?.nome ?? '—',
        cor: p?.cor_agenda ?? null,
        entrada: lerDataHora(p?.entrada)?.format('HH:mm') ?? null,
        // data e hora completas (hora da loja): mostra "desde ontem, 22h" quando o ponto vem de outro dia
        entradaEm: lerDataHora(p?.entrada),
      })),
    ),
    materiaisARepor: ouNulo(dados?.materiais_a_repor, (itens) =>
      itens.map((m) => ({
        id: m?.id,
        nome: m?.nome ?? '—',
        unidade: m?.unidade ?? '',
        quantidade: lerNumero(m?.quantidade_atual) ?? 0,
        minimo: lerNumero(m?.estoque_minimo) ?? 0,
      })),
    ),
  }
}
