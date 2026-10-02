import { Alert, App, Col, DatePicker, Form, Input, InputNumber, Row, Select, TimePicker } from 'antd'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento } from '../data/mock.js'
import { localOcupado, locaisDoServico, rotulosLocal } from '../data/locais.js'
import { bloqueioAtinge, jornadaDe } from '../data/horarios.js'
import { horaCurta, nomeCompleto } from '../utils/formatos.js'
import PainelFormulario from './base/PainelFormulario.jsx'
import { usePainel } from './base/usePainel.js'
import Etiqueta from './base/Etiqueta.jsx'
import { EtiquetaTipoLocal } from './Etiquetas.jsx'
import UltimaAlteracao from './UltimaAlteracao.jsx'
import HistoricoCliente from './HistoricoCliente.jsx'
import ResumoCliente from './ResumoCliente.jsx'

// Avisa quando o horário cai fora da jornada do profissional ou dentro de um bloqueio.
// No sistema real essa validação é feita pelo back-end.
// A jornada e os bloqueios do profissional vêm do perfil dele (data/horarios.js).
function avisoDisponibilidade({ data, hora, duracao }, funcionario, jornadas, bloqueios) {
  if (!funcionario || !data || !hora) return null
  const inicio = data.hour(hora.hour()).minute(hora.minute()).second(0)
  const fim = inicio.add(duracao ?? 0, 'minute')
  const [ini, fi] = [inicio.format('HH:mm'), fim.format('HH:mm')]

  const dentroJornada = jornadaDe(funcionario, jornadas).some(
    (j) => j.diaSemana === inicio.day() && j.inicio <= ini && fi <= j.fim,
  )
  const bloqueio = bloqueios.find(
    (b) => bloqueioAtinge(b, funcionario) && inicio.isBefore(dayjs(b.fim)) && fim.isAfter(dayjs(b.inicio)),
  )
  if (bloqueio) return `Horário bloqueado: ${bloqueio.motivo || 'sem motivo informado'}.`
  if (!dentroJornada) return 'Horário fora da jornada de trabalho do profissional.'
  return null
}

const opcoesStatus = Object.entries(statusAgendamento).map(([value, s]) => ({ value, label: s.label }))

