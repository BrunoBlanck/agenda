import dayjs from 'dayjs'

// Dados de exemplo da Plataforma (SUPERADMIN), estrutura.md seção 1.

const diasAtras = (dias) => dayjs().subtract(dias, 'day').toISOString()

export const superadminsIniciais = [
  { id: 1, nome: 'Rafael Mendes', email: 'rafael@agendaplataforma.com', ativo: true, ultimoLoginEm: diasAtras(0) },
  { id: 2, nome: 'Camila Rocha', email: 'camila@agendaplataforma.com', ativo: true, ultimoLoginEm: diasAtras(3) },
]

export const tiposIniciais = [
  { id: 1, codigo: 'clinica', nome: 'Clínica', descricao: 'Clínicas médicas, odontológicas, estética, fisioterapia', ativo: true },
  { id: 2, codigo: 'barbearia', nome: 'Barbearia', descricao: 'Barbearias e salões', ativo: true },
  { id: 3, codigo: 'escola', nome: 'Escola', descricao: 'Escolas de música, idiomas, reforço', ativo: true },
]

// modulos: módulos opcionais sugeridos para a loja ao ser criada com este plano
export const planosIniciais = [
  {
    id: 1,
    nome: 'Básico',
    descricao: 'Agenda, clientes e serviços',
    precoMensal: 89.9,
    limiteFuncionarios: 3,
    limiteAgendamentosMes: 300,
    modulos: ['servicos'],
    ativo: true,
  },
  {
    id: 2,
    nome: 'Profissional',
    descricao: 'Tudo do Básico, mais estoque, controle de ponto e locais',
    precoMensal: 189.9,
    limiteFuncionarios: 15,
    limiteAgendamentosMes: null,
    modulos: ['servicos', 'materiais', 'controle_tempo', 'locais'],
    ativo: true,
  },
  {
    id: 3,
    nome: 'Rede',
    descricao: 'Para redes com várias unidades e equipe grande',
    precoMensal: 449.9,
    limiteFuncionarios: null,
    limiteAgendamentosMes: null,
    modulos: ['servicos', 'materiais', 'controle_tempo', 'locais'],
    ativo: true,
  },
]

// Funcionários das outras lojas (só para a prévia; os da loja 1 estão em mock.js)
const equipe = (...lista) =>
  lista.map(([nome, email, perfil, ativo = true], i) => ({ id: i + 1, nome, email, perfil, ativo }))

