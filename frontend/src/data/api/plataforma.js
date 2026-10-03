import { api, ErroApi, urlDaApi } from './cliente.js'
import { enviarDataHora, enviarNumero, lerNumero, lerPagina, paraCamel, textoOuNulo } from './conversao.js'
import { conflitoNoCampo } from './registro.js'

// Plataforma (SUPERADMIN): lojas, módulos, funcionários pelo suporte, planos, usuários admin, auditoria
// e visão geral. Funções puras: chamam a API e convertem com mapeamento explícito por campo (INT-09).
// Ids são uuid (string). Datas chegam no fuso da loja (ou da plataforma) e são mostradas como vieram.

const sa = api.superadmin
const id = (valor) => encodeURIComponent(String(valor))
const lista = (valor) => (Array.isArray(valor) ? valor : [])

// --- Visão geral --------------------------------------------------------------------------------

export async function obterVisaoGeral(sinal) {
  const d = (await sa.get('/visao-geral', { sinal })) ?? {}
  return {
    lojasAtivas: lerNumero(d.lojas_ativas) ?? 0,
    lojasSuspensas: lerNumero(d.lojas_suspensas) ?? 0,
    lojasCanceladas: lerNumero(d.lojas_canceladas) ?? 0,
    funcionariosAtivos: lerNumero(d.funcionarios_ativos) ?? 0,
    receitaMensal: lerNumero(d.receita_mensal) ?? 0,
    // { clinica: { ativa: 1, suspensa: 0, cancelada: 0 }, ... } (chaves são códigos: ficam como vieram)
    lojasPorTipo: d.lojas_por_tipo && typeof d.lojas_por_tipo === 'object' ? d.lojas_por_tipo : {},
    modulosEmUso: lista(d.modulos_em_uso).map((m) => ({
      codigo: m.codigo,
      nome: m.nome ?? m.codigo,
      lojas: lerNumero(m.lojas) ?? 0,
    })),
    modulosExpirando: lista(d.modulos_expirando).map((m) => ({
      lojaId: m.loja_id,
      lojaNome: m.loja_nome ?? '—',
      codigo: m.codigo,
      nome: m.nome ?? m.codigo,
      expiraEm: m.expira_em ?? null,
      vencido: !!m.vencido,
    })),
    ultimasAcoes: lista(d.ultimas_acoes).map((a) => ({
      id: a.id,
      criadoEm: a.criado_em ?? null,
      tabela: a.tabela,
      tabelaNome: a.tabela_nome ?? a.tabela,
      operacao: a.operacao,
      superadminId: a.superadmin_id ?? null,
      superadminNome: a.superadmin_nome ?? null,
      lojaId: a.loja_id ?? null,
      lojaNome: a.loja_nome ?? null,
    })),
  }
}

// --- Lojas ---------------------------------------------------------------------------------------

// Resumo (lista) e detalhe. modulos é um mapa por código (controle_tempo): fica como veio.
// nome_fantasia pode vir null em loja antiga: a tela usa a razão social no lugar.
export function lerLoja(d) {
  const l = paraCamel(d ?? {}, ['modulos'])
  return {
    ...l,
    nomeFantasia: d?.nome_fantasia || d?.nome || '',
    logoUrl: urlDaApi(d?.logo_url),
    modulos: d?.modulos && typeof d.modulos === 'object' ? d.modulos : {},
    funcionariosAtivos: lerNumero(d?.funcionarios_ativos) ?? 0,
  }
}

export async function listarLojas({ busca, tipo, status, pagina = 1, porPagina = 20 } = {}, sinal) {
  const dados = await sa.get('/lojas', {
    query: { busca: busca?.trim() || undefined, tipo, status, pagina, por_pagina: porPagina },
    sinal,
  })
  return lerPagina(dados, lerLoja)
}

export async function listarOpcoesLojas(sinal) {
  return lista(await sa.get('/lojas/opcoes', { sinal })).map((l) => ({
    id: l.id,
    nome: l.nome_fantasia || l.nome || l.slug,
    slug: l.slug,
    status: l.status,
  }))
}

export const obterLoja = async (lojaId, sinal) => lerLoja(await sa.get(`/lojas/${id(lojaId)}`, { sinal }))

