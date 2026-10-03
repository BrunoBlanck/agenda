import { useConsulta } from '../data/api/useConsulta.js'
import { buscarHorariosSite, buscarLocaisSite, buscarLojaPublica, buscarServicosSite } from '../data/api/site.js'

// Hooks do protótipo do site do consumidor (só usados aqui; o painel não importa nada de site/).

/** Dados públicos da loja e serviços oferecidos. erro.status 404 = agendamento online indisponível. */
export function useLojaPublica(slug) {
  const consulta = useConsulta(
    (sinal) =>
      Promise.all([buscarLojaPublica(slug, sinal), buscarServicosSite(slug, sinal)]).then(([loja, servicos]) => ({
        loja,
        servicos,
      })),
    ['site-loja', slug],
  )
  return {
    loja: consulta.dados?.loja ?? null,
    servicos: consulta.dados?.servicos ?? [],
    carregando: consulta.carregando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
  }
}

/** Locais onde o serviço pode acontecer (vazio sem o módulo Locais). */
export function useLocaisSite(slug, servicoId, ativo) {
  const consulta = useConsulta((sinal) => buscarLocaisSite(slug, servicoId, sinal), ['site-locais', slug, servicoId], {
    ativo,
  })
  return { locais: consulta.dados ?? [], carregando: consulta.carregando, erro: consulta.erro }
}

/** Horários livres por dia, prontos do servidor. filtros: { servicoId, funcionarioId, localId, inicio, fim }. */
export function useHorariosSite(slug, filtros, ativo) {
  const consulta = useConsulta((sinal) => buscarHorariosSite(slug, filtros, sinal), ['site-horarios', slug, filtros], {
    ativo,
  })
  return {
    dias: consulta.dados ?? [],
    carregando: consulta.carregando,
    atualizando: consulta.atualizando,
    erro: consulta.erro,
    recarregar: consulta.recarregar,
    definirDados: consulta.definirDados,
  }
}
