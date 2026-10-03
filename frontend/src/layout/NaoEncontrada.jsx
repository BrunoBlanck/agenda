import { Button } from 'antd'
import { CompassOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import { caminhoPainel } from './caminhos.js'

// Endereço que não existe na SPA.
// Sem `inicio`: tela solta (fora das áreas, ex.: slug inválido), só texto, sem link para outra área.
// Com `inicio`: dentro do painel já aberto (menu à esquerda), com o atalho para o início da área.
export default function NaoEncontrada({ inicio }) {
  const navigate = useNavigate()

  if (inicio) {
    return (
      <Pagina titulo="Página não encontrada">
        <Secao>
          <EstadoVazio
            icone={<CompassOutlined />}
            titulo="Este endereço não existe no painel"
            descricao="Confira o endereço ou escolha uma tela no menu."
            acao={<Button onClick={() => navigate(inicio)}>Ir para o início</Button>}
          />
        </Secao>
      </Pagina>
    )
  }

  return (
    <main className="pagina-solta">
      <title>Página não encontrada | Agenda</title>
      <section className="pagina-solta-folha">
        <EstadoVazio
          icone={<CompassOutlined />}
          titulo="Página não encontrada"
          descricao={`Confira o endereço digitado. O painel de cada loja fica em ${caminhoPainel('nome-da-loja')}.`}
        />
      </section>
    </main>
  )
}
