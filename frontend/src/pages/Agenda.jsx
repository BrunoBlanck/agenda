import { useState } from 'react'
import { Button, Flex, Segmented, Select, Tooltip } from 'antd'
import { LeftOutlined, MenuFoldOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'
import VisaoSemana from '../components/agenda/VisaoSemana.jsx'
import VisaoMes from '../components/agenda/VisaoMes.jsx'
import DetalheDia from '../components/agenda/DetalheDia.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import { COR_PADRAO, diasDaSemana, diasDoMes, minutosDe } from '../components/agenda/util.js'
import { alvoBloqueio, bloqueioAtinge, jornadaDe } from '../data/horarios.js'
import { capitalizar } from '../utils/formatos.js'
import '../components/agenda/agenda.css'

const unidade = { semana: 'week', mes: 'month' }

// Painel do dia aberto ou recolhido: lembrado neste navegador (preferência de cada usuário)
const CHAVE_PAINEL = 'agenda.painelDia'
const lerPainel = () => {
  try {
    return localStorage.getItem(CHAVE_PAINEL) !== 'fechado'
  } catch {
    return true
  }
}
const gravarPainel = (aberto) => {
  try {
    localStorage.setItem(CHAVE_PAINEL, aberto ? 'aberto' : 'fechado')
  } catch {
    // Sem acesso ao armazenamento: só não lembra a escolha
  }
}

const tituloPeriodo = (modo, referencia) => {
  if (modo === 'mes') return capitalizar(referencia.format('MMMM [de] YYYY'))
  const [inicio, fim] = [diasDaSemana(referencia)[0], diasDaSemana(referencia)[6]]
  return inicio.isSame(fim, 'month')
    ? `${inicio.format('D')} a ${fim.format('D [de] MMMM [de] YYYY')}`
    : `${inicio.format('D [de] MMM')} a ${fim.format('D [de] MMM [de] YYYY')}`
}

export default function Agenda() {
  const { agendamentos, funcionarios, perfis, jornadas, bloqueios } = useData()
  const { agenda, usuario, moduloAtivo } = useAcesso()
  const [modo, setModo] = useState('semana')
  const [referencia, setReferencia] = useState(dayjs()) // semana/mês exibido
  const [dia, setDia] = useState(dayjs()) // dia detalhado no painel lateral
  const [profissional, setProfissional] = useState(null)
  const painelAgendamento = usePainel() // agendamento aberto; {hora} = novo naquele horário
  const [painelAberto, setPainelAberto] = useState(lerPainel)
  const alternarPainel = (aberto) => {
    setPainelAberto(aberto)
    gravarPainel(aberto)
  }

  const func = (id) => funcionarios.itens.find((f) => f.id === id)

  // Quem só vê a própria agenda fica sempre filtrado em si mesmo
  const filtroFunc = agenda.verEquipe ? profissional : usuario?.id
  const visiveis = agendamentos.itens.filter(agenda.ver).filter((a) => !filtroFunc || a.funcionarioId === filtroFunc)
  // quem: para quem é o bloqueio (null = loja inteira)
  const bloqueiosVisiveis = bloqueios.itens
    .filter((b) => !filtroFunc || bloqueioAtinge(b, func(filtroFunc)))
    .map((b) => ({ ...b, quem: alvoBloqueio(b, funcionarios.itens, perfis.itens) }))

  // Faixa de horas da semana: cobre as jornadas e os agendamentos, com mínimo de 8h às 18h
  const minutosUsados = [
    ...(filtroFunc ? jornadaDe(func(filtroFunc), jornadas.itens) : jornadas.itens).flatMap((j) => [minutosDe(j.inicio), minutosDe(j.fim)]),
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

  const novo = (data, hora = null) => {
    setDia(data)
    painelAgendamento.abrir({ hora })
  }
  const abrir = (a) => painelAgendamento.abrir(a)
  const chaveDia = dia.format('YYYY-MM-DD')

  return (
    <Pagina
      titulo="Agenda"
      descricao={agenda.verEquipe ? undefined : 'Mostrando só a sua agenda.'}
      acoes={
        agenda.criar && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => novo(dia)}>
            Agendar
          </Button>
        )
      }
    >
      <div className={painelAberto ? 'agenda-layout' : 'agenda-layout sem-painel'}>
        <Secao>
          <div className="agenda-barra">
            <div className="agenda-navegacao">
              <Button onClick={irParaHoje}>Hoje</Button>
              <Button icon={<LeftOutlined />} aria-label={modo === 'mes' ? 'Mês anterior' : 'Semana anterior'} onClick={() => navegar(-1)} />
              <Button icon={<RightOutlined />} aria-label={modo === 'mes' ? 'Próximo mês' : 'Próxima semana'} onClick={() => navegar(1)} />
              <h2 className="agenda-periodo" aria-live="polite">
                {tituloPeriodo(modo, referencia)}
              </h2>
            </div>
            <div className="agenda-filtros">
              {agenda.verEquipe && (
                <Select
                  allowClear
                  placeholder="Todos os profissionais"
                  aria-label="Profissional"
                  value={profissional}
                  onChange={setProfissional}
                  options={funcionarios.itens.map((f) => ({
                    value: f.id,
                    label: (
                      <Flex align="center" gap={8}>
                        <PontoCor cor={f.cor ?? COR_PADRAO} />
                        {f.nome}
                      </Flex>
                    ),
                  }))}
                />
              )}
              <Segmented
                value={modo}
                onChange={trocarModo}
                options={[
                  { value: 'semana', label: 'Semana' },
                  { value: 'mes', label: 'Mês' },
                ]}
              />
              {!painelAberto && (
                <Tooltip title="Mostrar os atendimentos do dia selecionado">
                  <Button icon={<MenuFoldOutlined />} onClick={() => alternarPainel(true)}>
                    Dia {dia.format('DD/MM')}
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>

          {modo === 'semana' ? (
            <VisaoSemana
              dias={diasDaSemana(referencia)}
              agendamentos={visiveis}
              bloqueios={bloqueiosVisiveis}
              horaInicio={horaInicio}
              horaFim={horaFim}
              diaSelecionado={dia}
              onSelecionarDia={setDia}
              onAbrir={abrir}
              onNovo={agenda.criar ? novo : null}
              destaqueId={painelAgendamento.destaqueId}
            />
          ) : (
            <VisaoMes
              dias={diasDoMes(referencia)}
              mes={referencia}
              agendamentos={visiveis}
              bloqueios={bloqueiosVisiveis}
              diaSelecionado={dia}
              onSelecionarDia={setDia}
            />
          )}
        </Secao>

        {painelAberto && (
          <DetalheDia
            dia={dia}
            agendamentos={visiveis.filter((a) => a.data === chaveDia)}
            bloqueios={bloqueiosVisiveis.filter((b) => dia.startOf('day').isBefore(b.fim) && dia.endOf('day').isAfter(b.inicio))}
            podeCriar={agenda.criar}
            podeEditar={agenda.editar}
            comServicos={moduloAtivo('servicos')}
            comLocais={moduloAtivo('locais')}
            onNovo={() => novo(dia)}
            onAbrir={abrir}
            destaqueId={painelAgendamento.destaqueId}
            onFechar={() => alternarPainel(false)}
          />
        )}
      </div>
      <AgendamentoPainel
        open={painelAgendamento.aberto}
        agendamento={painelAgendamento.registro?.id ? painelAgendamento.registro : null}
        dataInicial={dia}
        horaInicial={painelAgendamento.registro?.id ? null : painelAgendamento.registro?.hora}
        onClose={painelAgendamento.fechar}
      />
    </Pagina>
  )
}