// Campos de LojaEntrada (dados da loja + tipo, slug, plano e fuso). Todos vão no PUT: o que faltar vira vazio.
function corpoLoja(v) {
  return {
    nome_fantasia: v.nomeFantasia?.trim(),
    nome: v.nome?.trim(),
    cnpj: textoOuNulo(v.cnpj),
    telefone: textoOuNulo(v.telefone),
    email: textoOuNulo(v.email),
    cep: textoOuNulo(v.cep),
    logradouro: textoOuNulo(v.logradouro),
    numero: textoOuNulo(v.numero),
    complemento: textoOuNulo(v.complemento),
    bairro: textoOuNulo(v.bairro),
    cidade: textoOuNulo(v.cidade),
    uf: textoOuNulo(v.uf),
    tipo: v.tipo,
    slug: v.slug?.trim(),
    plano_id: v.planoId,
    ...(v.fusoHorario && { fuso_horario: v.fusoHorario }),
  }
}

/** Nova loja com os módulos escolhidos e o primeiro Administrador. senhaProvisoria só quando foi gerada. */
export async function criarLoja(v) {
  const d = await sa.post('/lojas', {
    ...corpoLoja(v),
    modulos: lista(v.modulos),
    admin: { nome: v.admin?.nome?.trim(), email: v.admin?.email?.trim(), senha: textoOuNulo(v.admin?.senha) },
  })
  return {
    loja: lerLoja(d),
    admin: lerFuncionario(d?.admin),
    senhaProvisoria: d?.senha_provisoria ?? null,
  }
}

export const salvarLoja = async (lojaId, v) => lerLoja(await sa.put(`/lojas/${id(lojaId)}`, corpoLoja(v)))

export const mudarStatusLoja = async (lojaId, status) =>
  lerLoja(await sa.post(`/lojas/${id(lojaId)}/status`, { status }))

export const excluirLoja = (lojaId) => sa.delete(`/lojas/${id(lojaId)}`)

/** Logo da loja: multipart, campo "arquivo" (PNG, JPEG ou WebP, até 2 MB). Resolve com o detalhe da loja. */
export async function enviarLogoDaLoja(lojaId, arquivo) {
  const corpo = new FormData()
  corpo.append('arquivo', arquivo)
  return lerLoja(await sa.put(`/lojas/${id(lojaId)}/logo`, corpo))
}

export const removerLogoDaLoja = (lojaId) => sa.delete(`/lojas/${id(lojaId)}/logo`)

// Acessar loja (PLA-17): sessão de 1 hora no painel como o Administrador da loja. Sem corpo.
// O token só passa por aqui e pelo sessionStorage da aba nova (nunca na URL, em log nem em mensagem: INT-06).
export async function gerarAcessoLoja(lojaId) {
  const d = (await sa.post(`/lojas/${id(lojaId)}/acesso`)) ?? {}
  // Sem token ou sem slug não há aonde ir: vira erro tratado, não uma aba em /undefined/painel
  if (typeof d.token !== 'string' || !d.token || typeof d.slug !== 'string' || !d.slug) {
    throw new ErroApi({ status: 500, mensagem: 'Não foi possível gerar o acesso à loja. Tente novamente em instantes.' })
  }
  return {
    token: d.token,
    expiraEm: d.expira_em ?? null,
    slug: d.slug,
    funcionarioNome: d.funcionario_nome ?? '',
  }
}

// --- Módulos da loja -----------------------------------------------------------------------------

const lerModulo = (m) => ({
  codigo: m.codigo,
  nome: m.nome ?? m.codigo,
  descricao: m.descricao ?? null,
  opcional: !!m.opcional,
  habilitado: !!m.habilitado,
  ativo: !!m.ativo,
  observacao: m.observacao ?? null,
  expiraEm: m.expira_em ?? null,
  atualizadoEm: m.atualizado_em ?? null,
  atualizadoPorNome: m.atualizado_por_nome ?? null,
})

export const listarModulosLoja = async (lojaId, sinal) =>
  lista(await sa.get(`/lojas/${id(lojaId)}/modulos`, { sinal })).map(lerModulo)

