import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Avatar,
  Button,
  Checkbox,
  Col,
  ConfigProvider,
  Empty,
  Flex,
  Form,
  Input,
  Result,
  Row,
  Select,
  Skeleton,
  Spin,
  Steps,
} from 'antd'
import {
  ArrowLeftOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  PhoneOutlined,
  VideoCameraOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { tiposLoja } from '../data/dominio.js'
import { foiCancelada } from '../data/api/cliente.js'
import { lerData } from '../data/api/conversao.js'
import { buscarHorariosSite, hojeNaLoja, pedirAgendamentoSite, somarDias } from '../data/api/site.js'
import { capitalizar, duracaoTexto, mascaraTelefone, moeda, soDigitos } from '../utils/formatos.js'
import { temasSite } from '../tema.js'
import { useHorariosSite, useLocaisSite, useLojaPublica } from './useSite.js'
import './site.css'

const DIAS_A_FRENTE = 14 // uma consulta só ao servidor (limite: 31 dias)
const QUALQUER = 'qualquer'
const CAMPOS_CLIENTE = ['nome', 'sobrenome', 'telefone', 'email', 'observacoes']

// Por enquanto o tipo da loja muda só os textos deste site de exemplo. No sistema real cada tipo
// terá o próprio site (layout e fluxo), escolhido pelo código do tipo (estrutura.md, 1.2)
const termosPorTipo = {
  clinica: { profissional: 'Profissional', servico: 'Serviço', nenhum: 'Nenhum serviço', chamada: 'Agende sua consulta' },
  barbearia: { profissional: 'Barbeiro', servico: 'Serviço', nenhum: 'Nenhum serviço', chamada: 'Agende seu horário' },
  escola: { profissional: 'Professor', servico: 'Aula', nenhum: 'Nenhuma aula', chamada: 'Agende sua aula' },
}

const enderecoDe = (loja) =>
  [
    loja.logradouro && [loja.logradouro, loja.numero].filter(Boolean).join(', '),
    loja.complemento,
    loja.bairro,
    [loja.cidade, loja.uf].filter(Boolean).join('/'),
  ]
    .filter(Boolean)
    .join(', ')

const mesmoHorario = (a, b) =>
  Boolean(a && b) &&
  a.inicio === b.inicio &&
  a.funcionarioId === b.funcionarioId &&
  (a.local?.id ?? null) === (b.local?.id ?? null)

// Segundos do Retry-After em texto curto ("40 s", "12 min")
const tempoEspera = (s) => (s > 60 ? `${Math.ceil(s / 60)} min` : `${s} s`)

// Site do consumidor final (protótipo, /site/:slug): escolhe o serviço, vê os horários livres
// (calculados pelo servidor), informa os dados e o pedido entra no painel da loja como "Aguardando aceite".
export default function SiteLoja() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const site = useLojaPublica(slug)
  const loja = site.erro ? null : site.loja
  const termos = termosPorTipo[loja?.tipo] ?? termosPorTipo.clinica
  const temaSite = temasSite[loja?.tipo] ?? temasSite.clinica
  const nome = loja?.nomeFantasia ?? 'Agendamento online'
  const endereco = loja ? enderecoDe(loja) : ''

  let conteudo
  if (site.erro?.status === 404) {
    conteudo = (
      <Result
        status="warning"
        title="Agendamento online indisponível"
        subTitle="Confira o endereço ou entre em contato com a loja pelo telefone."
      />
    )
  } else if (site.erro) {
    conteudo = (
      <Result
        status="error"
        title="Não foi possível abrir o agendamento online"
        subTitle={site.erro.mensagem}
        extra={
          <Button type="primary" onClick={site.recarregar}>
            Tentar de novo
          </Button>
        }
      />
    )
  } else if (!loja) {
    conteudo = <Skeleton active paragraph={{ rows: 6 }} />
  } else {
    conteudo = <Fluxo key={loja.slug} slug={slug} loja={loja} servicos={site.servicos} termos={termos} aoRecarregar={site.recarregar} />
  }

  return (
    <ConfigProvider theme={{ token: { colorPrimary: temaSite.cor, colorLink: temaSite.cor } }}>
    <div className="site" data-tipo={loja?.tipo} style={{ '--site-cor': temaSite.cor, '--site-topo': temaSite.topo }}>
      <title>{loja ? `${nome}: ${termos.chamada.toLowerCase()}` : nome}</title>
      <header className="site-topo">
        <div className="site-marca">
          <Avatar shape="square" size={36} src={loja?.logoUrl || undefined} className="site-logo">
            {nome.charAt(0)}
          </Avatar>
          <strong>{nome}</strong>
        </div>
        <Flex align="center" gap={8}>
          <span className="site-aviso">Protótipo</span>
          <Button type="text" onClick={() => navigate('/painel')}>
            Área da loja
          </Button>
        </Flex>
      </header>

      <section className="site-capa">
        <div className="site-conteudo">
          {loja && (
            <>
              {tiposLoja[loja.tipo] && <span className="site-tipo">{tiposLoja[loja.tipo].nome}</span>}
              <h1>{nome}</h1>
              <p>{termos.chamada} online, em poucos passos.</p>
              <div className="site-contato">
                {endereco && (
                  <span>
                    <EnvironmentOutlined /> {endereco}
                  </span>
                )}
                {loja.telefone && (
                  <span>
                    <PhoneOutlined /> {loja.telefone}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      <main className="site-conteudo site-principal">
        <div className="site-cartao">{conteudo}</div>
      </main>

      <footer className="site-rodape">
        {loja && (
          <p>
            {nome}
            {endereco && `, ${endereco}`}
          </p>
        )}
        <p>Protótipo do site de agendamento. A versão final será gerada pelo servidor.</p>
      </footer>
    </div>
    </ConfigProvider>
  )
}

function Fluxo({ slug, loja, servicos, termos, aoRecarregar }) {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [hoje] = useState(() => hojeNaLoja(loja.fusoHorario))
  const [etapa, setEtapa] = useState(0)
  const [servicoChave, setServicoChave] = useState(null)
  const [profissional, setProfissional] = useState(QUALQUER)
  const [localId, setLocalId] = useState(QUALQUER)
  const [dia, setDia] = useState(null) // "AAAA-MM-DD" (dia da loja)
  const [horario, setHorario] = useState(null) // um dos horários devolvidos pela API
  const [aviso, setAviso] = useState(null) // { etapa, mensagem }: falha do pedido, mostrada na etapa
  const [enviando, setEnviando] = useState(false)
  const [espera, setEspera] = useState(0) // 429: segundos até poder pedir de novo
  const [pedido, setPedido] = useState(null) // resposta do servidor ao pedido

  const servico = servicos.find((s) => s.chave === servicoChave) ?? null
  const filtros = {
    servicoId: servico?.id ?? null,
    funcionarioId: profissional === QUALQUER ? null : profissional,
    localId: localId === QUALQUER ? null : localId,
    inicio: hoje,
    fim: somarDias(hoje, DIAS_A_FRENTE - 1),
  }
  const escolhendo = Boolean(servico) && (etapa === 1 || etapa === 2)
  const { locais } = useLocaisSite(slug, servico?.id ?? null, loja.usaLocais && escolhendo)
  const horarios = useHorariosSite(slug, filtros, escolhendo)
  const livresDoDia = horarios.dias.find((d) => d.data === dia)?.horarios ?? []
  const dataDia = lerData(dia)

  useEffect(() => {
    if (espera <= 0) return undefined
    const relogio = setTimeout(() => setEspera((s) => s - 1), 1000)
    return () => clearTimeout(relogio)
  }, [espera])

  const irPara = (proxima) => {
    setAviso(null)
    setEtapa(proxima)
  }

  const escolherServico = (chave) => {
    setServicoChave(chave)
    setProfissional(QUALQUER)
    setLocalId(QUALQUER)
    setDia(null)
    setHorario(null)
    irPara(1)
  }

  // Volta ao começo com a lista de serviços atualizada (serviço ou profissional deixou de existir)
  const voltarAoInicio = (mensagem) => {
    setServicoChave(null)
    setDia(null)
    setHorario(null)
    setEtapa(0)
    setAviso({ etapa: 0, mensagem })
    aoRecarregar()
  }

  const tratarFalha = async (erro) => {
    const { status, mensagem } = erro
    if (status === 404) {
      aoRecarregar() // a loja ficou indisponível: a página mostra o aviso
      return
    }
    if (status === 422) {
      const doCliente = (erro.campos ?? []).filter((c) => CAMPOS_CLIENTE.includes(c.campo))
      if (doCliente.length) {
        form.setFields(doCliente.map((c) => ({ name: c.campo, errors: [c.mensagem] })))
        form.scrollToField(doCliente[0].campo)
        return
      }
      voltarAoInicio(mensagem) // serviço, profissional ou local que não vale mais
      return
    }
    if (status === 429) {
      setEspera(erro.tentarEm ?? 30)
      setAviso({ etapa: 2, mensagem })
      return
    }
    if (status === 409) {
      // Horário (ou local) tomado: recarrega os horários e volta para escolher outro.
      // Se o horário continua livre (ex.: pedidos pendentes deste telefone), fica aqui com a mensagem.
      const dias = await buscarHorariosSite(slug, filtros).catch(() => null)
      if (dias) horarios.definirDados(dias)
      else horarios.recarregar()
      const continuaLivre = dias?.some((d) => d.horarios.some((h) => mesmoHorario(h, horario)))
      if (continuaLivre) {
        setAviso({ etapa: 2, mensagem })
      } else {
        setHorario(null)
        setEtapa(1)
        setAviso({ etapa: 1, mensagem })
      }
      return
    }
    setAviso({ etapa: 2, mensagem }) // sem conexão ou erro do servidor: dá para tentar de novo
  }

  const enviar = async () => {
    if (enviando || espera > 0 || !horario) return
    const valores = await form.validateFields().catch(() => null)
    if (!valores) return
    setAviso(null)
    setEnviando(true)
    try {
      const criado = await pedirAgendamentoSite(slug, { servicoId: servico?.id, horario, cliente: valores })
      setPedido(criado)
      setEtapa(3)
    } catch (erro) {
      if (!foiCancelada(erro)) await tratarFalha(erro)
    } finally {
      setEnviando(false)
    }
  }

  const recomecar = () => {
    form.resetFields()
    setServicoChave(null)
    setProfissional(QUALQUER)
    setLocalId(QUALQUER)
    setDia(null)
    setHorario(null)
    setPedido(null)
    irPara(0)
  }

  const avisoDaEtapa = aviso?.etapa === etapa && (
    <Alert type="error" showIcon title={aviso.mensagem} role="alert" className="site-alerta" />
  )

  const quando = pedido?.inicio
    ? `${capitalizar(pedido.inicio.format('dddd, DD/MM'))} às ${pedido.inicio.format('HH:mm')}${
        pedido.funcionarioNome ? `, com ${pedido.funcionarioNome}` : ''
      }`
    : null

  return (
    <>
      <Steps
        current={etapa}
        size="small"
        responsive={false}
        titlePlacement="vertical"
        className="site-etapas"
        items={[{ title: termos.servico }, { title: 'Horário' }, { title: 'Seus dados' }, { title: 'Pronto' }]}
      />

      {etapa === 0 && (
        <>
          <h2>Escolha {termos.servico === 'Aula' ? 'a aula' : 'o serviço'}</h2>
          {avisoDaEtapa}
          {servicos.length === 0 ? (
            <Empty
              description={`${termos.nenhum} disponível para agendamento online no momento.${
                loja.telefone ? ` Ligue para ${loja.telefone}.` : ''
              }`}
            />
          ) : (
            <Row gutter={[16, 16]}>
              {servicos.map((s) => (
                <Col key={s.chave} xs={24} sm={12}>
                  <button type="button" className="site-opcao" onClick={() => escolherServico(s.chave)}>
                    <strong>{s.nome}</strong>
                    {s.descricao && <span className="site-descricao">{s.descricao}</span>}
                    <span>
                      <ClockCircleOutlined /> {duracaoTexto(s.duracao)}
                    </span>
                    {s.preco != null && <span className="site-preco">{moeda(s.preco)}</span>}
                  </button>
                </Col>
              ))}
            </Row>
          )}
        </>
      )}

      {etapa === 1 && servico && (
        <>
          <div className="site-servico-escolhido">
            <h2>
              {servico.nome}, {duracaoTexto(servico.duracao)}
            </h2>
            <Flex wrap gap={12} className="site-filtros">
              <Select
                aria-label={termos.profissional}
                value={profissional}
                onChange={(v) => {
                  setProfissional(v)
                  setHorario(null)
                  setAviso(null)
                }}
                options={[
                  { value: QUALQUER, label: `Qualquer ${termos.profissional.toLowerCase()}` },
                  ...servico.profissionais.map((f) => ({
                    value: f.id,
                    label: (
                      <Flex align="center" gap={8}>
                        <span className="site-cor-profissional" style={f.cor ? { background: f.cor } : undefined} />
                        {f.nome}
                      </Flex>
                    ),
                  })),
                ]}
              />
              {locais.length > 1 && (
                <Select
                  aria-label={loja.rotuloLocal}
                  value={localId}
                  onChange={(v) => {
                    setLocalId(v)
                    setHorario(null)
                    setAviso(null)
                  }}
                  options={[
                    { value: QUALQUER, label: `Qualquer ${loja.rotuloLocal.toLowerCase()}` },
                    ...locais.map((l) => ({
                      value: l.id,
                      label: (
                        <Flex align="center" gap={8}>
                          {l.tipo === 'online' ? <VideoCameraOutlined /> : <EnvironmentOutlined />}
                          {l.nome}
                        </Flex>
                      ),
                    })),
                  ]}
                />
              )}
            </Flex>
          </div>

          {avisoDaEtapa}

          {horarios.erro ? (
            <Alert
              type="error"
              showIcon
              title={horarios.erro.mensagem}
              className="site-alerta"
              action={
                <Button size="small" onClick={horarios.recarregar}>
                  Tentar de novo
                </Button>
              }
            />
          ) : horarios.carregando ? (
            <Skeleton active title={false} paragraph={{ rows: 3 }} />
          ) : (
            <Spin spinning={horarios.atualizando} delay={200}>
              <span className="site-rotulo">Escolha o dia</span>
              <div className="site-dias">
                {horarios.dias.map((d) => {
                  const total = d.horarios.length
                  const data = lerData(d.data)
                  return (
                    <button
                      key={d.data}
                      type="button"
                      disabled={total === 0}
                      className={['site-dia', d.data === dia && 'ativo'].filter(Boolean).join(' ')}
                      onClick={() => {
                        setDia(d.data)
                        setHorario(null)
                      }}
                    >
                      <span>{d.data === hoje ? 'Hoje' : capitalizar(data?.format('ddd') ?? '')}</span>
                      <strong>{data?.format('DD/MM') ?? d.data}</strong>
                      <small>{total ? `${total} ${total === 1 ? 'horário' : 'horários'}` : 'Sem horários'}</small>
                    </button>
                  )
                })}
              </div>

              {horarios.dias.length > 0 && horarios.dias.every((d) => d.horarios.length === 0) && (
                <Empty description="Nenhum horário livre nos próximos dias. Tente outra opção acima." />
              )}

              {dataDia && (
                <>
                  <span className="site-rotulo">Horários livres em {dataDia.format('DD/MM')}</span>
                  {livresDoDia.length === 0 ? (
                    <Empty description="Nenhum horário livre neste dia" />
                  ) : (
                    <div className="site-horarios">
                      {livresDoDia.map((h) => (
                        <Button
                          key={`${h.inicio}-${h.funcionarioId}`}
                          type={horario?.inicio === h.inicio ? 'primary' : 'default'}
                          onClick={() => {
                            setHorario(h)
                            setAviso(null)
                          }}
                        >
                          {h.hora}
                        </Button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </Spin>
          )}

          <div className="site-navegacao">
            <Button icon={<ArrowLeftOutlined />} onClick={() => irPara(0)}>
              Voltar
            </Button>
            <Button type="primary" disabled={!horario} onClick={() => irPara(2)}>
              Continuar
            </Button>
          </div>
        </>
      )}

      {etapa === 2 && servico && horario && (
        <Row gutter={[24, 24]}>
          <Col xs={24} md={10}>
            <div className="site-resumo">
              <span className="site-aviso">Resumo</span>
              <strong>{servico.nome}</strong>
              {dataDia && (
                <span>
                  <CalendarOutlined /> {capitalizar(dataDia.format('dddd, DD [de] MMMM'))}
                </span>
              )}
              <span>
                <ClockCircleOutlined /> {horario.hora}, {duracaoTexto(servico.duracao)}
              </span>
              {horario.funcionarioNome && (
                <span>
                  <UserOutlined /> {horario.funcionarioNome}
                </span>
              )}
              {horario.local && (
                <span>
                  {horario.local.tipo === 'online' ? (
                    <>
                      <VideoCameraOutlined /> Atendimento online (o link chega pelo WhatsApp)
                    </>
                  ) : (
                    <>
                      <EnvironmentOutlined /> {horario.local.nome}
                    </>
                  )}
                </span>
              )}
              {servico.preco != null && <span className="site-preco">{moeda(servico.preco)}</span>}
            </div>
          </Col>
          <Col xs={24} md={14}>
            <h2>Seu cadastro</h2>
            {avisoDaEtapa}
            <Form form={form} layout="vertical" disabled={enviando}>
              <Row gutter={12}>
                <Col xs={24} sm={10}>
                  <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe seu nome' }]}>
                    <Input maxLength={60} autoComplete="given-name" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={14}>
                  <Form.Item name="sobrenome" label="Sobrenome" rules={[{ required: true, whitespace: true, message: 'Informe seu sobrenome' }]}>
                    <Input maxLength={100} autoComplete="family-name" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="telefone"
                label="WhatsApp"
                normalize={mascaraTelefone}
                rules={[
                  { required: true, message: 'Informe seu WhatsApp' },
                  { validator: (_, v) => (!v || soDigitos(v).length >= 10 ? Promise.resolve() : Promise.reject(new Error('Telefone incompleto'))) },
                ]}
              >
                <Input placeholder="(11) 99999-9999" inputMode="tel" autoComplete="tel" />
              </Form.Item>
              <Form.Item name="email" label="E-mail" rules={[{ type: 'email', message: 'E-mail inválido' }]}>
                <Input maxLength={254} inputMode="email" autoComplete="email" />
              </Form.Item>
              <Form.Item name="observacoes" label="Observações">
                <Input.TextArea maxLength={500} showCount autoSize={{ minRows: 2, maxRows: 5 }} />
              </Form.Item>
              <Form.Item
                name="aceite"
                valuePropName="checked"
                rules={[{ validator: (_, v) => (v ? Promise.resolve() : Promise.reject(new Error('Necessário para continuar'))) }]}
              >
                <Checkbox>Entendo que este é um cadastro de exemplo</Checkbox>
              </Form.Item>
            </Form>
            <div className="site-navegacao">
              <Button icon={<ArrowLeftOutlined />} disabled={enviando} onClick={() => irPara(1)}>
                Voltar
              </Button>
              <Button type="primary" loading={enviando} disabled={espera > 0} onClick={enviar}>
                {espera > 0 ? `Aguarde ${tempoEspera(espera)}` : 'Solicitar agendamento'}
              </Button>
            </div>
          </Col>
        </Row>
      )}

      {etapa === 3 && pedido && (
        <Result
          status="success"
          title={pedido.clienteNome ? `Solicitação enviada, ${pedido.clienteNome}!` : 'Solicitação enviada!'}
          subTitle={[pedido.mensagem, quando && `${quando}.`, 'Você recebe a confirmação pelo WhatsApp.']
            .filter(Boolean)
            .join(' ')}
          extra={[
            <Button key="novo" onClick={recomecar}>
              Fazer outro agendamento
            </Button>,
            <Button key="painel" type="primary" onClick={() => navigate('/painel')}>
              Ver no painel da loja (demonstração)
            </Button>,
          ]}
        />
      )}
    </>
  )
}
