import dayjs from 'dayjs'

const hoje = dayjs().format('YYYY-MM-DD')
const amanha = dayjs().add(1, 'day').format('YYYY-MM-DD')
const diaRelativo = (dias) => dayjs().add(dias, 'day').format('YYYY-MM-DD')

// Loja aberta no painel da loja. tipo, slug, plano, status, fuso e módulos só o superadmin altera.
export const lojaInicial = {
  id: 1,
  tipo: 'clinica',
  slug: 'clinica-sorriso',
  planoId: 2,
  status: 'ativa',
  fusoHorario: 'America/Sao_Paulo',
  logoUrl: null,
  nomeFantasia: 'Clínica Sorriso',
  nome: 'Clínica Sorriso Serviços Odontológicos Ltda',
  cnpj: '11.222.333/0001-81',
  telefone: '(11) 3333-4444',
  email: 'contato@clinicasorriso.com',
  cep: '01310-100',
  logradouro: 'Avenida Paulista',
  numero: '1000',
  complemento: 'Sala 52',
  bairro: 'Bela Vista',
  cidade: 'São Paulo',
  uf: 'SP',
  // Módulos opcionais ativados pelo superadmin (loja_funcionalidades)
  modulos: { servicos: true, materiais: true, controle_tempo: true, locais: true },
  modulosInfo: {},
  // Como a loja chama os locais na tela (Sala, Cadeira, Maca, Consultório...)
  rotuloLocal: 'Consultório',
  rotuloLocalPlural: 'Consultórios',
  criadoEm: dayjs().subtract(90, 'day').toISOString(),
}

// acessos: nível por recurso. Recurso ausente = nenhum.
export const perfisIniciais = [
  {
    id: 1,
    nome: 'Administrador',
    descricao: 'Escrita em tudo o que estiver ativo na loja',
    padrao: true,
    acessoTotal: true,
    acessos: {},
  },
  {
    id: 2,
    nome: 'Recepção',
    descricao: 'Agenda de todos os profissionais, clientes e o próprio ponto',
    padrao: true,
    acessos: {
      agenda_propria: 'escrita',
      agenda_equipe: 'escrita',
      config_agendamentos: 'leitura',
      clientes: 'escrita',
      servicos: 'leitura',
      locais: 'leitura',
      ponto_proprio: 'escrita',
    },
  },
  {
    id: 3,
    nome: 'Profissional',
    descricao: 'Apenas a própria agenda, consulta de clientes e o próprio ponto',
    padrao: true,
    acessos: { agenda_propria: 'escrita', clientes: 'leitura', ponto_proprio: 'escrita' },
  },
]

export const funcionariosIniciais = [
  { id: 1, nome: 'Dra. Ana Souza', cor: '#0f766e', cargo: 'Dentista', perfilId: 1, email: 'ana@clinica.com', telefone: '(11) 99999-0001', ativo: true },
  { id: 2, nome: 'Dr. Carlos Lima', cor: '#2563eb', cargo: 'Fisioterapeuta', perfilId: 3, email: 'carlos@clinica.com', telefone: '(11) 99999-0002', ativo: true },
  { id: 3, nome: 'Juliana Alves', cor: '#d97706', cargo: 'Recepcionista', perfilId: 2, email: 'juliana@clinica.com', telefone: '(11) 99999-0003', ativo: true },
]

// Jornada semanal (diaSemana: 0 = domingo ... 6 = sábado)
const faixas = (funcionarioId, dias, lista) =>
  dias.flatMap((diaSemana) => lista.map(([inicio, fim]) => ({ funcionarioId, diaSemana, inicio, fim })))

export const jornadasIniciais = [
  ...faixas(1, [1, 2, 3, 4, 5], [['08:00', '12:00'], ['13:00', '18:00']]),
  ...faixas(2, [1, 2, 3, 4, 5], [['09:00', '17:00']]),
  ...faixas(2, [6], [['08:00', '12:00']]),
  ...faixas(3, [1, 2, 3, 4, 5, 6], [['07:30', '17:00']]),
].map((j, i) => ({ ...j, id: i + 1 }))

// funcionarioId null = bloqueio da loja inteira (ex.: feriado)
const proximaSegunda = dayjs().day(8).format('YYYY-MM-DD')
export const bloqueiosIniciais = [
  { id: 1, funcionarioId: null, inicio: `${proximaSegunda} 00:00`, fim: `${proximaSegunda} 23:59`, motivo: 'Feriado' },
  { id: 2, funcionarioId: 2, inicio: `${amanha} 15:00`, fim: `${amanha} 17:00`, motivo: 'Consulta médica' },
]

export const clientesIniciais = [
  { id: 1, nome: 'Maria Oliveira', cpf: '123.456.789-00', telefone: '(11) 98888-1111', email: 'maria@email.com', nascimento: '1985-04-12', canais: ['loja', 'whatsapp'] },
  { id: 2, nome: 'João Pereira', cpf: '987.654.321-00', telefone: '(11) 98888-2222', email: 'joao@email.com', nascimento: '1990-09-30', canais: ['whatsapp'] },
  { id: 3, nome: 'Fernanda Costa', cpf: '111.222.333-44', telefone: '(11) 98888-3333', email: 'fernanda@email.com', nascimento: '1978-01-05', canais: ['loja', 'site'] },
]

