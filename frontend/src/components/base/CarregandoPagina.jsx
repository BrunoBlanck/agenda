import { Skeleton } from 'antd'

// Enquanto a tela é baixada: o formato da página (cabeçalho e um bloco), sem spinner no meio
export default function CarregandoPagina() {
  return (
    <div className="pagina" aria-busy="true" aria-label="Carregando">
      <div>
        <Skeleton.Input active size="large" className="carregando-titulo" />
        <Skeleton active title={false} paragraph={{ rows: 1, width: '100%' }} className="carregando-descricao" />
      </div>
      <div className="secao">
        <div className="secao-corpo">
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      </div>
    </div>
  )
}
