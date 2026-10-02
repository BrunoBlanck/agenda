import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Avatar, Button, Card, Checkbox, Col, Empty, Flex, Form, Input, Result, Row, Select, Steps, Tag, Typography } from 'antd'
import {
  ArrowLeftOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  PhoneOutlined,
  UserOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { mascaraTelefone, moeda, soDigitos } from '../utils/formatos.js'
import { capitalizar, COR_PADRAO } from '../components/agenda/util.js'
import { horariosLivres } from './horariosLivres.js'

const DIAS_A_FRENTE = 14

// O tipo da loja muda só os textos do site (estrutura.md, 1.2)
const termosPorTipo = {
  clinica: { profissional: 'Profissional', servico: 'Serviço', chamada: 'Agende sua consulta' },
  barbearia: { profissional: 'Barbeiro', servico: 'Serviço', chamada: 'Agende seu horário' },
  escola: { profissional: 'Professor', servico: 'Aula', chamada: 'Agende sua aula' },
}

// Site do consumidor final (exemplo genérico): escolhe o serviço, vê os horários livres,
// faz um cadastro e a solicitação entra no painel da loja como "Aguardando aceite".
export default function SiteLoja() {
  const navigate = useNavigate()
  const { loja, tipos, servicos, funcionarios, jornadas, bloqueios, agendamentos, clientes } = useData()
  const { moduloAtivo } = useAcesso()
  const [etapa, setEtapa] = useState(0)
  const [servicoId, setServicoId] = useState(null)
  const [profissional, setProfissional] = useState('qualquer')
  const [dia, setDia] = useState(null)
  const [horario, setHorario] = useState(null)
  const [form] = Form.useForm()

  const dados = loja.dados
  const termos = termosPorTipo[dados.tipo] ?? termosPorTipo.clinica
  const nomeTipo = tipos.itens.find((t) => t.codigo === dados.tipo)?.nome

  // Sem o módulo Serviços, o site oferece um atendimento genérico de 30 minutos
  const comJornada = funcionarios.itens.filter((f) => f.ativo && jornadas.itens.some((j) => j.funcionarioId === f.id))
  const opcoes = moduloAtivo('servicos')
    ? servicos.itens.filter((s) => s.funcionarioIds.length > 0)
    : [{ id: 'atendimento', nome: 'Atendimento', duracao: 30, preco: null, funcionarioIds: comJornada.map((f) => f.id) }]
  const servico = opcoes.find((s) => s.id === servicoId)

  const profissionais = funcionarios.itens.filter((f) => f.ativo && servico?.funcionarioIds.includes(f.id))
  const idsConsulta = profissional === 'qualquer' ? profissionais.map((f) => f.id) : [profissional]
  const livresEm = (data) =>
    servico
      ? horariosLivres({
          data,
          funcionarioIds: idsConsulta,
          duracao: servico.duracao,
          jornadas: jornadas.itens,
          bloqueios: bloqueios.itens,
          agendamentos: agendamentos.itens,
        })
      : []
  const dias = Array.from({ length: DIAS_A_FRENTE }, (_, i) => dayjs().startOf('day').add(i, 'day'))
  const livresDoDia = dia ? livresEm(dia) : []
  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome

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
      clientes.atualizar(existente.id, { canais }, null)
    } else {
      clienteId = clientes.adicionar({ nome: v.nome, telefone: v.telefone, email: v.email, canais: ['site'] }, null)
    }
    agendamentos.adicionar(
      {
        clienteId,
        funcionarioId: horario.funcionarioId,
        servicoId: moduloAtivo('servicos') ? servico.id : null,
        data: dia.format('YYYY-MM-DD'),
        hora: horario.hora,
        duracao: servico.duracao,
        preco: servico.preco,
        status: 'pendente',
        origem: 'site',
      },
      null,
    )
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
    .join(' · ')

  return (
    <div className="site">
      <header className="site-topo">
        <Flex align="center" gap={10}>
          <Avatar shape="square" size={36} src={dados.logoUrl} style={{ background: '#0f766e' }}>
            {dados.nomeFantasia[0]}
          </Avatar>
          <Typography.Text strong style={{ fontSize: 17 }}>
            {dados.nomeFantasia}
          </Typography.Text>
        </Flex>
        <Flex align="center" gap={8}>
          <Tag color="purple">Exemplo</Tag>
          <Button type="text" onClick={() => navigate('/painel')}>
            Área da loja
          </Button>
        </Flex>
      </header>

      <section className="site-capa">
        <div className="site-conteudo">
          <Tag color="cyan" style={{ marginBottom: 12 }}>
            {nomeTipo}
          </Tag>
          <h1>{dados.nomeFantasia}</h1>
          <p>{termos.chamada} online, em poucos passos.</p>
          <Flex gap={24} wrap className="site-contato">
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
          </Flex>
        </div>
      </section>

      <main className="site-conteudo site-principal">
        {dados.status !== 'ativa' ? (
          <Card>
            <Result status="warning" title="Agendamento online indisponível" subTitle="Entre em contato com a loja pelo telefone." />
          </Card>
        ) : (
          <Card>
            <Steps
              current={etapa}
              size="small"
              style={{ marginBottom: 32 }}
              items={[{ title: termos.servico }, { title: 'Horário' }, { title: 'Seus dados' }, { title: 'Pronto' }]}
            />

            {etapa === 0 && (
              <>
                <Typography.Title level={4}>Escolha {termos.servico === 'Aula' ? 'a aula' : 'o serviço'}</Typography.Title>
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
                <Flex justify="space-between" align="center" wrap gap={12} style={{ marginBottom: 20 }}>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {servico.nome} · {servico.duracao} min
                  </Typography.Title>
                  <Select
                    style={{ minWidth: 240 }}
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
                            <span className="agenda-cor" style={{ background: f.cor ?? COR_PADRAO }} />
                            {f.nome}
                          </Flex>
                        ),
                      })),
                    ]}
                  />
                </Flex>

                <Typography.Text strong>Escolha o dia</Typography.Text>
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
                    <Typography.Text strong>Horários livres em {dia.format('DD/MM')}</Typography.Text>
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

                <Flex justify="space-between" style={{ marginTop: 24 }}>
                  <Button icon={<ArrowLeftOutlined />} onClick={() => setEtapa(0)}>
                    Voltar
                  </Button>
                  <Button type="primary" disabled={!horario} onClick={() => setEtapa(2)}>
                    Continuar
                  </Button>
                </Flex>
              </>
            )}

            {etapa === 2 && (
              <Row gutter={[24, 24]}>
                <Col xs={24} md={10}>
                  <div className="site-resumo">
                    <Typography.Text type="secondary">Resumo</Typography.Text>
                    <strong style={{ fontSize: 18 }}>{servico.nome}</strong>
                    <span>
                      <CalendarOutlined /> {capitalizar(dia.format('dddd, DD [de] MMMM'))}
                    </span>
                    <span>
                      <ClockCircleOutlined /> {horario.hora} · {servico.duracao} min
                    </span>
                    <span>
                      <UserOutlined /> {nomeFunc(horario.funcionarioId)}
                    </span>
                    {servico.preco != null && <span className="site-preco">{moeda(servico.preco)}</span>}
                  </div>
                </Col>
                <Col xs={24} md={14}>
                  <Typography.Title level={4} style={{ marginTop: 0 }}>
                    Seu cadastro
                  </Typography.Title>
                  <Form form={form} layout="vertical">
                    <Form.Item name="nome" label="Nome completo" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
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
                  <Flex justify="space-between">
                    <Button icon={<ArrowLeftOutlined />} onClick={() => setEtapa(1)}>
                      Voltar
                    </Button>
                    <Button type="primary" onClick={enviar}>
                      Solicitar agendamento
                    </Button>
                  </Flex>
                </Col>
              </Row>
            )}

            {etapa === 3 && (
              <Result
                status="success"
                title="Solicitação enviada!"
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
          </Card>
        )}
      </main>

      <footer className="site-rodape">
        {dados.nomeFantasia} · {endereco}
        <br />
        <span>Agendamento online · exemplo genérico do site do consumidor</span>
      </footer>
    </div>
  )
}