export const materiaisIniciais = [
  { id: 1, nome: 'Luvas descartáveis (cx)', categoria: 'Descartáveis', quantidade: 25, minimo: 10, unidade: 'cx' },
  { id: 2, nome: 'Máscaras cirúrgicas (cx)', categoria: 'Descartáveis', quantidade: 6, minimo: 10, unidade: 'cx' },
  { id: 3, nome: 'Anestésico local', categoria: 'Medicamentos', quantidade: 40, minimo: 20, unidade: 'un' },
  { id: 4, nome: 'Gaze estéril', categoria: 'Curativos', quantidade: 3, minimo: 15, unidade: 'pct' },
]

// Onde o atendimento acontece (estrutura.md, 2.19). tipo: presencial ou online
export const locaisIniciais = [
  { id: 1, nome: 'Consultório 1', tipo: 'presencial', descricao: 'Cadeira odontológica e raio-x', ativo: true },
  { id: 2, nome: 'Consultório 2', tipo: 'presencial', descricao: 'Cadeira odontológica', ativo: true },
  { id: 3, nome: 'Sala de fisioterapia', tipo: 'presencial', descricao: 'Macas e aparelhos', ativo: true },
  { id: 4, nome: 'Online · Dr. Carlos', tipo: 'online', linkPadrao: 'https://meet.google.com/abc-defg-hij', ativo: true },
]

// materiais: quantidade de cada material consumida por atendimento
// localIds: onde o serviço pode acontecer. Vazio = qualquer local ativo
export const servicosIniciais = [
  {
    id: 1,
    nome: 'Limpeza',
    duracao: 60,
    preco: 200,
    funcionarioIds: [1],
    materiais: [{ materialId: 1, quantidade: 1 }, { materialId: 4, quantidade: 2 }],
    localIds: [1, 2],
  },
  {
    id: 2,
    nome: 'Avaliação',
    duracao: 30,
    preco: 100,
    funcionarioIds: [1, 2],
    materiais: [{ materialId: 1, quantidade: 1 }, { materialId: 2, quantidade: 1 }],
    localIds: [],
  },
  {
    id: 3,
    nome: 'Sessão de fisioterapia',
    duracao: 45,
    preco: 150,
    funcionarioIds: [2],
    materiais: [],
    localIds: [3, 4],
  },
]

export const agendamentosIniciais = [
  { id: 1, clienteId: 1, funcionarioId: 1, localId: 1, data: hoje, hora: '09:00', servicoId: 1, duracao: 60, preco: 200, status: 'confirmado' },
  { id: 2, clienteId: 2, funcionarioId: 2, localId: 3, data: hoje, hora: '10:30', servicoId: 3, duracao: 45, preco: 150, status: 'agendado' },
  { id: 3, clienteId: 3, funcionarioId: 1, localId: 2, data: amanha, hora: '14:00', servicoId: 2, duracao: 30, preco: 100, status: 'agendado' },
  { id: 4, clienteId: 2, funcionarioId: 1, localId: 2, data: hoje, hora: '09:30', servicoId: 2, duracao: 30, preco: 100, status: 'agendado' },
  { id: 5, clienteId: 3, funcionarioId: 2, localId: 4, data: hoje, hora: '14:00', servicoId: 3, duracao: 45, preco: 150, status: 'confirmado' },
  { id: 6, clienteId: 1, funcionarioId: 2, localId: 3, data: diaRelativo(-1), hora: '11:00', servicoId: 3, duracao: 45, preco: 150, status: 'concluido' },
  { id: 7, clienteId: 2, funcionarioId: 1, localId: 1, data: diaRelativo(-1), hora: '16:00', servicoId: 1, duracao: 60, preco: 200, status: 'nao_compareceu' },
  { id: 8, clienteId: 3, funcionarioId: 1, localId: 1, data: diaRelativo(2), hora: '08:30', servicoId: 1, duracao: 60, preco: 200, status: 'agendado' },
  { id: 9, clienteId: 1, funcionarioId: 2, localId: 2, data: diaRelativo(2), hora: '10:00', servicoId: 2, duracao: 30, preco: 100, status: 'cancelado' },
  // Solicitado pelo site, aguardando a loja aceitar
  { id: 10, clienteId: 3, funcionarioId: 2, localId: 2, data: amanha, hora: '09:00', servicoId: 2, duracao: 30, preco: 100, status: 'pendente', origem: 'site' },
]

export const pontosIniciais = [
  { id: 1, funcionarioId: 1, data: hoje, entrada: '08:00', saida: null },
  { id: 2, funcionarioId: 3, data: hoje, entrada: '07:45', saida: null },
  { id: 3, funcionarioId: 2, data: dayjs().subtract(1, 'day').format('YYYY-MM-DD'), entrada: '08:10', saida: '17:05' },
]

// Por onde o cliente fala com a loja (pode ser mais de um)
export const canaisCliente = {
  loja: 'Loja (presencial)',
  whatsapp: 'WhatsApp',
  site: 'Site',
}

export const tiposLocal = {
  presencial: { label: 'Presencial', color: 'default' },
  online: { label: 'Online', color: 'purple' },
}

export const statusAgendamento = {
  pendente: { label: 'Aguardando aceite', color: 'gold' },
  agendado: { label: 'Agendado', color: 'blue' },
  confirmado: { label: 'Confirmado', color: 'green' },
  concluido: { label: 'Concluído', color: 'default' },
  cancelado: { label: 'Cancelado', color: 'red' },
  nao_compareceu: { label: 'Não compareceu', color: 'orange' },
}
