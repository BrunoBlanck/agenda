import { Button } from 'antd'
import { CalendarOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useNomes } from '../data/useNomes.js'
import { capitalizar, horaCurta, plural } from '../utils/formatos.js'
import { fimDe, inativo } from '../components/agenda/util.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import { EtiquetaStatus } from '../components/Etiquetas.jsx'
import AceiteSolicitacao from '../components/AceiteSolicitacao.jsx'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'

const chaveData = (a) => `${a.data} ${a.hora}`

// Início: o que a recepção (ou o profissional) precisa resolver agora.
// Cada bloco só aparece se o usuário tiver acesso ao recurso correspondente.
export default function Dashboard() {
  const { agendamentos, materiais, pontos } = useData()
  const { pode, agenda, moduloAtivo, usuario } = useAcesso()
  const nomes = useNomes()
  const navigate = useNavigate()
  const painel = usePainel()
  const agora = dayjs()
  const hoje = agora.format('YYYY-MM-DD')

  const verAgenda = pode('agenda_propria') || pode('agenda_equipe')
  const verMateriais = pode('materiais')
  const verEquipe = pode('ponto_equipe')
  const comServicos = moduloAtivo('servicos')

  const agendaHoje = agendamentos.itens.filter((a) => a.data === hoje && agenda.ver(a)).sort((a, b) => a.hora.localeCompare(b.hora))
  const ativosHoje = agendaHoje.filter((a) => !inativo(a))
  const proximo = ativosHoje.find((a) => a.hora >= agora.format('HH:mm'))
  const pendentes = agendamentos.itens.filter((a) => a.status === 'pendente' && agenda.ver(a)).sort((a, b) => chaveData(a).localeCompare(chaveData(b)))
  const emServico = pontos.itens.filter((p) => p.data === hoje && !p.saida)
  const aRepor = materiais.itens.filter((m) => m.quantidade < m.minimo).sort((a, b) => a.quantidade / a.minimo - b.quantidade / b.minimo)

  const resumo = verAgenda
    ? [
        ativosHoje.length ? plural(ativosHoje.length, 'atendimento hoje', 'atendimentos hoje') : 'Nenhum atendimento hoje',
        proximo && `o próximo às ${horaCurta(proximo.hora)} com ${nomes.cliente(proximo.clienteId)}`,
      ]
        .filter(Boolean)
        .join(', ') + '.'
    : undefined

  const colunasHoje = [
    {
      title: 'Horário',
      key: 'hora',
      width: 120,
      render: (_, a) => (
        <span className={a.hora < agora.format('HH:mm') ? 'texto-apoio sem-quebra' : 'sem-quebra'}>
          {horaCurta(a.hora)} às {horaCurta(fimDe(a))}
        </span>
      ),
    },
    { title: 'Cliente', dataIndex: 'clienteId', render: (id) => <strong>{nomes.cliente(id)}</strong> },
    comServicos && { title: 'Serviço', dataIndex: 'servicoId', render: nomes.servico },
    agenda.verEquipe && {
      title: 'Profissional',
      dataIndex: 'funcionarioId',
      render: (id) => (
        <span className="com-ponto">
          <PontoCor cor={nomes.corDe(id)} /> {nomes.profissional(id)}
        </span>
      ),
    },
    { title: 'Situação', dataIndex: 'status', render: (s) => <EtiquetaStatus status={s} /> },
  ].filter(Boolean)

  const colunasPendentes = [
    {
      title: 'Quando',
      key: 'quando',
      width: 150,
      render: (_, a) => `${capitalizar(dayjs(a.data).format('ddd DD/MM'))}, ${horaCurta(a.hora)}`,
    },
    { title: 'Cliente', dataIndex: 'clienteId', render: (id) => <strong>{nomes.cliente(id)}</strong> },
    comServicos && { title: 'Serviço', dataIndex: 'servicoId', render: nomes.servico },
    agenda.verEquipe && { title: 'Profissional', dataIndex: 'funcionarioId', render: nomes.profissional },
    {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      align: 'right',
      render: (_, a) => (agenda.editar(a) ? <AceiteSolicitacao agendamento={a} /> : <EtiquetaStatus status="pendente" />),
    },
  ].filter(Boolean)

  const lateral = verEquipe || verMateriais

  return (
    <Pagina
      titulo={capitalizar(agora.format('dddd, D [de] MMMM'))}
      descricao={resumo ?? `Olá, ${usuario?.nome?.split(' ')[0] ?? ''}.`}
      acoes={
        verAgenda && (
          <>
            <Button icon={<CalendarOutlined />} onClick={() => navigate('/painel/agenda')}>
              Abrir agenda
            </Button>
            {agenda.criar && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => painel.abrir({})}>
                Agendar
              </Button>
            )}
          </>
        )
      }
    >
      {pendentes.length > 0 && (
        <Secao
          rente
          titulo={
            <>
              Solicitações do site <span className="marca-texto">{pendentes.length}</span>
            </>
          }
          descricao="Clientes que pediram horário pelo site. Aceite para confirmar ou recuse para liberar o horário."
        >
          <Tabela columns={colunasPendentes} dataSource={pendentes} pagination={false} />
        </Secao>
      )}

      <div className={verAgenda && lateral ? 'grade-principal' : 'pilha'}>
        {verAgenda && (
          <Secao rente titulo={agenda.verEquipe ? 'Agenda de hoje' : 'Minha agenda de hoje'}>
            <Tabela
              columns={colunasHoje}
              dataSource={agendaHoje}
              pagination={false}
              rowClassName={(a) => (inativo(a) ? 'linha-clicavel linha-apagada' : 'linha-clicavel')}
              onRow={(a) => ({ onClick: () => painel.abrir(a) })}
              destaqueId={painel.destaqueId}
              vazio={
                <EstadoVazio
                  titulo="Nenhum atendimento hoje"
                  descricao="Os horários marcados para hoje aparecem aqui."
                  acao={agenda.criar && <Button onClick={() => painel.abrir({})}>Agendar horário</Button>}
                />
              }
            />
          </Secao>
        )}

        {lateral && (
          <div className="pilha">
            {verEquipe && (
              <Secao titulo="Equipe em serviço" descricao="Quem registrou entrada hoje e ainda não saiu.">
                {emServico.length ? (
                  <ul className="lista-linhas lista-compacta">
                    {emServico.map((p) => (
                      <li key={p.id}>
                        <span className="com-ponto">
                          <PontoCor cor={nomes.corDe(p.funcionarioId)} /> {nomes.profissional(p.funcionarioId)}
                        </span>
                        <span className="texto-apoio numeros">desde {horaCurta(p.entrada)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EstadoVazio compacto titulo="Ninguém registrou entrada hoje" />
                )}
              </Secao>
            )}

            {verMateriais && (
              <Secao
                titulo="Estoque a repor"
                acoes={
                  <Button type="link" size="small" onClick={() => navigate('/painel/materiais')}>
                    Ver materiais
                  </Button>
                }
              >
                {aRepor.length ? (
                  <ul className="lista-linhas lista-compacta">
                    {aRepor.map((m) => (
                      <li key={m.id}>
                        <span>{m.nome}</span>
                        <span className="numeros">
                          <span className="marca-texto">{m.quantidade}</span>
                          <span className="texto-apoio">
                            {' '}
                            de {m.minimo} {m.unidade}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EstadoVazio compacto titulo="Estoque em dia" descricao="Nenhum material abaixo do mínimo." />
                )}
              </Secao>
            )}
          </div>
        )}
      </div>

      <AgendamentoPainel
        open={painel.aberto}
        agendamento={painel.registro?.id ? painel.registro : null}
        onClose={painel.fechar}
      />
    </Pagina>
  )
}
