import { api, urlDaApi } from '../api/cliente.js'
import { definirFusoLoja, paraCamel } from '../api/conversao.js'
import { criarSessao } from './criarSessao.jsx'

// GET /api/loja/eu: funcionário, perfil, loja, módulos ativos e nível efetivo em cada recurso.
// modulos e acessos são mapas por código (controle_tempo, agenda_propria): ficam como vieram.
export const converterEuLoja = (dados) => {
  const eu = paraCamel(dados, ['modulos', 'acessos'])
  return {
    funcionario: { ...eu.funcionario, cor: eu.funcionario?.corAgenda ?? null },
    perfil: eu.perfil,
    loja: eu.loja && { ...eu.loja, logoUrl: urlDaApi(eu.loja.logoUrl) },
    modulos: eu.modulos ?? {},
    acessos: eu.acessos ?? {},
  }
}

const loja = criarSessao('loja', {
  entrarApi: async ({ slug, email, senha }) =>
    (await api.loja.post('/auth/login', { slug: slug.trim().toLowerCase(), email: email.trim(), senha })).token,
  euApi: async (sinal) => converterEuLoja(await api.loja.get('/eu', { sinal })),
  aoCarregar: (eu) => definirFusoLoja(eu.loja?.fusoHorario),
})

const superadmin = criarSessao('superadmin', {
  entrarApi: async ({ email, senha }) => (await api.superadmin.post('/auth/login', { email: email.trim(), senha })).token,
  euApi: async (sinal) => paraCamel(await api.superadmin.get('/eu', { sinal })),
})

export const SessaoLojaProvider = loja.Provider
export const useSessaoLoja = loja.useSessao
export const SessaoSuperadminProvider = superadmin.Provider
export const useSessaoSuperadmin = superadmin.useSessao
