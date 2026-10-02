import { useData } from '../data/DataContext.jsx'
import { codigosOpcionais } from '../data/acesso.js'
import { tiposLoja } from '../data/plataforma.js'

const PERFIS_PADRAO = ['Administrador', 'Recepção', 'Profissional']

// Operações do superadmin sobre as lojas. Tudo é gravado com autor = null (não é um funcionário);
// o histórico (auditoria) guarda qual superadmin fez.
export function usePlataforma() {
  const { lojas, lojaAtualId, planos, funcionarios, perfis, registrar, definirModulo } = useData()

  const ehAtual = (loja) => loja.id === lojaAtualId
  const nomeTipo = (codigo) => tiposLoja[codigo]?.nome ?? '—'
  const plano = (id) => planos.todos.find((p) => p.id === id)

  // A loja atual usa os funcionários e perfis reais do painel da loja; as outras, os dados de exemplo
  const perfisDe = (loja) => (ehAtual(loja) ? perfis.itens.map((p) => p.nome) : PERFIS_PADRAO)

  const funcionariosDe = (loja, { comExcluidos = false } = {}) =>
    ehAtual(loja)
      ? (comExcluidos ? funcionarios.todos : funcionarios.itens).map((f) => ({
          ...f,
          perfil: perfis.todos.find((p) => p.id === f.perfilId)?.nome,
        }))
      : (loja.funcionarios ?? [])

  // Nas lojas de exemplo os funcionários ficam dentro da própria loja: o histórico é registrado à parte
  const salvarFuncionario = (loja, dados, id) => {
    if (ehAtual(loja)) {
      const { perfil, ...resto } = dados
      const perfilId = perfis.itens.find((p) => p.nome === perfil)?.id
      if (id) funcionarios.atualizar(id, { ...resto, perfilId }, null)
      else funcionarios.adicionar({ cargo: 'Administrador', cor: '#0f766e', ...resto, perfilId, criadoPorSuperadmin: true }, null)
      return
    }
    const lista = loja.funcionarios ?? []
    const antes = lista.find((f) => f.id === id) ?? null
    const depois = antes ? { ...antes, ...dados } : { ...dados, id: lista.length + 1, criadoPorSuperadmin: true }
    lojas.atualizar(loja.id, { funcionarios: antes ? lista.map((f) => (f.id === id ? depois : f)) : [...lista, depois] }, null, {
      semHistorico: true,
    })
    registrar({ lojaId: loja.id, tabela: 'funcionarios', registroId: depois.id, operacao: antes ? 'alterar' : 'inserir', antes, depois, autor: null })
  }

  const redefinirSenha = (loja, f) =>
    registrar({
      lojaId: loja.id,
      tabela: 'funcionarios',
      registroId: f.id,
      operacao: 'alterar',
      antes: { id: f.id, nome: f.nome, senha: '••••••' },
      depois: { id: f.id, nome: f.nome, senha: 'link de nova senha enviado' },
      autor: null,
    })

  const editarLoja = (loja, dados) => lojas.atualizar(loja.id, dados, null)

  // Nova loja: o superadmin escolhe os módulos que a loja vai usar e já cadastra o primeiro Administrador
  const criarLoja = ({ admin, modulos: escolhidos = [], ...dados }) => {
    const modulos = Object.fromEntries(codigosOpcionais.map((c) => [c, escolhidos.includes(c)]))
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
    registrar({
      lojaId: id,
      tabela: 'funcionarios',
      registroId: 1,
      operacao: 'inserir',
      antes: null,
      depois: { id: 1, nome: admin.nome, email: admin.email, perfil: 'Administrador', ativo: true },
      autor: null,
    })
    return id
  }

  return {
    ehAtual,
    nomeTipo,
    plano,
    perfisDe,
    funcionariosDe,
    salvarFuncionario,
    redefinirSenha,
    editarLoja,
    definirModulo,
    criarLoja,
  }
}
