import { Button, Skeleton } from 'antd'
import { CalendarOutlined, DisconnectOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAcesso } from '../data/useAcesso.js'
import { useInicio } from '../data/useInicio.js'
import { agoraNaLoja, lerData } from '../data/api/conversao.js'
import { capitalizar, horaCurta, plural } from '../utils/formatos.js'
import { COR_PADRAO, corDe, fimDe, inativo } from '../components/agenda/util.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import { EtiquetaStatus } from '../components/Etiquetas.jsx'
import AceiteSolicitacao from '../components/AceiteSolicitacao.jsx'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'
import { usePainelPath } from '../layout/caminhos.js'

// "desde 9h" para quem entrou hoje; com a data para entrada aberta desde outro dia (esqueceu de sair).
// entradaEm (dayjs, hora da loja) dá a data exata da entrada
function desde(p, hoje) {
  if (!p.entradaEm?.isValid?.()) return p.entrada ? `desde ${horaCurta(p.entrada)}` : null
  const hora = horaCurta(p.entradaEm.format('HH:mm'))
  if (p.entradaEm.isSame(hoje, 'day')) return `desde ${hora}`
  if (p.entradaEm.isSame(hoje.subtract(1, 'day'), 'day')) return `desde ontem, ${hora}`
  return `desde ${p.entradaEm.format('DD/MM')}, ${hora}`
}

// "Dra. Ana Souza" -> "Ana" (pula tratamentos abreviados como Dr., Dra., Sr.)
const primeiroNome = (nome) => {
  const partes = (nome ?? '').split(' ').filter(Boolean)
  return partes.find((p) => !p.endsWith('.')) ?? partes[0] ?? ''
}

// Enquanto o resumo chega: linhas no formato da lista (sem spinner)
function CarregandoLinhas({ linhas = 3 }) {
  return (
    <div className="carregando-linhas" aria-busy="true" aria-label="Carregando">
      <Skeleton active title={false} paragraph={{ rows: linhas, width: '100%' }} />
    </div>
  )
}

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const qtd = (n) => numero.format(Number(n) || 0)

