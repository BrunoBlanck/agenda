import dayjs from 'dayjs'
import { api, urlDaApi } from './cliente.js'
import { lerData, lerDataHora, lerNumero, textoOuNulo } from './conversao.js'

// Site do consumidor (público, sem token): /api/site/{slug}/...
// Loja inexistente, suspensa ou cancelada responde 404 em todas as rotas (SIT-01).

const caminho = (slug, resto = '') => `/${encodeURIComponent(slug ?? '')}${resto}`

// --- API -> tela ---------------------------------------------------------------------------------

function lerLoja(d) {
  return {
    tipo: d?.tipo ?? null,
    slug: d?.slug ?? '',
    nomeFantasia: d?.nome_fantasia || 'Agendamento online',
    logoUrl: urlDaApi(d?.logo_url),
    telefone: d?.telefone ?? null,
    email: d?.email ?? null,
    logradouro: d?.logradouro ?? null,
    numero: d?.numero ?? null,
    complemento: d?.complemento ?? null,
    bairro: d?.bairro ?? null,
    cidade: d?.cidade ?? null,
    uf: d?.uf ?? null,
    fusoHorario: d?.fuso_horario || 'America/Sao_Paulo',
    usaServicos: Boolean(d?.usa_servicos),
    usaLocais: Boolean(d?.usa_locais),
    rotuloLocal: d?.rotulo_local || 'Local',
  }
}

const lerProfissional = (d) => ({ id: d.id, nome: d.nome ?? '', cor: d.cor_agenda ?? null })

// id null = atendimento genérico (loja sem o módulo Serviços); "chave" identifica a opção na tela
const lerServico = (d) => ({
  id: d.id ?? null,
  chave: d.id ?? 'atendimento',
  nome: d.nome ?? '',
  descricao: d.descricao ?? null,
  duracao: Number(d.duracao_minutos) || 0,
  preco: lerNumero(d.preco),
  profissionais: (d.profissionais ?? []).map(lerProfissional),
})

const lerLocal = (d) => (d ? { id: d.id, nome: d.nome ?? '', tipo: d.tipo ?? null } : null)

// "inicio" fica exatamente como veio (com o fuso da loja): é o identificador do horário oferecido e
// volta igual no pedido, sem passar por conversão de fuso.
const lerHorario = (d) => ({
  hora: d.hora ?? lerDataHora(d.inicio)?.format('HH:mm') ?? '',
  inicio: d.inicio,
  funcionarioId: d.funcionario_id,
  funcionarioNome: d.funcionario_nome ?? '',
  local: lerLocal(d.local),
})

const lerDia = (d) => ({ data: d.data, horarios: (d.horarios ?? []).filter((h) => h?.inicio).map(lerHorario) })

const lerPedido = (d) => ({
  id: d?.id ?? null,
  status: d?.status ?? null,
  inicio: lerDataHora(d?.inicio),
  fim: lerDataHora(d?.fim),
  servicoNome: d?.servico_nome ?? '',
  funcionarioNome: d?.funcionario_nome ?? '',
  local: lerLocal(d?.local),
  preco: lerNumero(d?.preco),
  clienteNome: d?.cliente_nome ?? '',
  mensagem: d?.mensagem ?? '',
})

// --- Rotas ---------------------------------------------------------------------------------------

/** GET /api/site/{slug}: dados públicos da loja. */
export const buscarLojaPublica = (slug, sinal) => api.site.get(caminho(slug), { sinal }).then(lerLoja)

/** GET /api/site/{slug}/servicos: serviços ativos com os profissionais (sem o módulo: "Atendimento"). */
export const buscarServicosSite = (slug, sinal) =>
  api.site.get(caminho(slug, '/servicos'), { sinal }).then((lista) => (Array.isArray(lista) ? lista : []).map(lerServico))

/** GET /api/site/{slug}/locais?servico_id=: locais permitidos para o serviço (vazio sem o módulo Locais). */
export const buscarLocaisSite = (slug, servicoId, sinal) =>
  api.site
    .get(caminho(slug, '/locais'), { query: { servico_id: servicoId }, sinal })
    .then((lista) => (Array.isArray(lista) ? lista : []).map(lerLocal).filter(Boolean))

/**
 * GET /api/site/{slug}/horarios: horários livres por dia, já calculados pelo servidor (SIT-04).
 * funcionarioId/localId vazios = qualquer um. inicio/fim: "AAAA-MM-DD" (dia da loja, até 31 dias).
 */
export const buscarHorariosSite = (slug, { servicoId, funcionarioId, localId, inicio, fim }, sinal) =>
  api.site
    .get(caminho(slug, '/horarios'), {
      query: { servico_id: servicoId, funcionario_id: funcionarioId, local_id: localId, inicio, fim },
      sinal,
    })
    .then((lista) => (Array.isArray(lista) ? lista : []).filter((d) => d?.data).map(lerDia))

/**
 * POST /api/site/{slug}/agendamentos: pedido do cliente (entra "Aguardando aceite" no painel).
 * horario: um dos devolvidos por buscarHorariosSite. cliente: { nome, sobrenome, telefone, email, observacoes }.
 */
export function pedirAgendamentoSite(slug, { servicoId, horario, cliente }) {
  const corpo = {
    servico_id: servicoId ?? null,
    funcionario_id: horario.funcionarioId,
    inicio: horario.inicio,
    local_id: horario.local?.id ?? null,
    nome: textoOuNulo(cliente.nome) ?? '',
    sobrenome: textoOuNulo(cliente.sobrenome) ?? '',
    telefone: cliente.telefone ?? '',
    email: textoOuNulo(cliente.email),
    observacoes: textoOuNulo(cliente.observacoes),
  }
  return api.site.post(caminho(slug, '/agendamentos'), corpo).then(lerPedido)
}

// --- Datas ---------------------------------------------------------------------------------------

/** Hoje ("AAAA-MM-DD") no fuso da loja, não no do navegador. */
export function hojeNaLoja(fuso) {
  try {
    return new Intl.DateTimeFormat('sv-SE', { timeZone: fuso, year: 'numeric', month: '2-digit', day: '2-digit' }).format(
      new Date(),
    )
  } catch {
    return dayjs().format('YYYY-MM-DD') // fuso desconhecido no navegador: usa o local
  }
}

/** "AAAA-MM-DD" + n dias, sem passar por UTC. */
export const somarDias = (data, dias) => lerData(data)?.add(dias, 'day').format('YYYY-MM-DD') ?? null
