import dayjs from 'dayjs'
import { useData } from './DataContext.jsx'
import { modulos as catalogoModulos, recursos } from './acesso.js'

const peso = { nenhum: 0, leitura: 1, escrita: 2 }

// Regras de acesso do usuário logado (estrutura.md, 1.7, 1.8 e 2.2).
export function useAcesso() {
  const { funcionarios, perfis, modulos, sessao } = useData()
  const usuario = funcionarios.itens.find((f) => f.id === sessao.usuarioId)
  const perfil = perfis.itens.find((p) => p.id === usuario?.perfilId)

  // Módulo opcional: precisa estar habilitado e não ter vencido (loja_funcionalidades.expira_em)
  const moduloAtivo = (codigo) => {
    const modulo = catalogoModulos.find((m) => m.codigo === codigo)
    if (!modulo) return false
    if (!modulo.opcional) return true
    const expiraEm = modulos.info[codigo]?.expiraEm
    return !!modulos.ativos[codigo] && (!expiraEm || dayjs(expiraEm).isAfter(dayjs()))
  }

  // Nível efetivo: módulo desativado = nenhum, inclusive para o Administrador
  const nivel = (codigoRecurso) => {
    const recurso = recursos.find((r) => r.codigo === codigoRecurso)
    if (!recurso || !perfil || !moduloAtivo(recurso.modulo)) return 'nenhum'
    if (perfil.acessoTotal) return 'escrita'
    return perfil.acessos[codigoRecurso] ?? 'nenhum'
  }

  const pode = (codigoRecurso, minimo = 'leitura') => peso[nivel(codigoRecurso)] >= peso[minimo]

  const doUsuario = (a) => a.funcionarioId === usuario?.id
  const agenda = {
    verEquipe: pode('agenda_equipe'),
    criar: pode('agenda_equipe', 'escrita') || pode('agenda_propria', 'escrita'),
    criarParaOutros: pode('agenda_equipe', 'escrita'),
    ver: (a) => pode('agenda_equipe') || (pode('agenda_propria') && doUsuario(a)),
    editar: (a) => pode('agenda_equipe', 'escrita') || (pode('agenda_propria', 'escrita') && doUsuario(a)),
  }

  return { usuario, perfil, moduloAtivo, nivel, pode, agenda }
}
