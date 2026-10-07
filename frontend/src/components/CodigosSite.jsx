import { useState } from 'react'
import { Button, Input, Skeleton } from 'antd'
import { DisconnectOutlined, KeyOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useCodigosSite } from '../data/useCodigosSite.js'
import { horaCurta, listaEmTexto, plural, soDigitos } from '../utils/formatos.js'
import EstadoVazio from './base/EstadoVazio.jsx'
import PainelLateral from './base/PainelLateral.jsx'
import CodigoConfirmacao from './CodigoConfirmacao.jsx'
import './acesso-site.css'

// Consulta dos códigos do site que aguardam o cliente (só com escrita em Clientes). Enquanto não há
// SMS/WhatsApp, o cliente pede o código à loja: a recepção acha pelo telefone e lê ou cola o código.
// Busca de novo cada vez que abre (o código vale 15 minutos). Com muitos códigos, um filtro local
// por telefone ou nome (a lista tem no máximo 100).
const COM_FILTRO = 6

const casa = (c, termo) => {
  if (!termo) return true
  const digitos = soDigitos(termo)
  if (digitos && soDigitos(c.telefone).includes(digitos)) return true
  return c.clientes.some((cliente) => cliente.nome.toLowerCase().includes(termo.toLowerCase()))
}

export default function CodigosSite({ open, onClose }) {
  const codigos = useCodigosSite(open)
  const { itens } = codigos
  const [filtro, setFiltro] = useState('')
  // Cada abertura começa sem filtro
  const [abertoAntes, setAbertoAntes] = useState(open)
  if (open !== abertoAntes) {
    setAbertoAntes(open)
    if (open) setFiltro('')
  }
  const termo = filtro.trim()
  const visiveis = itens.filter((c) => casa(c, termo))

  const contagem = !codigos.carregando && !codigos.erro && itens.length ? plural(itens.length, 'código aguardando', 'códigos aguardando') : null

  let conteudo
  if (codigos.erro) {
    conteudo = (
      <EstadoVazio
        icone={<DisconnectOutlined />}
        titulo="Não foi possível carregar os códigos"
        descricao={codigos.erro.mensagem}
        acao={<Button onClick={codigos.recarregar}>Tentar de novo</Button>}
      />
    )
  } else if (codigos.carregando) {
    conteudo = (
      <div className="codigos-site-carregando" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} active title={{ width: '45%' }} paragraph={{ rows: 1, width: '60%' }} />
        ))}
      </div>
    )
  } else if (!itens.length) {
    conteudo = (
      <EstadoVazio
        icone={<KeyOutlined />}
        titulo="Nenhum código aguardando."
        descricao="O código aparece aqui quando um cliente cria a conta ou pede para trocar a senha no site."
      />
    )
  } else {
    conteudo = (
      <>
        <p className="codigos-site-ajuda texto-apoio">Confira o telefone com o cliente antes de passar o código.</p>
        {itens.length > COM_FILTRO && (
          <div className="codigos-site-filtro">
            <Input
              prefix={<SearchOutlined />}
              placeholder="Filtrar por telefone ou nome"
              aria-label="Filtrar por telefone ou nome"
              allowClear
              value={filtro}
              onChange={(e) => setFiltro(e.target.value)}
            />
          </div>
        )}
        {!visiveis.length && <EstadoVazio compacto titulo={`Nenhum código para "${termo}"`} descricao="Confira o número com o cliente." />}
        <ul className="lista-linhas codigos-site-lista">
          {visiveis.map((c) => (
            <li key={`${c.telefone}-${c.codigo}`} className="codigos-site-item">
              <div className="codigos-site-quem">
                <strong>{c.telefone}</strong>
                {c.clientes.length ? (
                  <span>{listaEmTexto(c.clientes.map((cliente) => cliente.nome))}</span>
                ) : (
                  <span className="codigos-site-sem-cadastro">Sem cadastro ainda</span>
                )}
              </div>
              <div className="codigos-site-codigo">
                <CodigoConfirmacao codigo={c.codigo} />
                <span className="acesso-site-validade">vale até {horaCurta(c.expiraEm?.format('HH:mm'))}</span>
              </div>
            </li>
          ))}
        </ul>
      </>
    )
  }

  return (
    <PainelLateral
      titulo="Códigos do site"
      nome="Confirmação de telefone"
      icone={<KeyOutlined />}
      open={open}
      onClose={onClose}
      rootClassName="painel-codigos-site"
    >
      {/* Atualizar fica junto da lista (no cabeçalho, no celular, disputaria espaço com o título) */}
      <div className="codigos-site-barra">
        <strong>{contagem}</strong>
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          loading={!!codigos.atualizando}
          disabled={codigos.carregando}
          onClick={codigos.recarregar}
        >
          Atualizar
        </Button>
      </div>
      {conteudo}
    </PainelLateral>
  )
}
