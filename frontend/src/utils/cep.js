import { soDigitos } from './formatos.js'

const TEMPO_LIMITE = 5_000

// Endereço pelo CEP (ViaCEP, serviço público fora da nossa API: por isso não passa por data/api/cliente.js,
// que só fala com o back-end e anexa o token). Só o CEP sai do navegador.
// null = CEP não encontrado ou resposta inesperada; sem conexão/tempo esgotado sobe como erro para quem chamou.
export async function buscarEndereco(cep) {
  const digitos = soDigitos(cep)
  if (digitos.length !== 8) return null
  const controle = new AbortController()
  const relogio = setTimeout(() => controle.abort(), TEMPO_LIMITE)
  try {
    const resposta = await fetch(`https://viacep.com.br/ws/${digitos}/json/`, { signal: controle.signal })
    if (!resposta.ok) return null
    const endereco = await resposta.json().catch(() => null)
    if (!endereco || typeof endereco !== 'object' || endereco.erro) return null
    // Só o que veio preenchido: campo vazio no ViaCEP não apaga o que a pessoa já digitou
    const campos = { logradouro: endereco.logradouro, bairro: endereco.bairro, cidade: endereco.localidade, uf: endereco.uf }
    return Object.fromEntries(Object.entries(campos).filter(([, v]) => typeof v === 'string' && v.trim()))
  } finally {
    clearTimeout(relogio)
  }
}
