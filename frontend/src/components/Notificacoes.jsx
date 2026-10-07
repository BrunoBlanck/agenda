import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { Button, Skeleton } from 'antd'
import {
  BellOutlined,
  CalendarOutlined,
  CloseCircleOutlined,
  DisconnectOutlined,
  ReloadOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { useAcesso } from '../data/useAcesso.js'
import { useNotificacoes, useNotificacoesResumo } from '../data/useNotificacoes.js'
import { agoraNaLoja } from '../data/api/conversao.js'
import { foiCancelada } from '../data/api/cliente.js'
import { usePainelPath } from '../layout/caminhos.js'
import { dataHoraBR, plural, quandoAconteceu } from '../utils/formatos.js'
import EstadoVazio from './base/EstadoVazio.jsx'
import Etiqueta from './base/Etiqueta.jsx'
import PainelLateral from './base/PainelLateral.jsx'
import './notificacoes.css'

// Ícone e tom de cada evento da loja (NOT-03); evento desconhecido usa o sino em tom neutro
const EVENTOS = {
  novo_pedido: { icone: <CalendarOutlined />, tom: 'tinta' },
  remarcacao_pedida: { icone: <SwapOutlined />, tom: 'atencao' },
  cancelado_pelo_cliente: { icone: <CloseCircleOutlined />, tom: 'perigo' },
}
const EVENTO_PADRAO = { icone: <BellOutlined />, tom: 'neutro' }

const LOTE_MARCACAO = 100 // POST /visualizar aceita até 100 ids

/**
 * Sino do cabeçalho do painel (NOT-06): contador do que não foi visto e, ao clicar, o painel lateral
 * com as notificações do usuário logado. Abrir marca como visualizadas as que aparecem na lista.
 */
export default function SinoNotificacoes() {
  const [aberto, setAberto] = useState(false)
  const resumo = useNotificacoesResumo()
  // Carregando ou com falha: sino sem número (a falha não aparece como erro)
  const n = resumo.naoVisualizadas ?? 0
  const rotulo = n > 0 ? `Notificações, ${n > 99 ? 'mais de 99' : n} ${n === 1 ? 'não lida' : 'não lidas'}` : 'Notificações'

  return (
    <>
      <Button type="text" className="sino" icon={<BellOutlined />} aria-label={rotulo} aria-haspopup="dialog" onClick={() => setAberto(true)}>
        {n > 0 && (
          <span className="sino-contador" aria-hidden="true">
            {n > 99 ? '99+' : n}
          </span>
        )}
      </Button>
      <PainelNotificacoes aberto={aberto} onClose={() => setAberto(false)} aoMarcar={resumo.recarregar} />
    </>
  )
}

function PainelNotificacoes({ aberto, onClose, aoMarcar }) {
  const lista = useNotificacoes(aberto)
  const { usuario, pode } = useAcesso()
  const caminho = usePainelPath()
  const verAgenda = pode('agenda_propria') || pode('agenda_equipe')

  // Não lidas que apareceram nesta abertura: continuam destacadas até fechar, mesmo depois de marcadas
  const [destacadas, setDestacadas] = useState([])
  const [mais, setMais] = useState({ carregando: false, erro: null })
  const [abertoAntes, setAbertoAntes] = useState(aberto)
  if (aberto !== abertoAntes) {
    setAbertoAntes(aberto)
    if (aberto) {
      setDestacadas([])
      setMais({ carregando: false, erro: null })
    }
  }
  const naoLidas = aberto ? lista.itens.filter((item) => !item.visualizada && !destacadas.includes(item.id)).map((item) => item.id) : []
  if (naoLidas.length) setDestacadas((atuais) => [...atuais, ...naoLidas.filter((id) => !atuais.includes(id))])

  // Marca na API as não lidas mostradas (também as que chegam por "Carregar mais"), uma vez por abertura.
  // Falha não atrapalha a lista: elas continuam não lidas e são marcadas na próxima abertura.
  const enviadas = useRef(new Set())
  const marcar = useEffectEvent((ids) => {
    lista.marcarVisualizadas(ids).then(aoMarcar, () => {})
  })
  useEffect(() => {
    if (aberto) enviadas.current = new Set()
  }, [aberto])
  const chaveDestacadas = destacadas.join(',')
  useEffect(() => {
    if (!aberto || !chaveDestacadas) return
    const novas = chaveDestacadas.split(',').filter((id) => !enviadas.current.has(id))
    novas.forEach((id) => enviadas.current.add(id))
    for (let i = 0; i < novas.length; i += LOTE_MARCACAO) marcar(novas.slice(i, i + LOTE_MARCACAO))
  }, [aberto, chaveDestacadas])

  const carregarMais = async () => {
    setMais({ carregando: true, erro: null })
    try {
      await lista.carregarMais()
      setMais({ carregando: false, erro: null })
    } catch (e) {
      if (!foiCancelada(e)) setMais({ carregando: false, erro: e?.mensagem ?? 'Não foi possível carregar mais notificações.' })
    }
  }

  const agora = agoraNaLoja()
  let conteudo
  if (lista.erro) {
    conteudo = (
      <EstadoVazio
        icone={<DisconnectOutlined />}
        titulo="Não foi possível carregar as notificações"
        descricao={lista.erro.mensagem}
        acao={<Button onClick={lista.recarregar}>Tentar de novo</Button>}
      />
    )
  } else if (lista.carregando) {
    conteudo = (
      <div className="notificacoes-carregando" aria-busy="true" aria-label="Carregando as notificações">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} active avatar={{ size: 32 }} title={{ width: '50%' }} paragraph={{ rows: 2, width: ['100%', '30%'] }} />
        ))}
      </div>
    )
  } else if (!lista.itens.length) {
    conteudo = (
      <EstadoVazio
        icone={<BellOutlined />}
        titulo="Nenhuma notificação por enquanto."
        descricao="Você é avisado aqui quando um cliente pede, remarca ou cancela um horário seu pelo site."
      />
    )
  } else {
    conteudo = (
      <>
        <ul className="lista-linhas notificacoes-lista">
          {lista.itens.map((item) => (
            <ItemNotificacao
              key={item.id}
              item={item}
              nova={destacadas.includes(item.id)}
              agora={agora}
              linkAgenda={verAgenda && item.agendamentoId && item.inicioAgendamento ? `${caminho('/agenda')}?dia=${item.inicioAgendamento.format('YYYY-MM-DD')}` : null}
              aoSeguirLink={onClose}
            />
          ))}
        </ul>
        {lista.temMais && (
          <div className="notificacoes-mais">
            <span className="texto-apoio numeros">
              Mostrando {lista.itens.length} de {lista.total}
            </span>
            <Button block loading={mais.carregando} onClick={carregarMais}>
              Carregar mais
            </Button>
            {mais.erro && (
              <p className="notificacoes-mais-erro" role="alert">
                {mais.erro}
              </p>
            )}
          </div>
        )}
      </>
    )
  }

  return (
    <PainelLateral
      titulo="Notificações"
      nome={usuario?.nome || 'Você'}
      icone={<BellOutlined />}
      open={aberto}
      onClose={onClose}
      rootClassName="painel-notificacoes"
    >
      {/* Atualizar fica junto da lista (no cabeçalho, no celular, disputaria espaço com o título) */}
      <div className="notificacoes-barra">
        <strong aria-live="polite">{!lista.carregando && !lista.erro && destacadas.length ? plural(destacadas.length, 'nova', 'novas') : null}</strong>
        <Button type="text" size="small" icon={<ReloadOutlined />} disabled={lista.carregando} onClick={lista.recarregar}>
          Atualizar
        </Button>
      </div>
      {conteudo}
    </PainelLateral>
  )
}

