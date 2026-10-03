import { useState } from 'react'
import { Button, Segmented, Skeleton } from 'antd'
import {
  DisconnectOutlined,
  EnvironmentOutlined,
  LockOutlined,
  MailOutlined,
  PhoneOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useAcesso } from '../data/useAcesso.js'
import { useHistoricoCliente } from '../data/useHistoricoCliente.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { agoraNaLoja } from '../data/api/conversao.js'
import { capitalizar, dataBR, horaCurta, moeda, nomeCompleto } from '../utils/formatos.js'
import { COR_PADRAO } from './agenda/util.js'
import { IconesCanais } from './CanaisCliente.jsx'
import { EtiquetaStatus } from './Etiquetas.jsx'
import PontoCor from './base/PontoCor.jsx'
import EstadoVazio from './base/EstadoVazio.jsx'
import PainelLateral from './base/PainelLateral.jsx'
import './historico-cliente.css'

const POR_PAGINA = 10

// Filtros da lista (a API filtra: o resumo continua com todos os agendamentos)
const FILTROS = {
  todos: 'Todos',
  concluidos: 'Concluídos',
  faltas: 'Faltas e cancelados',
}

const haQuanto = (data) => {
  const dias = agoraNaLoja().startOf('day').diff(dayjs(data).startOf('day'), 'day')
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'ontem'
  return `há ${dias} dias`
}

// Agrupa por mês, mantendo a ordem (mais recente primeiro)
const porMes = (lista) =>
  lista.reduce((grupos, a) => {
    const chave = a.data.slice(0, 7)
    const grupo = grupos.at(-1)
    if (grupo?.chave === chave) grupo.itens.push(a)
    else grupos.push({ chave, itens: [a] })
    return grupos
  }, [])

// Bloco de data (dia grande, mês abreviado) usado na lista e no próximo agendamento
function BlocoData({ data, destaque = false }) {
  return (
    <span className={destaque ? 'bloco-data destaque' : 'bloco-data'} aria-hidden="true">
      <strong>{data.format('DD')}</strong>
      <span>{data.format('MMM').replace('.', '')}</span>
    </span>
  )
}

// Um agendamento: serviço, horário, profissional (com a cor dele na agenda) e local
function Atendimento({ a, comLocais }) {
  const local = comLocais && a.localNome
  return (
    <div className="atendimento-textos">
      <strong className={a.status === 'cancelado' ? 'riscado' : undefined}>{a.servicoNome ?? 'Atendimento'}</strong>
      <span>
        {dataBR(a.data)}, {horaCurta(a.hora)}
        {a.horaFim && ` às ${horaCurta(a.horaFim)}`}
      </span>
      <span className="atendimento-quem">
        <span>
          <PontoCor cor={a.cor ?? COR_PADRAO} /> {a.funcionarioNome ?? '—'}
        </span>
        {local && (
          <span>
            {a.localTipo === 'online' ? <VideoCameraOutlined aria-hidden="true" /> : <EnvironmentOutlined aria-hidden="true" />} {a.localNome}
          </span>
        )}
      </span>
      {a.motivoCancelamento && <em>{a.motivoCancelamento}</em>}
    </div>
  )
}