/** Só o campo alterado: { habilitado } | { observacao } | { expiraEm } (null = sem prazo). */
export async function definirModuloLoja(lojaId, codigo, campos) {
  const corpo = {}
  if ('habilitado' in campos) corpo.habilitado = !!campos.habilitado
  if ('observacao' in campos) corpo.observacao = textoOuNulo(campos.observacao)
  if ('expiraEm' in campos) corpo.expira_em = enviarDataHora(campos.expiraEm)
  return lerModulo(await sa.patch(`/lojas/${id(lojaId)}/modulos/${id(codigo)}`, corpo))
}

// --- Funcionários pelo suporte -------------------------------------------------------------------

export function lerFuncionario(f) {
  if (!f) return null
  return {
    id: f.id,
    nome: f.nome ?? '',
    email: f.email ?? '',
    perfilId: f.perfil_id ?? null,
    perfilNome: f.perfil_nome ?? null,
    perfilAcessoTotal: !!f.perfil_acesso_total,
    telefone: f.telefone ?? null,
    ativo: !!f.ativo,
    ultimoLoginEm: f.ultimo_login_em ?? null,
    criadoPor: f.criado_por ?? null, // 'loja' | 'superadmin' | null
    criadoEm: f.criado_em ?? null,
    atualizadoEm: f.atualizado_em ?? null,
  }
}

export const listarPerfisLoja = async (lojaId, sinal) =>
  lista(await sa.get(`/lojas/${id(lojaId)}/perfis`, { sinal })).map((p) => ({
    id: p.id,
    nome: p.nome,
    acessoTotal: !!p.acesso_total,
  }))

export const listarFuncionariosLoja = async (lojaId, sinal) =>
  lista(await sa.get(`/lojas/${id(lojaId)}/funcionarios`, { sinal })).map(lerFuncionario)

/** Cria (sem funcionarioId) ou edita. Na criação, senhaProvisoria vem quando a senha foi gerada. */
export async function salvarFuncionarioLoja(lojaId, v, funcionarioId) {
  const corpo = {
    nome: v.nome?.trim(),
    email: v.email?.trim(),
    perfil_id: v.perfilId,
    telefone: textoOuNulo(v.telefone),
    ativo: v.ativo ?? true,
  }
  if (funcionarioId) {
    return { funcionario: lerFuncionario(await sa.put(`/lojas/${id(lojaId)}/funcionarios/${id(funcionarioId)}`, corpo)) }
  }
  const d = await sa.post(`/lojas/${id(lojaId)}/funcionarios`, { ...corpo, senha: textoOuNulo(v.senha) })
  return { funcionario: lerFuncionario(d), senhaProvisoria: d?.senha_provisoria ?? null }
}

/** Troca a senha na hora: a informada ou uma provisória gerada (devolvida uma vez). */
export async function redefinirSenhaFuncionario(lojaId, funcionarioId, senha) {
  const d = await sa.post(`/lojas/${id(lojaId)}/funcionarios/${id(funcionarioId)}/redefinir-senha`, {
    senha: textoOuNulo(senha),
  })
  return { mensagem: d?.mensagem ?? 'Senha redefinida.', senhaProvisoria: d?.senha_provisoria ?? null }
}

// --- Planos --------------------------------------------------------------------------------------

const lerPlano = (p) => ({
  id: p.id,
  nome: p.nome ?? '',
  descricao: p.descricao ?? null,
  precoMensal: lerNumero(p.preco_mensal) ?? 0,
  ativo: !!p.ativo,
  lojasAtivas: lerNumero(p.lojas_ativas) ?? 0,
  criadoEm: p.criado_em ?? null,
  atualizadoEm: p.atualizado_em ?? null,
})

export const listarPlanos = async (sinal) => lista(await sa.get('/planos', { sinal })).map(lerPlano)

export const obterPlano = async (planoId, sinal) => lerPlano(await sa.get(`/planos/${id(planoId)}`, { sinal }))

// 409 de unicidade (backend/app/erros.py, planos_nome_uk): ao lado do campo
const CONFLITOS_PLANO = [['plano com este nome', 'nome']]

export async function salvarPlano(v, planoId) {
  const corpo = {
    nome: v.nome?.trim(),
    descricao: textoOuNulo(v.descricao),
    preco_mensal: enviarNumero(v.precoMensal),
    ativo: v.ativo ?? true,
  }
  try {
    return lerPlano(planoId ? await sa.put(`/planos/${id(planoId)}`, corpo) : await sa.post('/planos', corpo))
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITOS_PLANO)
  }
}

