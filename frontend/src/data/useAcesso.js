import { useSessaoLoja } from './sessao/sessoes.js'

const peso = { nenhum: 0, leitura: 1, escrita: 2 }

// Regras de acesso do usuário logado (estrutura.md, 1.7, 1.8 e 2.2), a partir de GET /api/loja/eu (INT-08).
// O servidor já entrega o nível efetivo (módulo desligado = nenhum, inclusive para o Administrador):
// o navegador só lê, nunca deduz permissão pelo nome do perfil. Quem decide de verdade é a API.
export function useAcesso() {
  const { eu } = useSessaoLoja()
  const usuario = eu?.funcionario ?? null
  const perfil = eu?.perfil ?? null
  const loja = eu?.loja ?? null

  const moduloAtivo = (codigo) => !!eu?.modulos?.[codigo]

  const nivel = (codigoRecurso) => {
    const n = eu?.acessos?.[codigoRecurso]
    return n in peso ? n : 'nenhum'
  }

  const pode = (codigoRecurso, minimo = 'leitura') => peso[nivel(codigoRecurso)] >= peso[minimo]

  const doUsuario = (a) => a?.funcionarioId != null && a.funcionarioId === usuario?.id
  const agenda = {
    verEquipe: pode('agenda_equipe'),
    criar: pode('agenda_equipe', 'escrita') || pode('agenda_propria', 'escrita'),
    criarParaOutros: pode('agenda_equipe', 'escrita'),
    ver: (a) => pode('agenda_equipe') || (pode('agenda_propria') && doUsuario(a)),
    editar: (a) => pode('agenda_equipe', 'escrita') || (pode('agenda_propria', 'escrita') && doUsuario(a)),
  }

  return { usuario, perfil, loja, moduloAtivo, nivel, pode, agenda }
}