// Histórico do cliente: resumo e os agendamentos dele, do mais recente para o mais antigo.
// Busca sozinho na API quando abre (GET /clientes/{id}/historico); quem só vê a própria agenda
// recebe só os atendimentos dele.
export default function HistoricoCliente({ clienteId, open, onClose }) {
  const { agenda, moduloAtivo } = useAcesso()
  const tratarErro = useTratarErro()
  const [filtro, setFiltro] = useState('todos')
  // Cada abertura começa com todos os agendamentos e busca de novo. Fechado, os dados ficam
  // (o painel ainda está animando a saída) e nada é buscado.
  const [abertoAntes, setAbertoAntes] = useState(open)
  const [aberturas, setAberturas] = useState(0)
  if (open !== abertoAntes) {
    setAbertoAntes(open)
    if (open) {
      setFiltro('todos')
      setAberturas((n) => n + 1)
    }
  }
  const h = useHistoricoCliente(clienteId, { ativo: open || aberturas > 0, filtro, porPagina: POR_PAGINA, abertura: aberturas })
  const { cliente, ultimo, proximo } = h
  const comLocais = moduloAtivo('locais')
  const lista = h.agendamentos.filter((a) => a.inicio)
  const faltam = Math.max(0, h.total - h.agendamentos.length)

  const verMais = async () => {
    try {
      await h.carregarMais()
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: h.recarregar })
    }
  }

  let conteudo
  if (!h.permitido) {
    conteudo = <EstadoVazio icone={<LockOutlined />} titulo="Sem acesso ao histórico" descricao="Seu perfil não permite consultar clientes." />
  } else if (h.erro && !cliente) {
    conteudo =
      h.erro.status === 404 ? (
        <EstadoVazio titulo="Cliente não encontrado" descricao="Ele pode ter sido excluído." />
      ) : (
        <EstadoVazio
          icone={<DisconnectOutlined />}
          titulo="Não foi possível carregar o histórico"
          descricao={h.erro.mensagem}
          acao={<Button onClick={h.recarregar}>Tentar de novo</Button>}
        />
      )
  } else if (!cliente) {
    conteudo = (
      <div className="historico-carregando">
        <Skeleton active title={false} paragraph={{ rows: 2 }} />
        <Skeleton.Button active block />
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    )
  } else {
    conteudo = (
      <div className="historico">
        {/* Nome e iniciais ficam no cabeçalho do painel; aqui, como falar com o cliente */}
        <div className="historico-cliente">
          <div className="historico-contato">
            <span>
              <PhoneOutlined aria-hidden="true" /> {cliente.telefone || '—'}
            </span>
            {cliente.email && (
              <span>
                <MailOutlined aria-hidden="true" /> {cliente.email}
              </span>
            )}
            <IconesCanais canais={cliente.canais} />
          </div>
          <span className="texto-apoio">
            {!cliente.ativo && 'Cadastro inativo. '}
            {ultimo ? `Último atendimento ${haQuanto(ultimo.inicio)} (${dataBR(ultimo.data)})` : 'Ainda sem atendimentos concluídos'}
          </span>
        </div>

        {cliente.observacoes && <p className="historico-observacoes">{cliente.observacoes}</p>}

        <div className="numeros-resumo historico-numeros">
          <div>
            <span>Atendimentos</span>
            <strong>{h.concluidos}</strong>
          </div>
          <div>
            <span>Faltas</span>
            <strong className={h.faltas ? 'tom-atencao' : undefined}>{h.faltas}</strong>
          </div>
          <div>
            <span>Cancelados</span>
            <strong className={h.cancelados ? 'tom-perigo' : undefined}>{h.cancelados}</strong>
          </div>
          <div>
            <span>Total gasto</span>
            <strong>{moeda(h.totalGasto)}</strong>
          </div>
        </div>

        {proximo?.inicio && (
          <section className="historico-proximo" aria-label="Próximo agendamento">
            <BlocoData data={proximo.inicio} destaque />
            <div className="historico-proximo-textos">
              <span className="texto-apoio">Próximo agendamento, {proximo.inicio.format('dddd')}</span>
              <Atendimento a={proximo} comLocais={comLocais} />
            </div>
            <EtiquetaStatus status={proximo.status} />
          </section>
        )}

        <div className="historico-lista-cabecalho">
          <h4>Agendamentos</h4>
          <Segmented
            size="small"
            value={filtro}
            onChange={setFiltro}
            options={Object.entries(FILTROS).map(([value, label]) => ({ value, label }))}
          />
        </div>
        {!agenda.verEquipe && h.parcial && <p className="historico-aviso texto-apoio">Mostrando só os atendimentos da sua agenda.</p>}

        {/* O erro vem antes: se a troca de filtro falhar, a lista ainda é a do filtro anterior */}
        {h.erro ? (
          <EstadoVazio
            compacto
            titulo="Não foi possível atualizar a lista"
            descricao={h.erro.mensagem}
            acao={<Button onClick={h.recarregar}>Tentar de novo</Button>}
          />
        ) : !h.listaAtual ? (
          <div className="historico-carregando">
            <Skeleton active paragraph={{ rows: 3 }} />
          </div>
        ) : (
          lista.length === 0 && <EstadoVazio compacto titulo="Nenhum agendamento neste filtro" />
        )}

        {h.listaAtual &&
          porMes(lista).map((mes) => (
            <section key={mes.chave} aria-label={dayjs(`${mes.chave}-01`).format('MMMM [de] YYYY')}>
              <h5 className="historico-mes">{capitalizar(dayjs(`${mes.chave}-01`).format('MMMM [de] YYYY'))}</h5>
              <ul className="lista-linhas">
                {mes.itens.map((a) => (
                  <li key={a.id} className={['historico-item', ['cancelado', 'nao_compareceu'].includes(a.status) && 'apagado'].filter(Boolean).join(' ')}>
                    <BlocoData data={a.inicio} />
                    <Atendimento a={a} comLocais={comLocais} />
                    <div className="historico-item-fim">
                      <EtiquetaStatus status={a.status} />
                      {a.preco != null && <span className="texto-apoio">{moeda(a.preco)}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}

        {h.listaAtual && faltam > 0 && (
          <Button type="link" className="historico-mais" loading={h.carregandoMais} onClick={verMais}>
            Ver mais {faltam}
          </Button>
        )}
      </div>
    )
  }

  return (
    <PainelLateral
      titulo="Histórico do cliente"
      nome={cliente ? nomeCompleto(cliente) : undefined}
      semNome={h.carregando ? 'Carregando…' : undefined}
      open={open}
      onClose={onClose}
      largura={560}
      rootClassName="painel-historico"
    >
      {conteudo}
    </PainelLateral>
  )
}
