import dayjs from 'dayjs'

// Dados de exemplo da Plataforma (SUPERADMIN), estrutura.md seção 1.

const diasAtras = (dias) => dayjs().subtract(dias, 'day').toISOString()

export const superadminsIniciais = [
  { id: 1, nome: 'Rafael Mendes', email: 'rafael@agendaplataforma.com', ativo: true, ultimoLoginEm: diasAtras(0) },
  { id: 2, nome: 'Camila Rocha', email: 'camila@agendaplataforma.com', ativo: true, ultimoLoginEm: diasAtras(3) },
]

// Tipo da loja: constante do sistema (no banco, enum tipo_loja). Cada tipo tem o próprio site do
// consumidor final (layout, textos e fluxo), por isso um tipo novo só entra junto com código novo.
export const tiposLoja = {
  clinica: { nome: 'Clínica', descricao: 'Clínicas médicas, odontológicas, estética, fisioterapia' },
  barbearia: { nome: 'Barbearia', descricao: 'Barbearias e salões' },
  escola: { nome: 'Escola', descricao: 'Escolas de música, idiomas, reforço' },
}

export const opcoesTipoLoja = Object.entries(tiposLoja).map(([value, t]) => ({ value, label: t.nome }))

// Plano é só comercial (nome e preço). Não define nem limita os módulos da loja:
// isso é escolhido loja a loja, para esconder o que a loja não usa.
export const planosIniciais = [
  { id: 1, nome: 'Básico', descricao: 'Para quem está começando', precoMensal: 89.9, ativo: true },
  { id: 2, nome: 'Profissional', descricao: 'Equipes de até 15 pessoas', precoMensal: 189.9, ativo: true },
  { id: 3, nome: 'Rede', descricao: 'Para redes com várias unidades e equipe grande', precoMensal: 449.9, ativo: true },
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

// Histórico de alterações (no banco: auditoria, uma linha por inserção, alteração ou exclusão).
// quem: { f: id do funcionário da loja } | { s: id do superadmin } | 'site'
const horasAtras = (horas) => dayjs().subtract(horas, 'hour').toISOString()
const registro = (horas, lojaId, tabela, operacao, antes, depois, quem) => ({
  lojaId,
  tabela,
  registroId: (depois ?? antes).id ?? (depois ?? antes).codigo,
  operacao,
  antes,
  depois,
  funcionarioId: quem.f ?? null,
  superadminId: quem.s ?? null,
  site: quem === 'site',
  criadoEm: horasAtras(horas),
})

export const historicoInicial = [
  registro(24 * 100, null, 'superadmin_usuarios', 'inserir', null, { id: 2, nome: 'Camila Rocha', email: 'camila@agendaplataforma.com', ativo: true }, { s: 1 }),
  registro(24 * 90, 1, 'lojas', 'inserir', null, { id: 1, nomeFantasia: 'Clínica Sorriso', slug: 'clinica-sorriso', tipo: 'clinica', planoId: 2, status: 'ativa' }, { s: 1 }),
  registro(24 * 58, 3, 'loja_funcionalidades', 'alterar', { codigo: 'materiais', ativo: true }, { codigo: 'materiais', ativo: false, observacao: 'Escola não usa estoque' }, { s: 1 }),
  registro(24 * 30, 1, 'loja_funcionalidades', 'alterar', { codigo: 'locais', ativo: false }, { codigo: 'locais', ativo: true }, { s: 2 }),
  registro(24 * 20, 1, 'clientes', 'inserir', null, { id: 1, nome: 'Maria', sobrenome: 'Oliveira', telefone: '(11) 98888-1111', canais: ['loja'] }, { f: 1 }),
  registro(24 * 15, null, 'planos', 'alterar', { id: 2, nome: 'Profissional', precoMensal: 179.9 }, { id: 2, nome: 'Profissional', precoMensal: 189.9 }, { s: 1 }),
  registro(24 * 10, 4, 'lojas', 'alterar', { id: 4, nomeFantasia: 'Clínica Bem Estar', status: 'ativa' }, { id: 4, nomeFantasia: 'Clínica Bem Estar', status: 'suspensa' }, { s: 2 }),
  registro(24 * 7, 2, 'servicos', 'inserir', null, { id: 3, nome: 'Corte + barba', duracao: 50, preco: 70 }, { f: 1 }),
  registro(24 * 6, 1, 'clientes', 'alterar', { id: 2, nome: 'João', sobrenome: 'Pereira', telefone: '(11) 97777-0000' }, { id: 2, nome: 'João', sobrenome: 'Pereira', telefone: '(11) 98888-2222' }, { f: 3 }),
  registro(24 * 5, 1, 'funcionarios', 'inserir', null, { id: 3, nome: 'Juliana Alves', email: 'juliana@clinica.com', perfil: 'Recepção', ativo: true }, { s: 1 }),
  registro(24 * 4, 3, 'clientes', 'inserir', null, { id: 7, nome: 'Pedro', sobrenome: 'Santos', telefone: '(31) 98888-5555' }, { f: 4 }),
  registro(24 * 3, 1, 'materiais', 'alterar', { id: 2, nome: 'Máscaras cirúrgicas (cx)', quantidade: 12 }, { id: 2, nome: 'Máscaras cirúrgicas (cx)', quantidade: 6 }, { f: 1 }),
  registro(24 * 2, 1, 'materiais', 'excluir', { id: 99, nome: 'Algodão (pct)', quantidade: 0, unidade: 'pct' }, { id: 99, nome: 'Algodão (pct)', quantidade: 0, unidade: 'pct', excluidoEm: horasAtras(48), excluidoPor: 1 }, { f: 1 }),
  registro(24 * 2, 3, 'locais', 'alterar', { id: 1, nome: 'Sala 101', descricao: 'Piano vertical' }, { id: 1, nome: 'Sala 101', descricao: 'Piano de cauda, isolamento acústico' }, { f: 1 }),
  registro(26, 1, 'agendamentos', 'alterar', { id: 3, data: dayjs().add(1, 'day').format('YYYY-MM-DD'), hora: '11:00' }, { id: 3, data: dayjs().add(1, 'day').format('YYYY-MM-DD'), hora: '14:00' }, { f: 3 }),
  registro(20, 1, 'agendamentos', 'inserir', null, { id: 10, data: dayjs().add(1, 'day').format('YYYY-MM-DD'), hora: '09:00', status: 'pendente', origem: 'site' }, 'site'),
  registro(18, 3, 'agendamentos', 'excluir', { id: 31, data: dayjs().format('YYYY-MM-DD'), hora: '15:00', status: 'agendado' }, { id: 31, data: dayjs().format('YYYY-MM-DD'), hora: '15:00', status: 'agendado', excluidoEm: horasAtras(18), excluidoPor: 4 }, { f: 4 }),
  registro(3, 1, 'agendamentos', 'alterar', { id: 1, data: dayjs().format('YYYY-MM-DD'), hora: '09:00', status: 'agendado' }, { id: 1, data: dayjs().format('YYYY-MM-DD'), hora: '09:00', status: 'confirmado' }, { f: 3 }),
].map((r, i) => ({ ...r, id: i + 1 }))

export const statusLoja = {
  ativa: { label: 'Ativa', color: 'green' },
  suspensa: { label: 'Suspensa', color: 'orange' },
  cancelada: { label: 'Cancelada', color: 'red' },
}

export const operacoesHistorico = {
  inserir: { label: 'Inclusão', color: 'green' },
  alterar: { label: 'Alteração', color: 'blue' },
  excluir: { label: 'Exclusão', color: 'red' },
}

// Tabelas que podem ser consultadas na auditoria
export const tabelasLoja = {
  agendamentos: 'Agendamentos',
  clientes: 'Clientes',
  funcionarios: 'Funcionários',
  servicos: 'Serviços',
  materiais: 'Materiais',
  locais: 'Locais',
  registros_ponto: 'Controle de tempo',
  perfis: 'Perfis de acesso',
  perfil_horarios: 'Jornadas dos perfis',
  bloqueios_agenda: 'Bloqueios da agenda',
  lojas: 'Dados da loja',
  loja_funcionalidades: 'Módulos da loja',
}

// Valor usado no lugar do id da loja para ver as tabelas da própria plataforma
export const PLATAFORMA = 'plataforma'

export const tabelasPlataforma = {
  planos: 'Planos',
  superadmin_usuarios: 'Usuários admin',
}