export const excluirPlano = (planoId) => sa.delete(`/planos/${id(planoId)}`)

// --- Usuários admin ------------------------------------------------------------------------------

const lerUsuario = (u) => ({
  id: u.id,
  nome: u.nome ?? '',
  email: u.email ?? '',
  ativo: !!u.ativo,
  ultimoLoginEm: u.ultimo_login_em ?? null,
  criadoEm: u.criado_em ?? null,
  atualizadoEm: u.atualizado_em ?? null,
  voce: !!u.voce,
})

export const listarUsuarios = async (sinal) => lista(await sa.get('/usuarios', { sinal })).map(lerUsuario)

export const obterUsuario = async (usuarioId, sinal) => lerUsuario(await sa.get(`/usuarios/${id(usuarioId)}`, { sinal }))

// 409 que tem campo no formulário (backend/app/erros.py superadmin_usuarios_email_uk e routers/superadmin/usuarios.py)
const CONFLITOS_USUARIO = [
  ['usuário admin com este e-mail', 'email'],
  ['não pode desativar o seu próprio usuário', 'ativo'],
  ['pelo menos um usuário admin ativo', 'ativo'],
]

/** Senha: no cadastro, vazia = provisória gerada (senhaProvisoria); na edição, só se for trocar. */
export async function salvarUsuario(v, usuarioId) {
  const corpo = { nome: v.nome?.trim(), email: v.email?.trim(), ativo: v.ativo ?? true, senha: textoOuNulo(v.senha) }
  try {
    const d = usuarioId ? await sa.put(`/usuarios/${id(usuarioId)}`, corpo) : await sa.post('/usuarios', corpo)
    return { usuario: lerUsuario(d), senhaProvisoria: d?.senha_provisoria ?? null }
  } catch (erro) {
    throw conflitoNoCampo(erro, CONFLITOS_USUARIO)
  }
}

export const excluirUsuario = (usuarioId) => sa.delete(`/usuarios/${id(usuarioId)}`)

// --- Auditoria -----------------------------------------------------------------------------------

export async function listarTabelasAuditoria(sinal) {
  const d = (await sa.get('/auditoria/tabelas', { sinal })) ?? {}
  const objeto = (v) => (v && typeof v === 'object' ? v : {})
  return { loja: objeto(d.loja), plataforma: objeto(d.plataforma) }
}

// filtros: { loja: uuid | 'plataforma', tabela?, periodo: 'hoje'|'7d'|'30d'|'90d'|'ano'|'intervalo', inicio?, fim?, quem? }
const queryAuditoria = ({ loja, tabela, periodo, inicio, fim }) => ({
  loja,
  tabela: tabela || undefined,
  periodo,
  ...(periodo === 'intervalo' && { inicio, fim }),
})

const lerQuem = (q) => ({
  tipo: q?.tipo ?? 'sistema',
  id: q?.id ?? null,
  nome: q?.nome ?? '—',
  chave: q?.chave ?? '',
})

// antes/depois são a linha do banco (chaves snake_case): ficam como vieram
const lerItemAuditoria = (d) => ({
  id: d.id,
  criadoEm: d.criado_em ?? null,
  lojaId: d.loja_id ?? null,
  tabela: d.tabela,
  tabelaNome: d.tabela_nome ?? d.tabela,
  registroId: d.registro_id != null ? String(d.registro_id) : '',
  rotulo: d.rotulo || null,
  operacao: d.operacao,
  origem: d.origem ?? null,
  quem: lerQuem(d.quem),
  mudancas: lista(d.mudancas).map((m) => ({ campo: String(m.campo), antes: m.antes ?? null, depois: m.depois ?? null })),
  antes: d.antes && typeof d.antes === 'object' ? d.antes : null,
  depois: d.depois && typeof d.depois === 'object' ? d.depois : null,
})

export async function listarAuditoria({ pagina = 1, porPagina = 20, quem, ...filtros }, sinal) {
  const dados = await sa.get('/auditoria', {
    query: { ...queryAuditoria(filtros), quem: quem || undefined, pagina, por_pagina: porPagina },
    sinal,
  })
  return lerPagina(dados, lerItemAuditoria)
}

export const listarPessoasAuditoria = async (filtros, sinal) =>
  lista(await sa.get('/auditoria/pessoas', { query: queryAuditoria(filtros), sinal })).map(lerQuem)
