import { useState } from 'react'
import { Alert, Button, Flex, Segmented, Select, Tooltip } from 'antd'
import { LeftOutlined, MenuFoldOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useAgenda } from '../data/useAgenda.js'
import { useFiltrosAgenda } from '../data/useAgendamentos.js'
import { agoraNaLoja } from '../data/api/conversao.js'
import AgendamentoPainel from '../components/AgendamentoPainel.jsx'
import { usePainel } from '../components/base/usePainel.js'
import VisaoSemana from '../components/agenda/VisaoSemana.jsx'
import VisaoMes from '../components/agenda/VisaoMes.jsx'
import DetalheDia from '../components/agenda/DetalheDia.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import { COR_PADRAO, diasDaSemana, diasDoMes, minutosDe } from '../components/agenda/util.js'
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
  const { agenda, moduloAtivo } = useAcesso()
  const [modo, setModo] = useState('semana')
  const [referencia, setReferencia] = useState(agoraNaLoja) // semana/mês exibido (no dia da loja)
  const [dia, setDia] = useState(agoraNaLoja) // dia detalhado no painel lateral
  const [profissional, setProfissional] = useState(null)
  const painelAgendamento = usePainel() // agendamento aberto; {hora} = novo naquele horário
  const [painelAberto, setPainelAberto] = useState(lerPainel)
  const alternarPainel = (aberto) => {
    setPainelAberto(aberto)
    gravarPainel(aberto)
  }

  // Período da tela: a semana ou a grade do mês (6 semanas). O servidor devolve só o que o usuário
  // pode ver (quem só tem Minha agenda recebe só os próprios) e os bloqueios que atingem o filtro.
  const dias = modo === 'semana' ? diasDaSemana(referencia) : diasDoMes(referencia)
  const filtros = useFiltrosAgenda({ ativo: agenda.verEquipe })
  const funcionarioId = agenda.verEquipe ? profissional : null
  const periodo = useAgenda({ inicio: dias[0], fim: dias.at(-1), funcionarioId })

  // Ao trocar de semana/mês/profissional a consulta mantém os dados antigos até a resposta chegar.
  // Guarda qual período terminou de carregar por último: enquanto não for o da tela, a grade mostra
  // o formato dela vazio (blocos cinza), em vez de uma semana que parece livre.
  const chavePeriodo = `${dias[0].format('YYYY-MM-DD')}|${dias.at(-1).format('YYYY-MM-DD')}|${funcionarioId ?? ''}`
  const [carga, setCarga] = useState({ buscando: periodo.atualizando, chave: null })
  if (carga.buscando !== periodo.atualizando) {
    setCarga({ buscando: periodo.atualizando, chave: periodo.atualizando ? carga.chave : chavePeriodo })
  }
  const carregandoPeriodo = carga.chave !== chavePeriodo
  const visiveis = periodo.agendamentos
  // quem: para quem é o bloqueio (null = loja inteira)
  const bloqueiosVisiveis = periodo.bloqueios

  // Faixa de horas da semana: cobre as jornadas e os agendamentos, com mínimo de 8h às 18h
  const minutosUsados = [
    ...periodo.jornadas.flatMap((j) => [minutosDe(j.inicio), minutosDe(j.fim)]),
    ...visiveis.flatMap((a) => [minutosDe(a.hora), Math.min(24 * 60, minutosDe(a.hora) + (a.duracao ?? 0))]),
  ]
  const horaInicio = Math.min(8, ...minutosUsados.map((m) => Math.floor(m / 60)))
  const horaFim = Math.min(24, Math.max(18, ...minutosUsados.map((m) => Math.ceil(m / 60))))

  const navegar = (passo) => {
    const nova = referencia.add(passo, unidade[modo])
    setReferencia(nova)
    if (modo === 'semana') setDia(dia.add(passo, 'week'))
    else setDia(nova.isSame(agoraNaLoja(), 'month') ? agoraNaLoja() : nova.startOf('month'))
  }

  const irParaHoje = () => {
    setReferencia(agoraNaLoja())
    setDia(agoraNaLoja())
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
                  onChange={(id) => setProfissional(id ?? null)}
                  loading={filtros.carregando}
                  notFoundContent={filtros.erro ? filtros.erro.mensagem : undefined}
                  options={filtros.profissionais.map((f) => ({
                    value: f.id,
                    label: (
                      <Flex align="center" gap={8}>
                        <PontoCor cor={f.cor ?? COR_PADRAO} />
                        {f.ativo ? f.nome : `${f.nome} (inativo)`}
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
                <Tooltip title="Mostrar os atendimentos do dia selecionado" rootClassName="dica-icone">
                  <Button icon={<MenuFoldOutlined />} onClick={() => alternarPainel(true)}>
                    Dia {dia.format('DD/MM')}
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>

          {periodo.erro && (
            <Alert
              type="error"
              showIcon
              title="Não foi possível carregar a agenda."
              description={periodo.erro.mensagem}
              action={
                <Button size="small" onClick={periodo.recarregar}>
                  Tentar de novo
                </Button>
              }
              className="agenda-erro"
            />
          )}
          <div aria-busy={periodo.atualizando}>
            {modo === 'semana' ? (
              <VisaoSemana
                dias={dias}
                agendamentos={visiveis}
                bloqueios={bloqueiosVisiveis}
                horaInicio={horaInicio}
                horaFim={horaFim}
                diaSelecionado={dia}
                onSelecionarDia={setDia}
                onAbrir={abrir}
                onNovo={agenda.criar ? novo : null}
                destaqueId={painelAgendamento.destaqueId}
                carregando={carregandoPeriodo}
              />
            ) : (
              <VisaoMes
                dias={dias}
                mes={referencia}
                agendamentos={visiveis}
                bloqueios={bloqueiosVisiveis}
                diaSelecionado={dia}
                onSelecionarDia={setDia}
                carregando={carregandoPeriodo}
              />
            )}
          </div>
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
            onRespondido={periodo.recarregar}
            destaqueId={painelAgendamento.destaqueId}
            carregando={carregandoPeriodo}
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
        onSalvo={periodo.recarregar}
      />
    </Pagina>
  )
}
