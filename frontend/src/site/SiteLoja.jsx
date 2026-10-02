import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Avatar, Button, Checkbox, Col, ConfigProvider, Empty, Flex, Form, Input, Result, Row, Select, Steps } from 'antd'
import {
  ArrowLeftOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  PhoneOutlined,
  VideoCameraOutlined,
  UserOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { SITE, useData } from '../data/DataContext.jsx'
import { tiposLoja } from '../data/plataforma.js'
import { useAcesso } from '../data/useAcesso.js'
import { mascaraTelefone, moeda, soDigitos } from '../utils/formatos.js'
import { capitalizar } from '../utils/formatos.js'
import { COR_PADRAO } from '../components/agenda/util.js'
import { horariosLivres } from './horariosLivres.js'
import { locaisDoServico } from '../data/locais.js'
import { jornadaDe } from '../data/horarios.js'
import { temasSite } from '../tema.js'
import './site.css'

const DIAS_A_FRENTE = 14

// Por enquanto o tipo da loja muda só os textos deste site de exemplo. No sistema real cada tipo
// terá o próprio site (layout e fluxo), escolhido pelo código do tipo (estrutura.md, 1.2)
const termosPorTipo = {
  clinica: { profissional: 'Profissional', servico: 'Serviço', chamada: 'Agende sua consulta' },
  barbearia: { profissional: 'Barbeiro', servico: 'Serviço', chamada: 'Agende seu horário' },
  escola: { profissional: 'Professor', servico: 'Aula', chamada: 'Agende sua aula' },
}

// Site do consumidor final (exemplo genérico): escolhe o serviço, vê os horários livres,
// faz um cadastro e a solicitação entra no painel da loja como "Aguardando aceite".
export default function SiteLoja() {
  const navigate = useNavigate()
  const { loja, servicos, funcionarios, jornadas, bloqueios, agendamentos, clientes, locais } = useData()
  const { moduloAtivo } = useAcesso()
  const [etapa, setEtapa] = useState(0)
  const [servicoId, setServicoId] = useState(null)
  const [profissional, setProfissional] = useState('qualquer')
  const [dia, setDia] = useState(null)
  const [horario, setHorario] = useState(null)
  const [nomeCliente, setNomeCliente] = useState('') // só o nome, para chamar o cliente por ele
  const [form] = Form.useForm()

  const dados = loja.dados
  const termos = termosPorTipo[dados.tipo] ?? termosPorTipo.clinica
  const nomeTipo = tiposLoja[dados.tipo]?.nome
  const temaSite = temasSite[dados.tipo] ?? temasSite.clinica

  // Sem o módulo Serviços, o site oferece um atendimento genérico de 30 minutos
  const comJornada = funcionarios.itens.filter((f) => f.ativo && jornadaDe(f, jornadas.itens).length > 0)
  const opcoes = moduloAtivo('servicos')
    ? servicos.itens.filter((s) => s.funcionarioIds.length > 0)
    : [{ id: 'atendimento', nome: 'Atendimento', duracao: 30, preco: null, funcionarioIds: comJornada.map((f) => f.id) }]
  const servico = opcoes.find((s) => s.id === servicoId)

  const profissionais = funcionarios.itens.filter((f) => f.ativo && servico?.funcionarioIds.includes(f.id))
  const idsConsulta = profissional === 'qualquer' ? profissionais.map((f) => f.id) : [profissional]
  const localIds = moduloAtivo('locais') ? locaisDoServico(servico, locais.itens).map((l) => l.id) : null
  const livresEm = (data) =>
    servico
      ? horariosLivres({
          data,
          funcionarioIds: idsConsulta,
          funcionarios: funcionarios.itens,
          duracao: servico.duracao,
          jornadas: jornadas.itens,
          bloqueios: bloqueios.itens,
          agendamentos: agendamentos.itens,
          localIds,
        })
      : []
  const dias = Array.from({ length: DIAS_A_FRENTE }, (_, i) => dayjs().startOf('day').add(i, 'day'))
  const livresDoDia = dia ? livresEm(dia) : []
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome
  const localDoHorario = locais.itens.find((l) => l.id === horario?.localId)

  const escolherServico = (id) => {
    setServicoId(id)
    setProfissional('qualquer')
    setDia(null)
    setHorario(null)
    setEtapa(1)
  }

  const enviar = async () => {
    const v = await form.validateFields().catch(() => null)
    if (!v) return
    // Cliente já cadastrado (mesmo telefone) ganha o canal "site"; senão é criado
    const existente = clientes.itens.find((c) => soDigitos(c.telefone) === soDigitos(v.telefone))
    let clienteId = existente?.id
    if (existente) {
      const canais = [...new Set([...(existente.canais ?? []), 'site'])]
      clientes.atualizar(existente.id, { canais }, SITE)
    } else {
      clienteId = clientes.adicionar({ nome: v.nome.trim(), sobrenome: v.sobrenome.trim(), telefone: v.telefone, email: v.email, canais: ['site'] }, SITE)
    }
    agendamentos.adicionar(
      {
        clienteId,
        funcionarioId: horario.funcionarioId,
        localId: horario.localId,
        servicoId: moduloAtivo('servicos') ? servico.id : null,
        data: dia.format('YYYY-MM-DD'),
        hora: horario.hora,
        duracao: servico.duracao,
        preco: servico.preco,
        status: 'pendente',
        origem: 'site',
      },
      SITE,
    )
    setNomeCliente(existente?.nome ?? v.nome.trim())
    setEtapa(3)
  }

  const recomecar = () => {
    form.resetFields()
    setServicoId(null)
    setDia(null)
    setHorario(null)
    setEtapa(0)
  }

  const endereco = [dados.logradouro && `${dados.logradouro}, ${dados.numero}`, dados.bairro, dados.cidade && `${dados.cidade}/${dados.uf}`]
    .filter(Boolean)
    .join(', ')

  return (
    <ConfigProvider theme={{ token: { colorPrimary: temaSite.cor, colorLink: temaSite.cor } }}>
    <div className="site" data-tipo={dados.tipo} style={{ '--site-cor': temaSite.cor, '--site-topo': temaSite.topo }}>
      <title>{`${dados.nomeFantasia}: ${termos.chamada.toLowerCase()}`}</title>
      <header className="site-topo">
        <div className="site-marca">
          <Avatar shape="square" size={36} src={dados.logoUrl} className="site-logo">
            {dados.nomeFantasia[0]}
          </Avatar>
          <strong>{dados.nomeFantasia}</strong>
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
          <span className="site-tipo">{nomeTipo}</span>
          <h1>{dados.nomeFantasia}</h1>
          <p>{termos.chamada} online, em poucos passos.</p>
          <div className="site-contato">
            {endereco && (
              <span>
                <EnvironmentOutlined /> {endereco}
              </span>
            )}
            {dados.telefone && (
              <span>
                <PhoneOutlined /> {dados.telefone}
              </span>
            )}
          </div>
        </div>
      </section>

      <main className="site-conteudo site-principal">
        {dados.status !== 'ativa' ? (
          <div className="site-cartao">
            <Result status="warning" title="Agendamento online indisponível" subTitle="Entre em contato com a loja pelo telefone." />
          </div>
        ) : (
          <div className="site-cartao">
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
                <Row gutter={[16, 16]}>
                  {opcoes.map((s) => (
                    <Col key={s.id} xs={24} sm={12}>
                      <button type="button" className="site-opcao" onClick={() => escolherServico(s.id)}>
                        <strong>{s.nome}</strong>
                        <span>
                          <ClockCircleOutlined /> {s.duracao} min
                        </span>
                        {s.preco != null && <span className="site-preco">{moeda(s.preco)}</span>}
                      </button>
                    </Col>
                  ))}
                </Row>
              </>
            )}

            {etapa === 1 && servico && (
              <>
                <div className="site-servico-escolhido">
                  <h2>
                    {servico.nome}, {servico.duracao} min
                  </h2>
                  <Select
                    aria-label={termos.profissional}
                    value={profissional}
                    onChange={(v) => {
                      setProfissional(v)
                      setHorario(null)
                    }}
                    options={[
                      { value: 'qualquer', label: `Qualquer ${termos.profissional.toLowerCase()}` },
                      ...profissionais.map((f) => ({
                        value: f.id,
                        label: (
                          <Flex align="center" gap={8}>
                            <span className="site-cor-profissional" style={{ background: f.cor ?? COR_PADRAO }} />
                            {f.nome}
                          </Flex>
                        ),
                      })),
                    ]}
                  />
                </div>

                <span className="site-rotulo">Escolha o dia</span>
                <div className="site-dias">
                  {dias.map((d) => {
                    const total = livresEm(d).length
                    const ativo = dia?.isSame(d, 'day')
                    return (
                      <button
                        key={d.format('YYYY-MM-DD')}
                        type="button"
                        disabled={total === 0}
                        className={['site-dia', ativo && 'ativo'].filter(Boolean).join(' ')}
                        onClick={() => {
                          setDia(d)
                          setHorario(null)
                        }}
                      >
                        <span>{d.isSame(dayjs(), 'day') ? 'Hoje' : capitalizar(d.format('ddd'))}</span>
                        <strong>{d.format('DD/MM')}</strong>
                        <small>{total ? `${total} horários` : 'Sem horários'}</small>
                      </button>
                    )
                  })}
                </div>

                {dia && (
                  <>
                    <span className="site-rotulo">Horários livres em {dia.format('DD/MM')}</span>
                    {livresDoDia.length === 0 ? (
                      <Empty description="Nenhum horário livre neste dia" />
                    ) : (
                      <div className="site-horarios">
                        {livresDoDia.map((h) => (
                          <Button
                            key={h.hora}
                            type={horario?.hora === h.hora ? 'primary' : 'default'}
                            onClick={() => setHorario(h)}
                          >
                            {h.hora}
                          </Button>
                        ))}
                      </div>
                    )}
                  </>
                )}

                <div className="site-navegacao">
                  <Button icon={<ArrowLeftOutlined />} onClick={() => setEtapa(0)}>
                    Voltar
                  </Button>
                  <Button type="primary" disabled={!horario} onClick={() => setEtapa(2)}>
                    Continuar
                  </Button>
                </div>
              </>
            )}

            {etapa === 2 && (
              <Row gutter={[24, 24]}>
                <Col xs={24} md={10}>
                  <div className="site-resumo">
                    <span className="site-aviso">Resumo</span>
                    <strong>{servico.nome}</strong>
                    <span>
                      <CalendarOutlined /> {capitalizar(dia.format('dddd, DD [de] MMMM'))}
                    </span>
                    <span>
                      <ClockCircleOutlined /> {horario.hora}, {servico.duracao} min
                    </span>
                    <span>
                      <UserOutlined /> {nomeFunc(horario.funcionarioId)}
                    </span>
                    {localDoHorario && (
                      <span>
                        {localDoHorario.tipo === 'online' ? (
                          <>
                            <VideoCameraOutlined /> Atendimento online (o link chega pelo WhatsApp)
                          </>
                        ) : (
                          <>
                            <EnvironmentOutlined /> {localDoHorario.nome}
                          </>
                        )}
                      </span>
                    )}
                    {servico.preco != null && <span className="site-preco">{moeda(servico.preco)}</span>}
                  </div>
                </Col>
                <Col xs={24} md={14}>
                  <h2>Seu cadastro</h2>
                  <Form form={form} layout="vertical">
                    <Row gutter={12}>
                      <Col xs={24} sm={10}>
                        <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe seu nome' }]}>
                          <Input maxLength={60} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} sm={14}>
                        <Form.Item name="sobrenome" label="Sobrenome" rules={[{ required: true, whitespace: true, message: 'Informe seu sobrenome' }]}>
                          <Input maxLength={100} />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item
                      name="telefone"
                      label="WhatsApp"
                      normalize={mascaraTelefone}
                      rules={[{ required: true }, { validator: (_, v) => (!v || soDigitos(v).length >= 10 ? Promise.resolve() : Promise.reject(new Error('Telefone incompleto'))) }]}
                    >
                      <Input placeholder="(11) 99999-9999" />
                    </Form.Item>
                    <Form.Item name="email" label="E-mail" rules={[{ type: 'email' }]}>
                      <Input />
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
                    <Button icon={<ArrowLeftOutlined />} onClick={() => setEtapa(1)}>
                      Voltar
                    </Button>
                    <Button type="primary" onClick={enviar}>
                      Solicitar agendamento
                    </Button>
                  </div>
                </Col>
              </Row>
            )}

            {etapa === 3 && (
              <Result
                status="success"
                title={`Solicitação enviada, ${nomeCliente}!`}
                subTitle={`${dados.nomeFantasia} vai confirmar seu horário de ${dia.format('DD/MM')} às ${horario.hora}. Você recebe a confirmação pelo WhatsApp.`}
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
          </div>
        )}
      </main>

      <footer className="site-rodape">
        <p>
          {dados.nomeFantasia}
          {endereco && `, ${endereco}`}
        </p>
        <p>Protótipo do site de agendamento. A versão final será gerada pelo servidor.</p>
      </footer>
    </div>
    </ConfigProvider>
  )
}
