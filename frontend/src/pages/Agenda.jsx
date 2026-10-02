import { useState } from 'react'
import { Card, Row, Col, Select, Button, Flex, Typography, Segmented } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import AgendamentoModal from '../components/AgendamentoModal.jsx'
import VisaoSemana from '../components/agenda/VisaoSemana.jsx'
import VisaoMes from '../components/agenda/VisaoMes.jsx'
import DetalheDia from '../components/agenda/DetalheDia.jsx'
import { COR_PADRAO, capitalizar, diasDaSemana, diasDoMes, minutosDe } from '../components/agenda/util.js'

const unidade = { semana: 'week', mes: 'month' }

export default function Agenda() {
  const { agendamentos, clientes, funcionarios, servicos, jornadas, bloqueios } = useData()
  const { agenda, usuario, moduloAtivo } = useAcesso()
  const [modo, setModo] = useState('semana')
  const [referencia, setReferencia] = useState(dayjs()) // semana/mês exibido
  const [dia, setDia] = useState(dayjs()) // dia detalhado no painel lateral
  const [profissional, setProfissional] = useState(null)
  const [modal, setModal] = useState({ open: false, agendamento: null, hora: null })

  const func = (id) => funcionarios.itens.find((f) => f.id === id)
  const nomeCliente = (id) => clientes.itens.find((c) => c.id === id)?.nome ?? '—'
  const nomeFunc = (id) => func(id)?.nome ?? '—'
  const nomeServico = (id) => servicos.itens.find((s) => s.id === id)?.nome ?? 'Atendimento'
  const corDe = (id) => func(id)?.cor ?? COR_PADRAO

  // Quem só vê a própria agenda fica sempre filtrado em si mesmo
  const filtroFunc = agenda.verEquipe ? profissional : usuario?.id
  const visiveis = agendamentos.itens.filter(agenda.ver).filter((a) => !filtroFunc || a.funcionarioId === filtroFunc)
  const bloqueiosVisiveis = bloqueios.itens.filter((b) => b.funcionarioId == null || !filtroFunc || b.funcionarioId === filtroFunc)

  // Faixa de horas da semana: cobre as jornadas e os agendamentos, com mínimo de 08:00 às 18:00
  const minutosUsados = [
    ...jornadas.itens.filter((j) => !filtroFunc || j.funcionarioId === filtroFunc).flatMap((j) => [minutosDe(j.inicio), minutosDe(j.fim)]),
    ...visiveis.flatMap((a) => [minutosDe(a.hora), minutosDe(a.hora) + (a.duracao ?? 0)]),
  ]
  const horaInicio = Math.min(8, ...minutosUsados.map((m) => Math.floor(m / 60)))
  const horaFim = Math.min(24, Math.max(18, ...minutosUsados.map((m) => Math.ceil(m / 60))))

  const navegar = (passo) => {
    const nova = referencia.add(passo, unidade[modo])
    setReferencia(nova)
    if (modo === 'semana') setDia(dia.add(passo, 'week'))
    else setDia(nova.isSame(dayjs(), 'month') ? dayjs() : nova.startOf('month'))
  }

  const irParaHoje = () => {
    setReferencia(dayjs())
    setDia(dayjs())
  }

  const trocarModo = (novo) => {
    setModo(novo)
    setReferencia(dia)
  }

  const semana = diasDaSemana(referencia)
  const titulo =
    modo === 'mes'
      ? referencia.format('MMMM [de] YYYY')
      : semana[0].isSame(semana[6], 'month')
        ? `${semana[0].format('DD')} a ${semana[6].format('DD [de] MMMM [de] YYYY')}`
        : `${semana[0].format('DD [de] MMM')} a ${semana[6].format('DD [de] MMM [de] YYYY')}`

  const chaveDia = dia.format('YYYY-MM-DD')
  const novo = (data, hora = null) => {
    setDia(data)
    setModal({ open: true, agendamento: null, hora })
  }

  return (
    <Row gutter={[16, 16]} align="top">
      <Col xs={24} xl={17}>
        <Card>
          <Flex justify="space-between" align="center" wrap gap={12} style={{ marginBottom: 16 }}>
            <Flex align="center" gap={8}>
              <Button onClick={irParaHoje}>Hoje</Button>
              <Button icon={<LeftOutlined />} onClick={() => navegar(-1)} />
              <Button icon={<RightOutlined />} onClick={() => navegar(1)} />
              <Typography.Title level={5} style={{ margin: '0 0 0 8px' }}>
                {capitalizar(titulo)}
              </Typography.Title>
            </Flex>
            <Flex align="center" gap={8} wrap>
              {agenda.verEquipe ? (
                <Select
                  allowClear
                  placeholder="Todos os profissionais"
                  style={{ minWidth: 220 }}
                  value={profissional}
                  onChange={setProfissional}
                  options={funcionarios.itens.map((f) => ({
                    value: f.id,
                    label: (
                      <Flex align="center" gap={8}>
                        <span className="agenda-cor" style={{ background: f.cor ?? COR_PADRAO }} />
                        {f.nome}
                      </Flex>
                    ),
                  }))}
                />
              ) : (
                <Typography.Text type="secondary">Mostrando apenas a sua agenda</Typography.Text>
              )}
              <Segmented
                value={modo}
                onChange={trocarModo}
                options={[
                  { value: 'semana', label: 'Semana' },
                  { value: 'mes', label: 'Mês' },
                ]}
              />
            </Flex>
          </Flex>

          {modo === 'semana' ? (
            <VisaoSemana
              dias={semana}
              agendamentos={visiveis}
              bloqueios={bloqueiosVisiveis}
              horaInicio={horaInicio}
              horaFim={horaFim}
              diaSelecionado={dia}
              onSelecionarDia={setDia}
              onAbrir={(a) => setModal({ open: true, agendamento: a, hora: null })}
              onNovo={agenda.criar ? novo : null}
              nomeCliente={nomeCliente}
              nomeServico={nomeServico}
              nomeFunc={nomeFunc}
              corDe={corDe}
            />
          ) : (
            <VisaoMes
              dias={diasDoMes(referencia)}
              mes={referencia}
              agendamentos={visiveis}
              bloqueios={bloqueiosVisiveis}
              diaSelecionado={dia}
              onSelecionarDia={setDia}
              nomeCliente={nomeCliente}
              corDe={corDe}
            />
          )}
        </Card>
      </Col>
      <Col xs={24} xl={7} className="agenda-coluna-detalhe">
        <DetalheDia
          dia={dia}
          agendamentos={visiveis.filter((a) => a.data === chaveDia)}
          bloqueios={bloqueiosVisiveis.filter((b) => dia.startOf('day').isBefore(b.fim) && dia.endOf('day').isAfter(b.inicio))}
          podeCriar={agenda.criar}
          podeEditar={agenda.editar}
          onNovo={() => novo(dia)}
          onAbrir={(a) => setModal({ open: true, agendamento: a, hora: null })}
          nomeCliente={nomeCliente}
          nomeServico={nomeServico}
          nomeFunc={nomeFunc}
          corDe={corDe}
          comServicos={moduloAtivo('servicos')}
        />
      </Col>
      <AgendamentoModal
        open={modal.open}
        agendamento={modal.agendamento}
        dataInicial={dia}
        horaInicial={modal.hora}
        onClose={() => setModal({ open: false, agendamento: null, hora: null })}
      />
    </Row>
  )
}
