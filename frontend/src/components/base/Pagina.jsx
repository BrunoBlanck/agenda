import { Button } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

// Estrutura de toda tela dos painéis: título, descrição curta, ações principais e o conteúdo.
// voltar: rota da tela anterior (mostra a seta ao lado do título).
export default function Pagina({ titulo, descricao, acoes, voltar, children }) {
  const navigate = useNavigate()
  return (
    <div className="pagina">
      {typeof titulo === 'string' && <title>{`${titulo} | Agenda`}</title>}
      <header className="pagina-cabecalho">
        <div className="pagina-titulo">
          {voltar && (
            <Button
              type="text"
              className="pagina-voltar"
              icon={<ArrowLeftOutlined />}
              aria-label="Voltar"
              onClick={() => navigate(voltar)}
            />
          )}
          <div>
            <h1>{titulo}</h1>
            {descricao && <p className="pagina-descricao">{descricao}</p>}
          </div>
        </div>
        {acoes && <div className="pagina-acoes">{acoes}</div>}
      </header>
      {children}
    </div>
  )
}
