import { soDigitos } from './formatos.js'

// Endereço pelo CEP (ViaCEP). null = CEP não encontrado; erro de rede sobe para quem chamou.
export async function buscarEndereco(cep) {
  const digitos = soDigitos(cep)
  if (digitos.length !== 8) return null
  const resposta = await fetch(`https://viacep.com.br/ws/${digitos}/json/`)
  const endereco = await resposta.json()
  if (endereco.erro) return null
  return { logradouro: endereco.logradouro, bairro: endereco.bairro, cidade: endereco.localidade, uf: endereco.uf }
}