// Painel para criar/editar um agendamento. `agendamento` = null cria um novo.
// O cabeçalho mostra o cliente assim que ele é escolhido. O histórico do cliente abre no lugar
// do agendamento (fecha um, abre o outro), nunca por cima.
export default function AgendamentoPainel({ open, onClose, agendamento, dataInicial, horaInicial }) {
  const { clientes, funcionarios, agendamentos, servicos, materiais, jornadas, bloqueios, locais, loja } = useData()
  const { usuario, moduloAtivo, agenda } = useAcesso()
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const historico = usePainel()
  const valores = Form.useWatch([], form) ?? {}
  const servico = servicos.itens.find((s) => s.id === valores.servicoId)

  const comServicos = moduloAtivo('servicos')
  const comMateriais = moduloAtivo('materiais')
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja.dados)
  const somenteLeitura = agendamento ? !agenda.editar(agendamento) : !agenda.criar

  // Sem escrita na agenda da equipe, o usuário só agenda para si mesmo (e só os serviços que ele realiza).
  // Com escrita, aparecem os profissionais habilitados para o serviço escolhido.
  const proprio = (id) => id === usuario?.id || id === agendamento?.funcionarioId
  const servicosDisponiveis = servicos.itens.filter(
    (s) => agenda.criarParaOutros || s.funcionarioIds.some(proprio) || s.id === agendamento?.servicoId,
  )
  const profissionais = funcionarios.itens.filter((f) =>
    agenda.criarParaOutros ? f.ativo && (!comServicos || servico?.funcionarioIds.includes(f.id)) : proprio(f.id),
  )

  // Locais permitidos para o serviço (o já gravado no agendamento continua na lista mesmo se inativo)
  const permitidos = (s) => locaisDoServico(comServicos ? s : null, locais.itens)
  const opcoesLocal = [
    ...permitidos(servico),
    ...locais.itens.filter((l) => l.id === agendamento?.localId && !permitidos(servico).includes(l)),
  ]
  // Outro agendamento ativo usa o local no horário informado?
  const ocupado = (localId, { data, hora, duracao } = valores) => {
    if (!data || !hora) return false
    const ini = hora.hour() * 60 + hora.minute()
    return localOcupado(localId, data.format('YYYY-MM-DD'), ini, ini + (duracao ?? 0), agendamentos.itens, agendamento?.id)
  }
  const localEscolhido = locais.itens.find((l) => l.id === valores.localId)
  const semServico = comServicos && !servico

  // Serviço preenche duração e preço; local e profissional são mantidos se continuarem válidos
  const trocarServico = (id) => {
    const novo = servicos.itens.find((s) => s.id === id)
    form.setFieldsValue({ duracao: novo?.duracao, preco: novo?.preco })
    if (comLocais && !permitidos(novo).some((l) => l.id === form.getFieldValue('localId'))) {
      const lista = permitidos(novo)
      form.setFieldsValue({ localId: lista.length === 1 ? lista[0].id : undefined })
    }
    if (agenda.criarParaOutros && !novo?.funcionarioIds.includes(form.getFieldValue('funcionarioId'))) {
      form.setFieldsValue({ funcionarioId: novo?.funcionarioIds.length === 1 ? novo.funcionarioIds[0] : undefined })
    }
  }

  const resumoMateriais =
    comMateriais &&
    servico?.materiais
      ?.map((m) => {
        const mat = materiais.itens.find((x) => x.id === m.materialId)
        return `${m.quantidade} ${mat?.unidade ?? ''} de ${mat?.nome ?? ''}`.replace(/\s+/g, ' ').trim()
      })
      .join(', ')

  const profissionalEscolhido = funcionarios.itens.find((f) => f.id === valores.funcionarioId)
  const aviso = avisoDisponibilidade(valores, profissionalEscolhido, jornadas.itens, bloqueios.itens)

  const valoresIniciais = agendamento
    ? { ...agendamento, data: dayjs(agendamento.data), hora: dayjs(agendamento.hora, 'HH:mm') }
    : {
        data: dataInicial ?? dayjs(),
        hora: horaInicial ? dayjs(horaInicial, 'HH:mm') : undefined,
        duracao: 30,
        status: 'agendado',
        funcionarioId: agenda.criarParaOutros ? undefined : usuario?.id,
      }

  const salvar = (campos) => {
    const dados = { ...campos, data: campos.data.format('YYYY-MM-DD'), hora: campos.hora.format('HH:mm') }
    if (agendamento) {
      agendamentos.atualizar(agendamento.id, dados)
      message.success('Agendamento salvo.')
    } else {
      agendamentos.adicionar(dados)
      message.success(`Agendado para ${campos.data.format('DD/MM')} às ${horaCurta(dados.hora)}.`)
    }
    onClose()
  }

  const titulo = somenteLeitura ? 'Agendamento' : agendamento ? 'Editar agendamento' : 'Novo agendamento'
  const cliente = clientes.todos.find((c) => c.id === valores.clienteId)

  return (
    <>
      <PainelFormulario
        titulo={titulo}
        nome={cliente && nomeCompleto(cliente)}
        open={open}
        form={form}
        valoresIniciais={valoresIniciais}
        somenteLeitura={somenteLeitura}
        textoSalvar={agendamento ? 'Salvar' : 'Agendar'}
        largura={560}
        onCancelar={onClose}
        onSalvar={salvar}
        rodape={<UltimaAlteracao item={agendamento} />}
      >
        {(fechar) => (
          <>
            <h3 className="grupo-formulario">Cliente</h3>
            <Form.Item name="clienteId" label="Cliente" rules={[{ required: true, message: 'Escolha o cliente' }]}>
              <Select
                showSearch
                optionFilterProp="label"
                placeholder="Busque pelo nome"
                options={clientes.itens.map((c) => ({ value: c.id, label: nomeCompleto(c) }))}
              />
            </Form.Item>
            <ResumoCliente
              clienteId={valores.clienteId}
              agendamentoId={agendamento?.id}
              onAbrir={() => {
                const id = valores.clienteId
                fechar(() => historico.abrir({ id }))
              }}
            />

            <h3 className="grupo-formulario">Atendimento</h3>
            {comServicos && (
              <Form.Item name="servicoId" label="Serviço" rules={[{ required: true, message: 'Escolha o serviço' }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  onChange={trocarServico}
                  options={servicosDisponiveis.map((s) => ({ value: s.id, label: `${s.nome} (${s.duracao} min)` }))}
                />
              </Form.Item>
            )}
            <Form.Item name="funcionarioId" label="Profissional" rules={[{ required: true, message: 'Escolha o profissional' }]}>
              <Select
                disabled={!agenda.criarParaOutros || semServico}
                placeholder={semServico ? 'Escolha o serviço primeiro' : 'Selecione'}
                options={profissionais.map((f) => ({ value: f.id, label: `${f.nome} (${f.cargo})` }))}
              />
            </Form.Item>
            {resumoMateriais && <Alert type="info" showIcon title={`Materiais usados: ${resumoMateriais}.`} className="alerta-formulario" />}

            <h3 className="grupo-formulario">{comLocais ? 'Quando e onde' : 'Quando'}</h3>
            <Row gutter={12}>
              <Col xs={24} sm={10}>
                <Form.Item name="data" label="Data" rules={[{ required: true, message: 'Informe a data' }]}>
                  <DatePicker format="DD/MM/YYYY" />
                </Form.Item>
              </Col>
              <Col xs={12} sm={7}>
                <Form.Item name="hora" label="Horário" rules={[{ required: true, message: 'Informe o horário' }]}>
                  <TimePicker format="HH:mm" minuteStep={15} needConfirm={false} />
                </Form.Item>
              </Col>
              <Col xs={12} sm={7}>
                <Form.Item name="duracao" label="Duração" rules={[{ required: true, message: 'Informe a duração' }]}>
                  <InputNumber min={15} step={15} suffix="min" />
                </Form.Item>
              </Col>
            </Row>
            {aviso && !somenteLeitura && <Alert type="warning" showIcon title={aviso} className="alerta-formulario" />}
            {comLocais && (
              <Form.Item
                name="localId"
                label={rotulos.singular}
                dependencies={['data', 'hora', 'duracao']}
                rules={[
                  { required: true, message: 'Escolha onde será o atendimento' },
                  {
                    validator: (_, id) =>
                      id && ocupado(id, form.getFieldsValue())
                        ? Promise.reject(new Error('Já existe outro agendamento aqui neste horário. Escolha outro horário ou local.'))
                        : Promise.resolve(),
                  },
                ]}
              >
                <Select
                  disabled={semServico}
                  placeholder={semServico ? 'Escolha o serviço primeiro' : 'Selecione'}
                  options={opcoesLocal.map((l) => ({
                    value: l.id,
                    disabled: ocupado(l.id),
                    label: (
                      <span className="local-info">
                        {l.nome} <EtiquetaTipoLocal tipo={l.tipo} />
                        {ocupado(l.id) && <Etiqueta tom="atencao">Ocupado</Etiqueta>}
                        {!l.ativo && <Etiqueta>Inativo</Etiqueta>}
                      </span>
                    ),
                  }))}
                />
              </Form.Item>
            )}
            {comLocais && localEscolhido?.tipo === 'online' && (
              <Form.Item
                name="linkReuniao"
                label="Link da reunião"
                extra={localEscolhido.linkPadrao ? 'Se ficar vazio, usa o link fixo do local.' : 'Este local não tem link fixo: informe o link deste atendimento.'}
                rules={[{ type: 'url', message: 'Informe um link completo, começando com https://' }]}
              >
                <Input placeholder={localEscolhido.linkPadrao ?? 'https://'} />
              </Form.Item>
            )}

            <h3 className="grupo-formulario">Valor e situação</h3>
            <Row gutter={12}>
              <Col xs={24} sm={12}>
                <Form.Item
                  name="preco"
                  label="Preço"
                  extra={comServicos ? 'Copiado do serviço. Mudar o serviço depois não altera este valor.' : undefined}
                >
                  <InputNumber min={0} step={10} prefix="R$" decimalSeparator="," />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="status" label="Situação">
                  <Select options={opcoesStatus} />
                </Form.Item>
              </Col>
            </Row>
          </>
        )}
      </PainelFormulario>
      <HistoricoCliente clienteId={historico.registro?.id} open={historico.aberto} onClose={historico.fechar} />
    </>
  )
}
