// Catálogos globais (estrutura.md, seção 1). Os recursos com nível de acesso vêm da API (GET /api/loja/recursos);
// aqui ficam só os nomes dos módulos e os rótulos dos níveis para a tela.

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

export const niveis = {
  nenhum: { label: 'Nenhum', tom: 'neutro' },
  leitura: { label: 'Leitura', tom: 'tinta' },
  escrita: { label: 'Escrita', tom: 'sucesso' },
}
