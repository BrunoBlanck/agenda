import { useEffect, useState } from 'react'
import { Modal, Form, Select, DatePicker, TimePicker, InputNumber, Alert, Button, Input, Tag } from 'antd'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento, tiposLocal } from '../data/mock.js'
import { localOcupado, locaisDoServico, rotulosLocal } from '../data/locais.js'
import { nomeCompleto } from '../utils/formatos.js'
import { bloqueioAtinge, jornadaDe } from '../data/horarios.js'
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
    (b) =>
      bloqueioAtinge(b, funcionario) &&
      inicio.isBefore(dayjs(b.fim)) &&
      fim.isAfter(dayjs(b.inicio)),
  )
  if (bloqueio) return `Horário bloqueado: ${bloqueio.motivo || 'sem motivo informado'}.`
  if (!dentroJornada) return 'Horário fora da jornada de trabalho do profissional.'
  return null
}

// Modal para criar/editar um agendamento. `agendamento` = null cria um novo.
export default function AgendamentoModal({ open, onClose, agendamento, dataInicial, horaInicial }) {
  const { clientes, funcionarios, agendamentos, servicos, materiais, jornadas, bloqueios, locais, loja } = useData()
  const { usuario, moduloAtivo, agenda } = useAcesso()
  const [form] = Form.useForm()
  const [verHistorico, setVerHistorico] = useState(false)
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
    agenda.criarParaOutros
      ? f.ativo && (!comServicos || servico?.funcionarioIds.includes(f.id))
      : proprio(f.id),
  )

  // Locais permitidos para o serviço (o já gravado no agendamento continua na lista mesmo se inativo)
  const permitidos = (s) => locaisDoServico(comServicos ? s : null, locais.itens)
  const opcoesLocal = [
    ...permitidos(servico),
    ...locais.itens.filter((l) => l.id === agendamento?.localId && !permitidos(servico).includes(l)),
  ]
  // Outro agendamento ativo usa o local no horário informado? (v = valores do formulário)
  const ocupado = (localId, { data, hora, duracao } = valores) => {
    if (!data || !hora) return false
    const ini = hora.hour() * 60 + hora.minute()
    return localOcupado(localId, data.format('YYYY-MM-DD'), ini, ini + (duracao ?? 0), agendamentos.itens, agendamento?.id)
  }
  const localEscolhido = locais.itens.find((l) => l.id === valores.localId)

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
        return `${m.quantidade} ${mat?.unidade ?? ''} ${mat?.nome ?? ''}`.trim()
      })
      .join(', ')

  const profissionalEscolhido = funcionarios.itens.find((f) => f.id === valores.funcionarioId)
  const aviso = avisoDisponibilidade(valores, profissionalEscolhido, jornadas.itens, bloqueios.itens)

  useEffect(() => {
    if (!open) return
    if (agendamento) {
      form.setFieldsValue({
        ...agendamento,
        data: dayjs(agendamento.data),
        hora: dayjs(agendamento.hora, 'HH:mm'),
      })
    } else {
      form.resetFields()
      form.setFieldsValue({
        data: dataInicial ?? dayjs(),
        hora: horaInicial ? dayjs(horaInicial, 'HH:mm') : undefined,
        duracao: 30,
        status: 'agendado',
        funcionarioId: agenda.criarParaOutros ? undefined : usuario?.id,
      })
    }
  }, [open, agendamento, dataInicial, horaInicial, form, agenda.criarParaOutros, usuario?.id])

  const salvar = async () => {
    const campos = await form.validateFields()
    const dados = {
      ...campos,
      data: campos.data.format('YYYY-MM-DD'),
      hora: campos.hora.format('HH:mm'),
    }
    if (agendamento) agendamentos.atualizar(agendamento.id, dados)
    else agendamentos.adicionar(dados)
    onClose()
  }

  const titulo = somenteLeitura ? 'Agendamento' : agendamento ? 'Editar agendamento' : 'Novo agendamento'

  return (
    <Modal
      title={titulo}
      open={open}
      onOk={salvar}
      onCancel={onClose}
      okText="Salvar"
      footer={somenteLeitura ? <Button onClick={onClose}>Fechar</Button> : undefined}
    >
      <Form form={form} layout="vertical" disabled={somenteLeitura}>
        <Form.Item name="clienteId" label="Cliente" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            options={clientes.itens.map((c) => ({ value: c.id, label: nomeCompleto(c) }))}
          />
        </Form.Item>
        <ResumoCliente clienteId={valores.clienteId} agendamentoId={agendamento?.id} onAbrir={() => setVerHistorico(true)} />
        {comServicos && (
          <Form.Item name="servicoId" label="Serviço" rules={[{ required: true }]}>
            <Select
              showSearch
              optionFilterProp="label"
              onChange={trocarServico}
              options={servicosDisponiveis.map((s) =>({ value: s.id, label: `${s.nome} (${s.duracao} min)` }))}
            />
          </Form.Item>
        )}
        <Form.Item name="funcionarioId" label="Profissional" rules={[{ required: true }]}>
          <Select
            disabled={!agenda.criarParaOutros || (comServicos && !servico)}
            placeholder={comServicos && !servico ? 'Escolha o serviço primeiro' : 'Selecione'}
            options={profissionais.map((f) => ({ value: f.id, label: `${f.nome} (${f.cargo})` }))}
          />
        </Form.Item>
        {resumoMateriais && (
          <Alert type="info" showIcon title={`Materiais: ${resumoMateriais}`} style={{ marginBottom: 16 }} />
        )}
        <Form.Item label="Data e horário" required style={{ marginBottom: 0 }}>
          <Form.Item name="data" rules={[{ required: true }]} style={{ display: 'inline-block', width: '40%', marginRight: 8 }}>
            <DatePicker format="DD/MM/YYYY" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="hora" rules={[{ required: true }]} style={{ display: 'inline-block', width: '25%', marginRight: 8 }}>
            <TimePicker format="HH:mm" minuteStep={15} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="duracao" rules={[{ required: true }]} style={{ display: 'inline-block', width: 'calc(35% - 16px)' }}>
            <InputNumber min={15} step={15} suffix="min" style={{ width: '100%' }} />
          </Form.Item>
        </Form.Item>
        {aviso && !somenteLeitura && <Alert type="warning" showIcon title={aviso} style={{ marginBottom: 16 }} />}
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
                    ? Promise.reject(new Error('Já existe outro agendamento aqui neste horário.'))
                    : Promise.resolve(),
              },
            ]}
          >
            <Select
              disabled={comServicos && !servico}
              placeholder={comServicos && !servico ? 'Escolha o serviço primeiro' : 'Selecione'}
              options={opcoesLocal.map((l) => ({
                value: l.id,
                disabled: ocupado(l.id),
                label: (
                  <>
                    {l.nome} <Tag color={tiposLocal[l.tipo]?.color}>{tiposLocal[l.tipo]?.label}</Tag>
                    {ocupado(l.id) && <Tag>Ocupado</Tag>}
                    {!l.ativo && <Tag>Inativo</Tag>}
                  </>
                ),
              }))}
            />
          </Form.Item>
        )}
        {comLocais && localEscolhido?.tipo === 'online' && (
          <Form.Item
            name="linkReuniao"
            label="Link da reunião"
            extra={localEscolhido.linkPadrao ? 'Se ficar vazio, usa o link fixo do local.' : 'Este local não tem link fixo; informe o link deste atendimento.'}
            rules={[{ type: 'url', message: 'Informe um link válido (https://...)' }]}
          >
            <Input placeholder={localEscolhido.linkPadrao ?? 'https://...'} />
          </Form.Item>
        )}
        <Form.Item
          name="preco"
          label="Preço"
          extra={comServicos ? 'Copiado do serviço; mudanças futuras no serviço não alteram este valor.' : undefined}
        >
          <InputNumber min={0} step={10} prefix="R$" style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="status" label="Status">
          <Select options={Object.entries(statusAgendamento).map(([value, s]) => ({ value, label: s.label }))} />
        </Form.Item>
      </Form>
      <UltimaAlteracao item={agendamento} />
      <HistoricoCliente clienteId={valores.clienteId} open={verHistorico} onClose={() => setVerHistorico(false)} />
    </Modal>
  )
}
