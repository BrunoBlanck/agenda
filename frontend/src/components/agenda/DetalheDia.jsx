import { Alert, Button, Skeleton, Tooltip } from 'antd'
import { MenuUnfoldOutlined, PlusOutlined } from '@ant-design/icons'
import { capitalizar, duracaoTexto, horaCurta, moeda, plural } from '../../utils/formatos.js'
import { corDe, ehHoje, fimDe, inativo, localDe, passaDaMeiaNoite } from './util.js'
import AceiteSolicitacao from '../AceiteSolicitacao.jsx'
import LocalInfo from '../LocalInfo.jsx'
import EstadoVazio from '../base/EstadoVazio.jsx'
import { EtiquetaStatus } from '../Etiquetas.jsx'

// Painel lateral: os atendimentos do dia selecionado, em ordem de horário.
// onRespondido: depois de aceitar/recusar um pedido do site (a tela recarrega a agenda).
// carregando: a agenda do período ainda não chegou (linhas cinza no lugar da lista).
export default function DetalheDia({ dia, agendamentos, bloqueios, podeCriar, podeEditar, comServicos, comLocais, onNovo, onAbrir, onFechar, onRespondido, destaqueId, carregando = false }) {
  const lista = [...agendamentos].sort((a, b) => (a.inicio ?? '').localeCompare(b.inicio ?? ''))
  const ativos = lista.filter((a) => !inativo(a))
  const minutos = ativos.reduce((t, a) => t + (a.duracao ?? 0), 0)
  const total = ativos.reduce((t, a) => t + (a.preco ?? 0), 0)

  const resumo = ativos.length
    ? `${plural(ativos.length, 'atendimento', 'atendimentos')} em ${duracaoTexto(minutos)}${total > 0 ? `, ${moeda(total)}` : ''}`
    : 'Nenhum atendimento'

  return (
    <aside className="agenda-dia" aria-label="Atendimentos do dia">
      <div className="agenda-dia-cabecalho">
        <div>
          <h2>
            {capitalizar(dia.format('dddd, D [de] MMMM'))}
            {ehHoje(dia) && <span className="marca-texto">hoje</span>}
          </h2>
          {carregando ? <Skeleton.Input active size="small" className="agenda-dia-resumo-carregando" /> : <p>{resumo}</p>}
        </div>
        {onFechar && (
          <Tooltip title="Recolher e ampliar o calendário" rootClassName="dica-icone">
            <Button type="text" icon={<MenuUnfoldOutlined />} aria-label="Recolher painel do dia" onClick={onFechar} />
          </Tooltip>
        )}
      </div>

      <div className="agenda-dia-corpo">
        {podeCriar && (
          <Button block icon={<PlusOutlined />} onClick={onNovo}>
            Agendar neste dia
          </Button>
        )}

        {!carregando && bloqueios.map((b) => (
          <Alert
            key={b.id}
            type="warning"
            showIcon
            title={b.quem == null ? `Loja fechada: ${b.motivo}` : `${b.quem} indisponível: ${b.motivo}`}
          />
        ))}

        {carregando ? (
          <div aria-busy="true" aria-label="Carregando os atendimentos do dia">
            <Skeleton active title={false} paragraph={{ rows: 3 }} />
            <Skeleton active title={false} paragraph={{ rows: 3 }} />
          </div>
        ) : lista.length === 0 ? (
          <EstadoVazio compacto titulo="Dia livre" descricao={podeCriar ? 'Clique num horário da grade para agendar.' : undefined} />
        ) : (
          <ul className="agenda-dia-lista">
            {lista.map((a) => (
              <li
                key={a.id}
                className={['agenda-item', inativo(a) && 'inativo', a.id === destaqueId && 'em-edicao'].filter(Boolean).join(' ')}
                style={{ '--cor-profissional': corDe(a) }}
              >
                <div className="agenda-item-topo">
                  <span className="agenda-item-hora">
                    {horaCurta(a.hora)} às {horaCurta(fimDe(a))}
                    {passaDaMeiaNoite(a) && ' do dia seguinte'}
                  </span>
                  <EtiquetaStatus status={a.status} />
                </div>
                <button type="button" className="agenda-item-cliente" onClick={() => onAbrir(a)}>
                  {a.clienteNome ?? '—'}
                </button>
                <div className="agenda-item-detalhes">
                  <span>{comServicos ? (a.servicoNome ?? 'Atendimento') : duracaoTexto(a.duracao)}</span>
                  {a.preco != null && <span>{moeda(a.preco)}</span>}
                </div>
                <div className="agenda-item-detalhes">
                  <span>{a.funcionarioNome ?? '—'}</span>
                  {comLocais && <LocalInfo local={localDe(a)} />}
                </div>
                {a.status === 'pendente' && podeEditar(a) && (
                  <div className="agenda-item-acoes">
                    <AceiteSolicitacao agendamento={a} onRespondido={onRespondido} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
