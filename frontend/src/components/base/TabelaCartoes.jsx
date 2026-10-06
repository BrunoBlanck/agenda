import { useId, useRef, useState } from 'react'
import { Button, Menu, Pagination, Popover, Skeleton } from 'antd'
import { DownOutlined, FilterOutlined, UpOutlined } from '@ant-design/icons'
import './tabela-cartoes.css'

// Modo celular da Tabela (DIR-004): cada linha vira um cartão, um debaixo do outro, com a mesma API
// de colunas do Table do antd. O lugar de cada coluna no cartão vem da prop `cartao` (ver Tabela.jsx).

const VAZIO = Symbol('vazio')

// Valor da coluna no registro, como o antd: dataIndex simples ou caminho (['cliente', 'nome']);
// sem dataIndex, o próprio registro
function valorDe(registro, dataIndex) {
  if (dataIndex == null || dataIndex === '') return registro
  return (Array.isArray(dataIndex) ? dataIndex : [dataIndex]).reduce((v, k) => v?.[k], registro)
}

function conteudoDe(coluna, registro, i) {
  const valor = valorDe(registro, coluna.dataIndex)
  const no = coluna.render ? coluna.render(valor, registro, i) : valor
  // Nada para mostrar (render devolveu null/false, ou campo vazio sem render): o par some do cartão
  if (no == null || no === false || no === '' || (Array.isArray(no) && no.length === 0)) return VAZIO
  return typeof no === 'object' && !Array.isArray(no) && !('$$typeof' in no) ? VAZIO : no
}

const chaveColuna = (c, i) => c.key ?? (Array.isArray(c.dataIndex) ? c.dataIndex.join('.') : c.dataIndex) ?? `coluna-${i}`
const rotuloDe = (c) => (typeof c.title === 'function' ? c.title({}) : c.title)

function papelDe(coluna) {
  if (coluna.cartao === false || coluna.hidden) return null
  if (coluna.cartao === 'acoes' || coluna.cartao === 'rodape') return 'acoes'
  if (coluna.cartao === undefined && coluna.key === 'acoes') return 'acoes'
  return coluna.cartao ?? 'par'
}

// Filtro de coluna (filters/filterDropdown do antd) num botão acima dos cartões, já que não há cabeçalho
function FiltroColuna({ coluna, valores, aoMudar }) {
  const [aberto, setAberto] = useState(false)
  const [rascunho, setRascunho] = useState(valores)
  const opcoes = coluna.filters ?? []
  const multiplo = coluna.filterMultiple !== false
  const titulo = rotuloDe(coluna)
  const nomes = valores.map((v) => opcoes.find((o) => o.value === v)?.text ?? String(v))

  const abrir = (sim) => {
    if (sim) setRascunho(valores)
    setAberto(sim)
  }

  const escolher = ({ key }) => {
    if (key === 'todos') aoMudar([])
    else {
      const valor = opcoes[Number(key)].value
      aoMudar(multiplo ? (valores.includes(valor) ? valores.filter((v) => v !== valor) : [...valores, valor]) : [valor])
    }
    if (!multiplo || key === 'todos') setAberto(false)
  }

  const conteudo =
    typeof coluna.filterDropdown === 'function' ? (
      coluna.filterDropdown({
        prefixCls: 'ant-table-filter',
        selectedKeys: rascunho,
        setSelectedKeys: setRascunho,
        confirm: ({ closeDropdown = true } = {}) => {
          aoMudar(rascunho)
          if (closeDropdown) setAberto(false)
        },
        clearFilters: () => {
          setRascunho([])
          aoMudar([])
        },
        filters: opcoes,
        visible: aberto,
        close: () => setAberto(false),
      })
    ) : coluna.filterDropdown ? (
      coluna.filterDropdown
    ) : (
      <Menu
        selectable
        multiple={multiplo}
        selectedKeys={valores.length ? opcoes.flatMap((o, i) => (valores.includes(o.value) ? [String(i)] : [])) : ['todos']}
        items={[{ key: 'todos', label: 'Todos' }, ...opcoes.map((o, i) => ({ key: String(i), label: o.text }))]}
        onClick={escolher}
      />
    )

  return (
    <Popover open={aberto} onOpenChange={abrir} trigger="click" placement="bottomLeft" arrow={false} content={<div className="tabela-cartoes-filtro-conteudo">{conteudo}</div>}>
      <Button className={nomes.length ? 'tabela-cartoes-filtro ativo' : 'tabela-cartoes-filtro'} icon={<FilterOutlined />}>
        <span className="tabela-cartoes-filtro-texto">
          {titulo}
          {nomes.length > 0 && `: ${nomes.join(', ')}`}
        </span>
      </Button>
    </Popover>
  )
}

