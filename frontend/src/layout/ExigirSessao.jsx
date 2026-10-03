import { Button } from 'antd'
import { DisconnectOutlined } from '@ant-design/icons'
import { Navigate, useLocation } from 'react-router-dom'
import CarregandoPagina from '../components/base/CarregandoPagina.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'

// Só mostra a área com sessão válida (INT-07). Sem sessão, vai ao login guardando a rota para voltar.
export default function ExigirSessao({ sessao, login, children }) {
  const { pathname, search } = useLocation()

  if (sessao.estado === 'verificando') {
    return (
      <div className="carregando-area">
        <CarregandoPagina />
      </div>
    )
  }
  if (sessao.estado === 'falhou') {
    return (
      <div className="carregando-area">
        <div className="secao">
          <EstadoVazio
            icone={<DisconnectOutlined />}
            titulo="Sem conexão com o servidor"
            descricao={sessao.erro?.mensagem ?? 'Confira a internet e tente de novo.'}
            acao={<Button onClick={sessao.tentarDeNovo}>Tentar de novo</Button>}
          />
        </div>
      </div>
    )
  }
  if (sessao.estado !== 'logado') return <Navigate to={login} replace state={{ de: `${pathname}${search}` }} />
  return children
}
