import { useId } from 'react'

// Bloco de conteúdo com fundo branco e borda (sem sombra). Use só quando o grupo for de fato separado.
// rente: o conteúdo (ex.: tabela) encosta nas bordas da seção.
export default function Secao({ titulo, descricao, acoes, rente = false, className, children }) {
  const id = useId()
  const temCabecalho = titulo || acoes
  return (
    <section className={['secao', className].filter(Boolean).join(' ')} aria-labelledby={titulo ? id : undefined}>
      {temCabecalho && (
        <div className="secao-cabecalho">
          <div>
            {titulo && <h2 id={id}>{titulo}</h2>}
            {descricao && <p>{descricao}</p>}
          </div>
          {acoes && <div className="pagina-acoes">{acoes}</div>}
        </div>
      )}
      <div className={rente ? 'secao-corpo rente' : 'secao-corpo'}>{children}</div>
    </section>
  )
}
