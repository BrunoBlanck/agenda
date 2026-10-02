// Catálogos globais mantidos pelo superadmin (estrutura.md, seção 1).

// opcional = o superadmin pode ativar/desativar por loja
export const modulos = [
  { codigo: 'inicio', nome: 'Início', opcional: false },
  { codigo: 'agenda', nome: 'Agenda e agendamentos', opcional: false },
  { codigo: 'clientes', nome: 'Clientes', opcional: false },
  { codigo: 'funcionarios', nome: 'Funcionários', opcional: false },
  { codigo: 'configuracoes', nome: 'Configurações', opcional: false },
  { codigo: 'servicos', nome: 'Serviços', opcional: true },
  { codigo: 'materiais', nome: 'Materiais', opcional: true },
  { codigo: 'controle_tempo', nome: 'Controle de tempo', opcional: true },
  { codigo: 'locais', nome: 'Locais', opcional: true },
]

// Módulos opcionais (os que o superadmin liga e desliga por loja)
export const codigosOpcionais = modulos.filter((m) => m.opcional).map((m) => m.codigo)

// Áreas que recebem nível de acesso (nenhum, leitura, escrita) nos perfis
export const recursos = [
  {
    codigo: 'agenda_propria',
    nome: 'Minha agenda',
    modulo: 'agenda',
    leitura: 'Ver os próprios agendamentos',
    escrita: 'Criar, remarcar, mudar status e cancelar os próprios',
  },
  {
    codigo: 'agenda_equipe',
    nome: 'Agenda da equipe',
    modulo: 'agenda',
    leitura: 'Ver agendamentos de todos',
    escrita: 'Criar, remarcar, mudar status e cancelar de qualquer profissional',
  },
  {
    codigo: 'config_agendamentos',
    nome: 'Horários e bloqueios',
    modulo: 'agenda',
    leitura: 'Ver a jornada dos perfis e os bloqueios',
    escrita: 'Editar a jornada dos perfis, bloqueios, folgas e feriados',
  },
  { codigo: 'clientes', nome: 'Clientes', modulo: 'clientes', leitura: 'Ver lista e ficha', escrita: 'Cadastrar, editar, inativar' },
  {
    codigo: 'funcionarios',
    nome: 'Funcionários',
    modulo: 'funcionarios',
    leitura: 'Ver lista',
    escrita: 'Cadastrar, editar, inativar, definir cargo e perfil',
  },
  {
    codigo: 'perfis_acesso',
    nome: 'Perfis de acesso',
    modulo: 'funcionarios',
    leitura: 'Ver perfis e seus níveis',
    escrita: 'Criar e editar perfis e níveis',
  },
  {
    codigo: 'servicos',
    nome: 'Serviços',
    modulo: 'servicos',
    leitura: 'Ver serviços',
    escrita: 'Cadastrar, editar, vincular profissionais e materiais',
  },
  {
    codigo: 'materiais',
    nome: 'Materiais',
    modulo: 'materiais',
    leitura: 'Ver estoque',
    escrita: 'Cadastrar, editar e ajustar estoque',
  },
  {
    codigo: 'locais',
    nome: 'Locais',
    modulo: 'locais',
    leitura: 'Ver salas, cadeiras, links online...',
    escrita: 'Cadastrar, editar, inativar e definir como a loja chama os locais',
  },
  {
    codigo: 'ponto_proprio',
    nome: 'Meu ponto',
    modulo: 'controle_tempo',
    leitura: 'Ver os próprios registros',
    escrita: 'Registrar entrada e saída',
  },
  {
    codigo: 'ponto_equipe',
    nome: 'Ponto da equipe',
    modulo: 'controle_tempo',
    leitura: 'Ver registros de todos',
    escrita: 'Corrigir registros (com justificativa)',
  },
  {
    codigo: 'config_loja',
    nome: 'Dados da loja',
    modulo: 'configuracoes',
    leitura: 'Ver logo, nome, contato, endereço e CNPJ',
    escrita: 'Editar esses dados',
  },
]

export const niveis = {
  nenhum: { label: 'Nenhum', tom: 'neutro' },
  leitura: { label: 'Leitura', tom: 'tinta' },
  escrita: { label: 'Escrita', tom: 'sucesso' },
}
