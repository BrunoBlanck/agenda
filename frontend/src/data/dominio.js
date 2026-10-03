// Valores fixos do domínio (enums do banco) com o rótulo e o tom de cada um na tela (INT-14).
// Valor desconhecido vindo da API não quebra: quem usa cai num rótulo neutro.

// Por onde o cliente fala com a loja (pode ser mais de um)
export const canaisCliente = {
  loja: 'Loja (presencial)',
  whatsapp: 'WhatsApp',
  site: 'Site',
}

// tom: cor semântica da etiqueta (components/Etiquetas.jsx)
export const tiposLocal = {
  presencial: { label: 'Presencial', tom: 'contorno' },
  online: { label: 'Online', tom: 'tinta' },
}

export const statusAgendamento = {
  pendente: { label: 'Aguardando aceite', tom: 'marca' },
  agendado: { label: 'Agendado', tom: 'tinta' },
  confirmado: { label: 'Confirmado', tom: 'sucesso' },
  concluido: { label: 'Concluído', tom: 'neutro' },
  cancelado: { label: 'Cancelado', tom: 'perigo' },
  nao_compareceu: { label: 'Não compareceu', tom: 'atencao' },
}

// Tipo da loja: constante do sistema (no banco, enum tipo_loja). Cada tipo tem o próprio site do
// consumidor final (layout, textos e fluxo), por isso um tipo novo só entra junto com código novo.
export const tiposLoja = {
  clinica: { nome: 'Clínica', descricao: 'Clínicas médicas, odontológicas, estética, fisioterapia' },
  barbearia: { nome: 'Barbearia', descricao: 'Barbearias e salões' },
  escola: { nome: 'Escola', descricao: 'Escolas de música, idiomas, reforço' },
}

export const opcoesTipoLoja = Object.entries(tiposLoja).map(([value, t]) => ({ value, label: t.nome }))

export const statusLoja = {
  ativa: { label: 'Ativa', tom: 'sucesso' },
  suspensa: { label: 'Suspensa', tom: 'atencao' },
  cancelada: { label: 'Cancelada', tom: 'perigo' },
}

export const operacoesHistorico = {
  inserir: { label: 'Inclusão', tom: 'sucesso' },
  alterar: { label: 'Alteração', tom: 'tinta' },
  excluir: { label: 'Exclusão', tom: 'perigo' },
  restaurar: { label: 'Restauração', tom: 'atencao' },
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
