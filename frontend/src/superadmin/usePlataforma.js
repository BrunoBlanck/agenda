import { useData } from '../data/DataContext.jsx'

const PERFIS_PADRAO = ['Administrador', 'Recepção', 'Profissional']

// Operações do superadmin sobre as lojas. Tudo é gravado com autor = null (não é um funcionário)
// e registrado em superadmin_auditoria.
export function usePlataforma() {
  const { lojas, lojaAtualId, tipos, planos, funcionarios, perfis, registrarAuditoria } = useData()

  const ehAtual = (loja) => loja.id === lojaAtualId
  const nomeTipo = (codigo) => tipos.itens.find((t) => t.codigo === codigo)?.nome ?? '—'
  const plano = (id) => planos.itens.find((p) => p.id === id)

  // A loja atual usa os funcionários e perfis reais do painel da loja; as outras, os dados de exemplo
  const perfisDe = (loja) => (ehAtual(loja) ? perfis.itens.map((p) => p.nome) : PERFIS_PADRAO)

  const funcionariosDe = (loja) =>
    ehAtual(loja)
      ? funcionarios.itens.map((f) => ({ ...f, perfil: perfis.itens.find((p) => p.id === f.perfilId)?.nome }))
      : (loja.funcionarios ?? [])

  const salvarFuncionario = (loja, dados, id) => {
    if (ehAtual(loja)) {
      const { perfil, ...resto } = dados
      const perfilId = perfis.itens.find((p) => p.nome === perfil)?.id
      if (id) funcionarios.atualizar(id, { ...resto, perfilId }, null)
      else funcionarios.adicionar({ cargo: 'Administrador', cor: '#0f766e', ...resto, perfilId, criadoPorSuperadmin: true }, null)
    } else {
      const lista = loja.funcionarios ?? []
      const novaLista = id
        ? lista.map((f) => (f.id === id ? { ...f, ...dados } : f))
        : [...lista, { ...dados, id: Date.now(), criadoPorSuperadmin: true }]
      lojas.atualizar(loja.id, { funcionarios: novaLista }, null)
    }
    registrarAuditoria(id ? 'funcionario.editar' : 'funcionario.criar', loja.id, { nome: dados.nome })
  }

  const editarLoja = (loja, dados) => {
    lojas.atualizar(loja.id, dados, null)
    const acaoStatus = { suspensa: 'loja.suspender', cancelada: 'loja.cancelar', ativa: 'loja.reativar' }
    if (dados.status && dados.status !== loja.status) registrarAuditoria(acaoStatus[dados.status], loja.id)
    else registrarAuditoria('loja.editar', loja.id)
  }

  const definirModulo = (loja, codigo, nome, ativo) => {
    lojas.atualizar(loja.id, { modulos: { ...loja.modulos, [codigo]: ativo } }, null)
    registrarAuditoria(ativo ? 'funcionalidade.ativar' : 'funcionalidade.desativar', loja.id, { modulo: nome })
  }

  const definirInfoModulo = (loja, codigo, info) =>
    lojas.atualizar(loja.id, { modulosInfo: { ...loja.modulosInfo, [codigo]: { ...loja.modulosInfo?.[codigo], ...info } } }, null)

  // Nova loja: módulos vêm do plano (estrutura.md 1.7) e já nasce com o primeiro Administrador
  const criarLoja = ({ admin, ...dados }) => {
    const sugeridos = plano(dados.planoId)?.modulos ?? ['servicos', 'materiais', 'controle_tempo']
    const modulos = Object.fromEntries(['servicos', 'materiais', 'controle_tempo'].map((c) => [c, sugeridos.includes(c)]))
    const id = lojas.adicionar(
      {
        ...dados,
        status: 'ativa',
        fusoHorario: 'America/Sao_Paulo',
        modulos,
        modulosInfo: {},
        funcionarios: [{ id: 1, nome: admin.nome, email: admin.email, perfil: 'Administrador', ativo: true, criadoPorSuperadmin: true }],
      },
      null,
    )
    registrarAuditoria('loja.criar', id, { nome: dados.nomeFantasia })
    registrarAuditoria('funcionario.criar', id, { nome: admin.nome })
    return id
  }

  return {
    ehAtual,
    nomeTipo,
    plano,
    perfisDe,
    funcionariosDe,
    salvarFuncionario,
    editarLoja,
    definirModulo,
    definirInfoModulo,
    criarLoja,
  }
}

// Lista usada pelos cadastros da plataforma (tipos, planos, usuários): grava sem funcionário
// como autor e registra cada criação/edição na auditoria.
export function comAuditoria(lista, registrarAuditoria, entidade) {
  return {
    itens: lista.itens,
    adicionar: (item) => {
      const id = lista.adicionar(item, null)
      registrarAuditoria(`${entidade}.criar`, null, { nome: item.nome })
      return id
    },
    atualizar: (id, dados) => {
      lista.atualizar(id, dados, null)
      registrarAuditoria(`${entidade}.editar`, null, { nome: dados.nome })
    },
    remover: lista.remover,
  }
}