// A loja 1 é a "Clínica Sorriso", que é a loja aberta no painel da loja
export const outrasLojas = [
  {
    id: 2,
    tipo: 'barbearia',
    planoId: 1,
    status: 'ativa',
    slug: 'barbearia-navalha',
    nomeFantasia: 'Barbearia Navalha',
    nome: 'Navalha Cortes Masculinos ME',
    cnpj: '',
    email: 'contato@navalha.com',
    telefone: '(19) 3222-1010',
    cidade: 'Campinas',
    uf: 'SP',
    fusoHorario: 'America/Sao_Paulo',
    modulos: { servicos: true, materiais: false, controle_tempo: false, locais: true },
    modulosInfo: { locais: { observacao: 'Cortesia: agenda por cadeira' } },
    rotuloLocal: 'Cadeira',
    rotuloLocalPlural: 'Cadeiras',
    criadoEm: diasAtras(120),
    funcionarios: equipe(['Marcos Silva', 'marcos@navalha.com', 'Administrador'], ['Diego Alves', 'diego@navalha.com', 'Profissional']),
  },
  {
    id: 3,
    tipo: 'escola',
    planoId: 2,
    status: 'ativa',
    slug: 'escola-harmonia',
    nomeFantasia: 'Escola de Música Harmonia',
    nome: 'Harmonia Ensino Musical Ltda',
    cnpj: '',
    email: 'secretaria@harmonia.com',
    telefone: '(31) 3555-2020',
    cidade: 'Belo Horizonte',
    uf: 'MG',
    fusoHorario: 'America/Sao_Paulo',
    modulos: { servicos: true, materiais: false, controle_tempo: true, locais: true },
    modulosInfo: { materiais: { observacao: 'Escola não usa estoque' } },
    rotuloLocal: 'Sala',
    rotuloLocalPlural: 'Salas',
    criadoEm: diasAtras(60),
    funcionarios: equipe(
      ['Paula Antunes', 'paula@harmonia.com', 'Administrador'],
      ['Lucas Prado', 'lucas@harmonia.com', 'Profissional'],
      ['Beatriz Lima', 'beatriz@harmonia.com', 'Profissional'],
      ['Renata Dias', 'renata@harmonia.com', 'Recepção'],
    ),
  },
  {
    id: 4,
    tipo: 'clinica',
    planoId: 1,
    status: 'suspensa',
    slug: 'clinica-bem-estar',
    nomeFantasia: 'Clínica Bem Estar',
    nome: 'Bem Estar Fisioterapia Ltda',
    cnpj: '',
    email: 'contato@bemestar.com',
    telefone: '(21) 3444-3030',
    cidade: 'Rio de Janeiro',
    uf: 'RJ',
    fusoHorario: 'America/Sao_Paulo',
    modulos: { servicos: true, materiais: false, controle_tempo: false, locais: false },
    modulosInfo: {},
    criadoEm: diasAtras(200),
    funcionarios: equipe(['Sérgio Nunes', 'sergio@bemestar.com', 'Administrador']),
  },
  {
    id: 5,
    tipo: 'barbearia',
    planoId: 1,
    status: 'cancelada',
    slug: 'dom-corte',
    nomeFantasia: 'Dom Corte',
    nome: 'Dom Corte Barbearia ME',
    cnpj: '',
    email: 'domcorte@email.com',
    telefone: '(41) 3111-4040',
    cidade: 'Curitiba',
    uf: 'PR',
    fusoHorario: 'America/Sao_Paulo',
    modulos: { servicos: true, materiais: false, controle_tempo: false, locais: false },
    modulosInfo: {},
    criadoEm: diasAtras(400),
    funcionarios: equipe(['Igor Campos', 'igor@domcorte.com', 'Administrador', false]),
  },
]

export const auditoriaInicial = [
  { id: 1, superadminId: 1, lojaId: 3, acao: 'funcionalidade.desativar', dados: { modulo: 'Materiais' }, criadoEm: diasAtras(58) },
  { id: 2, superadminId: 2, lojaId: 4, acao: 'loja.suspender', dados: { motivo: 'Pagamento em atraso' }, criadoEm: diasAtras(10) },
  { id: 3, superadminId: 1, lojaId: 1, acao: 'funcionario.criar', dados: { nome: 'Juliana Alves' }, criadoEm: diasAtras(5) },
  { id: 4, superadminId: 1, lojaId: null, acao: 'tipo_loja.editar', dados: { nome: 'Escola' }, criadoEm: diasAtras(2) },
]

export const statusLoja = {
  ativa: { label: 'Ativa', color: 'green' },
  suspensa: { label: 'Suspensa', color: 'orange' },
  cancelada: { label: 'Cancelada', color: 'red' },
}

export const acoesAuditoria = {
  'loja.criar': { label: 'Criou a loja', color: 'green' },
  'loja.editar': { label: 'Editou dados da loja', color: 'blue' },
  'loja.suspender': { label: 'Suspendeu a loja', color: 'orange' },
  'loja.reativar': { label: 'Reativou a loja', color: 'green' },
  'loja.cancelar': { label: 'Cancelou a loja', color: 'red' },
  'funcionalidade.ativar': { label: 'Ativou módulo', color: 'cyan' },
  'funcionalidade.desativar': { label: 'Desativou módulo', color: 'volcano' },
  'funcionario.criar': { label: 'Criou funcionário', color: 'green' },
  'funcionario.editar': { label: 'Editou funcionário', color: 'blue' },
  'funcionario.senha': { label: 'Redefiniu senha', color: 'purple' },
  'tipo_loja.criar': { label: 'Criou tipo de loja', color: 'green' },
  'tipo_loja.editar': { label: 'Editou tipo de loja', color: 'blue' },
  'plano.criar': { label: 'Criou plano', color: 'green' },
  'plano.editar': { label: 'Editou plano', color: 'blue' },
  'superadmin.criar': { label: 'Criou usuário da plataforma', color: 'green' },
  'superadmin.editar': { label: 'Editou usuário da plataforma', color: 'blue' },
}
