import { Component } from 'react'
import { Button } from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import EstadoVazio from './EstadoVazio.jsx'

// Se uma tela quebrar, mostra o erro no lugar dela e mantém o menu funcionando.
// Error boundary ainda só existe como componente de classe no React.
export default class LimiteErro extends Component {
  state = { erro: null }

  static getDerivedStateFromError(erro) {
    return { erro }
  }

  render() {
    if (!this.state.erro) return this.props.children
    return (
      <div className="secao">
        <EstadoVazio
          icone={<WarningOutlined />}
          titulo="Esta tela não carregou"
          descricao="Algo deu errado ao montar a tela. Recarregue a página; se continuar, avise o suporte."
          acao={<Button onClick={() => window.location.reload()}>Recarregar a página</Button>}
        />
      </div>
    )
  }
}
