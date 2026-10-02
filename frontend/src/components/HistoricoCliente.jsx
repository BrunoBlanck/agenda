import { useState } from 'react'
import { Button, Segmented } from 'antd'
import { EnvironmentOutlined, MailOutlined, PhoneOutlined, VideoCameraOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useNomes } from '../data/useNomes.js'
import { inicioDe, useHistoricoCliente } from '../data/useHistoricoCliente.js'
import { capitalizar, dataBR, horaCurta, moeda, nomeCompleto } from '../utils/formatos.js'
import { fimDe } from './agenda/util.js'
import { IconesCanais } from './CanaisCliente.jsx'
import { EtiquetaStatus } from './Etiquetas.jsx'
import PontoCor from './base/PontoCor.jsx'
import EstadoVazio from './base/EstadoVazio.jsx'
import PainelLateral from './base/PainelLateral.jsx'
import './historico-cliente.css'

const POR_PAGINA = 10

const FILTROS = {
  todos: { label: 'Todos', aceita: () => true },
  concluidos: { label: 'Concluídos', aceita: (a) => a.status === 'concluido' },
  faltas: { label: 'Faltas e cancelados', aceita: (a) => ['nao_compareceu', 'cancelado'].includes(a.status) },
}

const haQuanto = (data) => {
  const dias = dayjs().startOf('day').diff(dayjs(data).startOf('day'), 'day')
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
  const nomes = useNomes()
  const local = comLocais && a.localId && nomes.local(a.localId)
  return (
    <div className="atendimento-textos">
      <strong className={a.status === 'cancelado' ? 'riscado' : undefined}>{nomes.servico(a.servicoId)}</strong>
      <span>
        {dataBR(a.data)}, {horaCurta(a.hora)} às {horaCurta(fimDe(a))}
      </span>
      <span className="atendimento-quem">
        <span>
          <PontoCor cor={nomes.corDe(a.funcionarioId)} /> {nomes.profissional(a.funcionarioId)}
        </span>
        {local && (
          <span>
            {local.tipo === 'online' ? <VideoCameraOutlined aria-hidden="true" /> : <EnvironmentOutlined aria-hidden="true" />} {local.nome}
          </span>
        )}
      </span>
      {a.motivoCancelamento && <em>{a.motivoCancelamento}</em>}
    </div>
  )
}

// Histórico do cliente: resumo e os agendamentos dele, do mais recente para o mais antigo.
export default function HistoricoCliente({ clienteId, open, onClose }) {
  const { clientes } = useData()
  const { agenda, moduloAtivo } = useAcesso()
  const cliente = clientes.todos.find((c) => c.id === clienteId)
  const { visiveis, parcial, concluidos, faltas, cancelados, ultimo, proximo } = useHistoricoCliente(clienteId)
  const [filtro, setFiltro] = useState('todos')
  const [limite, setLimite] = useState(POR_PAGINA)
  // Cada abertura começa com todos os agendamentos e a primeira página
  const [abertoAntes, setAbertoAntes] = useState(open)
  if (open !== abertoAntes) {
    setAbertoAntes(open)
    if (open) {
      setFiltro('todos')
      setLimite(POR_PAGINA)
    }
  }
  const comLocais = moduloAtivo('locais')

  const gasto = visiveis.filter((a) => a.status === 'concluido').reduce((t, a) => t + (a.preco ?? 0), 0)
  const lista = visiveis.filter(FILTROS[filtro].aceita)

  return (
    <PainelLateral
      titulo="Histórico do cliente"
      nome={cliente && nomeCompleto(cliente)}
      open={open}
      onClose={onClose}
      largura={560}
      rootClassName="painel-historico"
    >
      {cliente && (
        <div className="historico">
          {/* Nome e iniciais ficam no cabeçalho do painel; aqui, como falar com o cliente */}
          <div className="historico-cliente">
            <div className="historico-contato">
              <span>
                <PhoneOutlined aria-hidden="true" /> {cliente.telefone}
              </span>
              {cliente.email && (
                <span>
                  <MailOutlined aria-hidden="true" /> {cliente.email}
                </span>
              )}
              <IconesCanais canais={cliente.canais} />
            </div>
            <span className="texto-apoio">
              {ultimo ? `Último atendimento ${haQuanto(ultimo.data)} (${dataBR(ultimo.data)})` : 'Ainda sem atendimentos concluídos'}
            </span>
          </div>

          {cliente.observacoes && <p className="historico-observacoes">{cliente.observacoes}</p>}

          <div className="numeros-resumo historico-numeros">
            <div>
              <span>Atendimentos</span>
              <strong>{concluidos}</strong>
            </div>
            <div>
              <span>Faltas</span>
              <strong className={faltas ? 'tom-atencao' : undefined}>{faltas}</strong>
            </div>
            <div>
              <span>Cancelados</span>
              <strong className={cancelados ? 'tom-perigo' : undefined}>{cancelados}</strong>
            </div>
            <div>
              <span>Total gasto</span>
              <strong>{moeda(gasto)}</strong>
            </div>
          </div>

          {proximo && (
            <section className="historico-proximo" aria-label="Próximo agendamento">
              <BlocoData data={inicioDe(proximo)} destaque />
              <div className="historico-proximo-textos">
                <span className="texto-apoio">Próximo agendamento, {inicioDe(proximo).format('dddd')}</span>
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
              onChange={(v) => {
                setFiltro(v)
                setLimite(POR_PAGINA)
              }}
              options={Object.entries(FILTROS).map(([value, f]) => ({ value, label: f.label }))}
            />
          </div>
          {!agenda.verEquipe && parcial && <p className="historico-aviso texto-apoio">Mostrando só os atendimentos da sua agenda.</p>}

          {lista.length === 0 && <EstadoVazio compacto titulo="Nenhum agendamento neste filtro" />}

          {porMes(lista.slice(0, limite)).map((mes) => (
            <section key={mes.chave} aria-label={dayjs(`${mes.chave}-01`).format('MMMM [de] YYYY')}>
              <h5 className="historico-mes">{capitalizar(dayjs(`${mes.chave}-01`).format('MMMM [de] YYYY'))}</h5>
              <ul className="lista-linhas">
                {mes.itens.map((a) => (
                  <li key={a.id} className={['historico-item', ['cancelado', 'nao_compareceu'].includes(a.status) && 'apagado'].filter(Boolean).join(' ')}>
                    <BlocoData data={inicioDe(a)} />
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

          {lista.length > limite && (
            <Button type="link" className="historico-mais" onClick={() => setLimite((n) => n + POR_PAGINA)}>
              Ver mais {lista.length - limite}
            </Button>
          )}
        </div>
      )}
    </PainelLateral>
  )
}