// Início: o que a recepção (ou o profissional) precisa resolver agora.
// Cada bloco vem do servidor (GET /api/loja/inicio) e só aparece se o usuário tiver acesso:
// bloco null = sem acesso (o servidor decide; useAcesso só adianta o formato enquanto carrega).
export default function Dashboard() {
  const { pode, agenda, moduloAtivo, usuario } = useAcesso()
  const { resumo: dados, carregando, erro, recarregar } = useInicio()
  const navigate = useNavigate()
  const caminho = usePainelPath()
  const painel = usePainel()
  const agora = agoraNaLoja()
  const hoje = dados?.data ?? agora

  const verAgenda = dados ? dados.agendaHoje != null : pode('agenda_propria') || pode('agenda_equipe')
  const verMateriais = dados ? dados.materiaisARepor != null : pode('materiais')
  const verEquipe = dados ? dados.equipeEmServico != null : pode('ponto_equipe')
  const verClientes = dados ? dados.clientesCadastrados != null : pode('clientes')
  const comServicos = moduloAtivo('servicos')
  const soPropria = dados ? dados.soPropria : !agenda.verEquipe

  const agendaHoje = dados?.agendaHoje ?? []
  const ativosHoje = agendaHoje.filter((a) => !inativo(a))
  const horaAgora = agora.format('HH:mm')
  const proximo = hoje.isSame(agora, 'day') ? ativosHoje.find((a) => a.hora >= horaAgora) : null
  const pendentes = dados?.solicitacoesSite ?? []
  const emServico = dados?.equipeEmServico ?? []
  const aRepor = dados?.materiaisARepor ?? []

  const resumo =
    verAgenda && dados
      ? [
          ativosHoje.length ? plural(ativosHoje.length, 'atendimento hoje', 'atendimentos hoje') : 'Nenhum atendimento hoje',
          proximo && `o próximo às ${horaCurta(proximo.hora)} com ${proximo.clienteNome ?? 'cliente'}`,
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
        <span className={a.hora < horaAgora ? 'texto-apoio sem-quebra' : 'sem-quebra'}>
          {horaCurta(a.hora)} às {horaCurta(fimDe(a))}
        </span>
      ),
    },
    { title: 'Cliente', dataIndex: 'clienteNome', render: (nome) => <strong>{nome ?? '—'}</strong> },
    comServicos && { title: 'Serviço', dataIndex: 'servicoNome', render: (nome) => nome ?? '—' },
    !soPropria && {
      title: 'Profissional',
      key: 'profissional',
      render: (_, a) => (
        <span className="com-ponto">
          <PontoCor cor={corDe(a)} /> {a.funcionarioNome ?? '—'}
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
      render: (_, a) => (a.data ? `${capitalizar(lerData(a.data).format('ddd DD/MM'))}, ${horaCurta(a.hora)}` : '—'),
    },
    { title: 'Cliente', dataIndex: 'clienteNome', render: (nome) => <strong>{nome ?? '—'}</strong> },
    comServicos && { title: 'Serviço', dataIndex: 'servicoNome', render: (nome) => nome ?? '—' },
    !soPropria && { title: 'Profissional', dataIndex: 'funcionarioNome', render: (nome) => nome ?? '—' },
    {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      align: 'right',
      render: (_, a) =>
        agenda.editar(a) ? <AceiteSolicitacao agendamento={a} onRespondido={recarregar} /> : <EtiquetaStatus status="pendente" />,
    },
  ].filter(Boolean)

  const lateral = verEquipe || verMateriais || verClientes

  if (erro && !dados) {
    return (
      <Pagina titulo={capitalizar(agora.format('dddd, D [de] MMMM'))}>
        <Secao>
          <EstadoVazio
            icone={<DisconnectOutlined />}
            titulo="Não foi possível carregar o resumo do dia"
            descricao={erro.mensagem}
            acao={<Button onClick={recarregar}>Tentar de novo</Button>}
          />
        </Secao>
      </Pagina>
    )
  }

  return (
    <Pagina
      titulo={capitalizar(hoje.format('dddd, D [de] MMMM'))}
      descricao={resumo ?? `Olá, ${primeiroNome(usuario?.nome)}.`}
      acoes={
        verAgenda && (
          <>
            <Button icon={<CalendarOutlined />} onClick={() => navigate(caminho('/agenda'))}>
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
          <Secao rente titulo={soPropria ? 'Minha agenda de hoje' : 'Agenda de hoje'}>
            {carregando ? (
              <CarregandoLinhas linhas={5} />
            ) : (
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
            )}
          </Secao>
        )}

        {lateral && (
          <div className="pilha">
            {verEquipe && (
              <Secao titulo="Equipe em serviço" descricao="Quem registrou entrada e ainda não saiu.">
                {carregando ? (
                  <CarregandoLinhas linhas={2} />
                ) : emServico.length ? (
                  <ul className="lista-linhas lista-compacta">
                    {emServico.map((p) => (
                      <li key={p.id}>
                        <span className="com-ponto">
                          <PontoCor cor={p.cor ?? COR_PADRAO} /> {p.nome}
                        </span>
                        {desde(p, hoje) && <span className="texto-apoio numeros">{desde(p, hoje)}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EstadoVazio compacto titulo="Ninguém em serviço agora" />
                )}
              </Secao>
            )}

            {verMateriais && (
              <Secao
                titulo="Estoque a repor"
                acoes={
                  <Button type="link" size="small" onClick={() => navigate(caminho('/materiais'))}>
                    Ver materiais
                  </Button>
                }
              >
                {carregando ? (
                  <CarregandoLinhas linhas={2} />
                ) : aRepor.length ? (
                  <ul className="lista-linhas lista-compacta">
                    {aRepor.map((m) => (
                      <li key={m.id}>
                        <span>{m.nome}</span>
                        <span className="numeros">
                          <span className="marca-texto">{qtd(m.quantidade)}</span>
                          <span className="texto-apoio">
                            {' '}
                            de {qtd(m.minimo)} {m.unidade}
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

            {verClientes && (
              <Secao
                titulo="Clientes"
                acoes={
                  <Button type="link" size="small" onClick={() => navigate(caminho('/clientes'))}>
                    Ver clientes
                  </Button>
                }
              >
                {dados ? (
                  <p className="texto-ajuda numeros">{plural(dados.clientesCadastrados ?? 0, 'cliente cadastrado', 'clientes cadastrados')}</p>
                ) : (
                  <CarregandoLinhas linhas={1} />
                )}
              </Secao>
            )}
          </div>
        )}
      </div>

      <AgendamentoPainel
        open={painel.aberto}
        agendamento={painel.registro?.id ? painel.registro : null}
        dataInicial={hoje}
        onClose={painel.fechar}
        onSalvo={recarregar}
      />
    </Pagina>
  )
}
