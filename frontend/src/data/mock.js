import dayjs from 'dayjs'

const hoje = dayjs().format('YYYY-MM-DD')
const amanha = dayjs().add(1, 'day').format('YYYY-MM-DD')

export const funcionariosIniciais = [
  { id: 1, nome: 'Dra. Ana Souza', cargo: 'Dentista', email: 'ana@clinica.com', telefone: '(11) 99999-0001', ativo: true },
  { id: 2, nome: 'Dr. Carlos Lima', cargo: 'Fisioterapeuta', email: 'carlos@clinica.com', telefone: '(11) 99999-0002', ativo: true },
  { id: 3, nome: 'Juliana Alves', cargo: 'Recepcionista', email: 'juliana@clinica.com', telefone: '(11) 99999-0003', ativo: true },
]

export const clientesIniciais = [
  { id: 1, nome: 'Maria Oliveira', cpf: '123.456.789-00', telefone: '(11) 98888-1111', email: 'maria@email.com', nascimento: '1985-04-12' },
  { id: 2, nome: 'João Pereira', cpf: '987.654.321-00', telefone: '(11) 98888-2222', email: 'joao@email.com', nascimento: '1990-09-30' },
  { id: 3, nome: 'Fernanda Costa', cpf: '111.222.333-44', telefone: '(11) 98888-3333', email: 'fernanda@email.com', nascimento: '1978-01-05' },
]

export const materiaisIniciais = [
  { id: 1, nome: 'Luvas descartáveis (cx)', categoria: 'Descartáveis', quantidade: 25, minimo: 10, unidade: 'cx' },
  { id: 2, nome: 'Máscaras cirúrgicas (cx)', categoria: 'Descartáveis', quantidade: 6, minimo: 10, unidade: 'cx' },
  { id: 3, nome: 'Anestésico local', categoria: 'Medicamentos', quantidade: 40, minimo: 20, unidade: 'un' },
  { id: 4, nome: 'Gaze estéril', categoria: 'Curativos', quantidade: 3, minimo: 15, unidade: 'pct' },
]

// materiais: quantidade de cada material consumida por atendimento
export const servicosIniciais = [
  {
    id: 1,
    nome: 'Limpeza',
    duracao: 60,
    preco: 200,
    funcionarioIds: [1],
    materiais: [{ materialId: 1, quantidade: 1 }, { materialId: 4, quantidade: 2 }],
  },
  {
    id: 2,
    nome: 'Avaliação',
    duracao: 30,
    preco: 100,
    funcionarioIds: [1, 2],
    materiais: [{ materialId: 1, quantidade: 1 }, { materialId: 2, quantidade: 1 }],
  },
  {
    id: 3,
    nome: 'Sessão de fisioterapia',
    duracao: 45,
    preco: 150,
    funcionarioIds: [2],
    materiais: [],
  },
]

export const agendamentosIniciais = [
  { id: 1, clienteId: 1, funcionarioId: 1, data: hoje, hora: '09:00', servicoId: 1, duracao: 60, status: 'confirmado' },
  { id: 2, clienteId: 2, funcionarioId: 2, data: hoje, hora: '10:30', servicoId: 3, duracao: 45, status: 'agendado' },
  { id: 3, clienteId: 3, funcionarioId: 1, data: amanha, hora: '14:00', servicoId: 2, duracao: 30, status: 'agendado' },
]

export const pontosIniciais = [
  { id: 1, funcionarioId: 1, data: hoje, entrada: '08:00', saida: null },
  { id: 2, funcionarioId: 3, data: hoje, entrada: '07:45', saida: null },
  { id: 3, funcionarioId: 2, data: dayjs().subtract(1, 'day').format('YYYY-MM-DD'), entrada: '08:10', saida: '17:05' },
]

export const statusAgendamento = {
  agendado: { label: 'Agendado', color: 'blue' },
  confirmado: { label: 'Confirmado', color: 'green' },
  concluido: { label: 'Concluído', color: 'default' },
  cancelado: { label: 'Cancelado', color: 'red' },
}