function CartoesCarregando() {
  return (
    <ul className="tabela-cartoes" aria-busy="true" aria-label="Carregando">
      {[0, 1, 2].map((i) => (
        <li key={i} className="cartao-tabela cartao-tabela-fantasma" aria-hidden="true">
          <Skeleton active title={{ width: '55%' }} paragraph={{ rows: 2, width: ['80%', '45%'] }} />
        </li>
      ))}
    </ul>
  )
}

export default function TabelaCartoes({
  columns = [],
  dataSource,
  rowKey = 'id',
  loading,
  pagination,
  vazio,
  rowClassName,
  onRow,
  expandable,
}) {
  const id = useId()
  const inicio = useRef(null)
  const [filtros, setFiltros] = useState({})
  const [paginaLocal, setPaginaLocal] = useState(pagination?.defaultCurrent ?? 1)
  const [expandidos, setExpandidos] = useState(() => new Set())

  const colunas = columns.filter(Boolean).map((c, i) => ({ coluna: c, chave: chaveColuna(c, i), papel: papelDe(c) }))
  // Título: a coluna marcada, senão a primeira que viraria par rótulo/valor
  if (!colunas.some((c) => c.papel === 'titulo')) {
    const primeira = colunas.find((c) => c.papel === 'par')
    if (primeira) primeira.papel = 'titulo'
  }
  const doPapel = (papel) => colunas.filter((c) => c.papel === papel || (papel === 'par' && c.papel === 'bloco'))

  // Filtros: controlados (filteredValue) vêm da tela; os outros ficam aqui. onFilter filtra a lista carregada.
  const comFiltro = colunas.filter(({ coluna }) => coluna.filters || coluna.filterDropdown)
  const valoresDe = ({ coluna, chave }) =>
    (coluna.filteredValue !== undefined ? coluna.filteredValue : (filtros[chave] ?? coluna.defaultFilteredValue)) ?? []
  const registros = (dataSource ?? []).filter((r) =>
    comFiltro.every((f) => {
      const valores = valoresDe(f)
      return !valores.length || !f.coluna.onFilter || valores.some((v) => f.coluna.onFilter(v, r))
    }),
  )

  // Paginação igual à do Table: local (fatia a lista) ou no servidor (total informado, lista já é a página)
  const config = pagination === false ? null : (pagination ?? {})
  const porPagina = config?.pageSize ?? config?.defaultPageSize ?? 10
  const total = config?.total ?? registros.length
  const ultima = Math.max(1, Math.ceil(total / porPagina))
  const atual = Math.min(config?.current ?? paginaLocal, ultima)
  const visiveis = config && registros.length > porPagina ? registros.slice((atual - 1) * porPagina, atual * porPagina) : registros

  const mudarPagina = (pagina, tamanho) => {
    setPaginaLocal(pagina)
    config?.onChange?.(pagina, tamanho)
    // Trocar de página no fim da lista volta para o primeiro cartão
    inicio.current?.scrollIntoView({ block: 'start' })
  }

  const mudarFiltro = (chave) => (valores) => {
    setFiltros((f) => ({ ...f, [chave]: valores }))
    setPaginaLocal(1)
  }

  const chaveDe = (r, i) => (typeof rowKey === 'function' ? rowKey(r, i) : (r?.[rowKey] ?? i))
  const carregando = loading !== null && typeof loading === 'object' ? !!loading.spinning : !!loading

  const abertos = expandable?.expandedRowKeys ? new Set(expandable.expandedRowKeys) : expandidos
  const alternar = (registro, chave) => {
    const abrir = !abertos.has(chave)
    const novos = new Set(abertos)
    if (abrir) novos.add(chave)
    else novos.delete(chave)
    setExpandidos(novos)
    expandable?.onExpand?.(abrir, registro)
    expandable?.onExpandedRowsChange?.([...novos])
  }

  const cartao = (registro, i) => {
    const chave = chaveDe(registro, i)
    const linha = onRow?.(registro, i) ?? {}
    const preenchidas = (papel) =>
      doPapel(papel)
        .map((c) => ({ ...c, no: conteudoDe(c.coluna, registro, i) }))
        .filter((c) => c.no !== VAZIO)
    const [titulo] = doPapel('titulo')
    const tituloNo = titulo ? conteudoDe(titulo.coluna, registro, i) : VAZIO
    const subtitulos = preenchidas('subtitulo')
    const etiquetas = preenchidas('etiqueta')
    const pares = preenchidas('par')
    const acoes = preenchidas('acoes')
    const expansivel = !!expandable?.expandedRowRender && (expandable.rowExpandable?.(registro) ?? true)
    const expandido = expansivel && abertos.has(chave)
    const idExpansao = `${id}-${chave}`
    const rotuloExpansao =
      typeof expandable?.rotuloCartao === 'function' ? expandable.rotuloCartao(registro) : (expandable?.rotuloCartao ?? 'Mais detalhes')
    const textoTitulo = tituloNo === VAZIO ? '—' : tituloNo

    return (
      <li key={chave} className={['cartao-tabela', rowClassName?.(registro, i)].filter(Boolean).join(' ')}>
        <div className="cartao-tabela-topo">
          <div className="cartao-tabela-cabeca">
            <h3 className="cartao-tabela-titulo">
              {/* Linha clicável (onRow.onClick): o título vira o botão que cobre o cartão inteiro */}
              {linha.onClick ? (
                <button type="button" className="cartao-tabela-abrir" onClick={linha.onClick}>
                  {textoTitulo}
                </button>
              ) : (
                textoTitulo
              )}
            </h3>
            {subtitulos.length > 0 && (
              <p className="cartao-tabela-subtitulo">
                {subtitulos.map((c) => (
                  <span key={c.chave}>{c.no}</span>
                ))}
              </p>
            )}
          </div>
          {etiquetas.length > 0 && (
            <div className="cartao-tabela-etiquetas">
              {etiquetas.map((c) => (
                <span key={c.chave}>{c.no}</span>
              ))}
            </div>
          )}
        </div>

        {pares.length > 0 && (
          <dl className="cartao-tabela-dados">
            {pares.map((c) => (
              <div key={c.chave} className={c.papel === 'bloco' ? 'cartao-tabela-par bloco' : 'cartao-tabela-par'}>
                <dt>{rotuloDe(c.coluna)}</dt>
                <dd>{c.no}</dd>
              </div>
            ))}
          </dl>
        )}

        {expandido && (
          <div id={idExpansao} className="cartao-tabela-expandido">
            {expandable.expandedRowRender(registro, i, 0, true)}
          </div>
        )}

        {(acoes.length > 0 || expansivel) && (
          <div className="cartao-tabela-rodape">
            {expansivel && (
              <Button
                type="text"
                className="cartao-tabela-expandir"
                icon={expandido ? <UpOutlined /> : <DownOutlined />}
                aria-expanded={expandido}
                aria-controls={expandido ? idExpansao : undefined}
                onClick={() => alternar(registro, chave)}
              >
                {rotuloExpansao}
              </Button>
            )}
            {acoes.length > 0 && (
              <div className="cartao-tabela-acoes">
                {acoes.map((c) => (
                  <span key={c.chave}>{c.no}</span>
                ))}
              </div>
            )}
          </div>
        )}
      </li>
    )
  }

  return (
    <div className="tabela-cartoes-area" ref={inicio}>
      {comFiltro.length > 0 && (
        <div className="tabela-cartoes-filtros" role="group" aria-label="Filtros da lista">
          {comFiltro.map((f) => (
            <FiltroColuna key={f.chave} coluna={f.coluna} valores={valoresDe(f)} aoMudar={mudarFiltro(f.chave)} />
          ))}
        </div>
      )}

      {carregando && visiveis.length === 0 ? (
        <CartoesCarregando />
      ) : visiveis.length === 0 ? (
        <div className="tabela-cartoes-vazio">{vazio}</div>
      ) : (
        <ul className={carregando ? 'tabela-cartoes atualizando' : 'tabela-cartoes'} aria-busy={carregando || undefined}>
          {visiveis.map(cartao)}
        </ul>
      )}

      {config && (
        <Pagination
          className="tabela-cartoes-paginacao"
          simple={{ readOnly: true }}
          current={atual}
          pageSize={porPagina}
          total={total}
          onChange={mudarPagina}
          hideOnSinglePage={config.hideOnSinglePage}
          showSizeChanger={false}
        />
      )}
    </div>
  )
}