function ItemNotificacao({ item, nova, agora, linkAgenda, aoSeguirLink }) {
  const { icone, tom } = EVENTOS[item.evento] ?? EVENTO_PADRAO
  return (
    <li className={nova ? 'notificacao nova' : 'notificacao'}>
      <span className={`notificacao-icone tom-${tom}`} aria-hidden="true">
        {icone}
      </span>
      <div className="notificacao-corpo">
        <div className="notificacao-topo">
          <h3 className="notificacao-titulo">{item.titulo}</h3>
          {nova && <Etiqueta tom="marca">Nova</Etiqueta>}
        </div>
        <p className="notificacao-mensagem">{item.mensagem}</p>
        <div className="notificacao-rodape">
          <time className="numeros" dateTime={item.criadoEm?.format('YYYY-MM-DDTHH:mm')} title={dataHoraBR(item.criadoEm)}>
            {quandoAconteceu(item.criadoEm, agora)}
          </time>
          {linkAgenda && (
            <Link to={linkAgenda} className="notificacao-link" onClick={aoSeguirLink}>
              <CalendarOutlined aria-hidden="true" /> Ver na agenda
              <span className="sr-only"> o dia {item.inicioAgendamento.format('DD/MM')}</span>
            </Link>
          )}
        </div>
      </div>
    </li>
  )
}
