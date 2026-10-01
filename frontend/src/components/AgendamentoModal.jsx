import { useEffect } from 'react'
import { Modal, Form, Select, DatePicker, TimePicker, InputNumber, Alert } from 'antd'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { statusAgendamento } from '../data/mock.js'

// Modal para criar/editar um agendamento. `agendamento` = null cria um novo.
export default function AgendamentoModal({ open, onClose, agendamento, dataInicial }) {
  const { clientes, funcionarios, agendamentos, servicos, materiais } = useData()
  const [form] = Form.useForm()
  const servicoId = Form.useWatch('servicoId', form)
  const servico = servicos.itens.find((s) => s.id === servicoId)

  // Só aparecem os profissionais habilitados para o serviço escolhido
  const profissionais = funcionarios.itens.filter((f) => f.ativo && servico?.funcionarioIds.includes(f.id))

  const trocarServico = (id) => {
    const novo = servicos.itens.find((s) => s.id === id)
    form.setFieldsValue({ duracao: novo?.duracao })
    if (!novo?.funcionarioIds.includes(form.getFieldValue('funcionarioId'))) {
      form.setFieldsValue({ funcionarioId: novo?.funcionarioIds.length === 1 ? novo.funcionarioIds[0] : undefined })
    }
  }

  const resumoMateriais = servico?.materiais
    ?.map((m) => {
      const mat = materiais.itens.find((x) => x.id === m.materialId)
      return `${m.quantidade} ${mat?.unidade ?? ''} ${mat?.nome ?? ''}`.trim()
    })
    .join(', ')

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
      form.setFieldsValue({ data: dataInicial ?? dayjs(), duracao: 30, status: 'agendado' })
    }
  }, [open, agendamento, dataInicial, form])

  const salvar = async () => {
    const valores = await form.validateFields()
    const dados = {
      ...valores,
      data: valores.data.format('YYYY-MM-DD'),
      hora: valores.hora.format('HH:mm'),
    }
    if (agendamento) agendamentos.atualizar(agendamento.id, dados)
    else agendamentos.adicionar(dados)
    onClose()
  }

  return (
    <Modal
      title={agendamento ? 'Editar agendamento' : 'Novo agendamento'}
      open={open}
      onOk={salvar}
      onCancel={onClose}
      okText="Salvar"
    >
      <Form form={form} layout="vertical">
        <Form.Item name="clienteId" label="Cliente" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            options={clientes.itens.map((c) => ({ value: c.id, label: c.nome }))}
          />
        </Form.Item>
        <Form.Item name="servicoId" label="Serviço" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            onChange={trocarServico}
            options={servicos.itens.map((s) => ({ value: s.id, label: `${s.nome} (${s.duracao} min)` }))}
          />
        </Form.Item>
        <Form.Item name="funcionarioId" label="Profissional" rules={[{ required: true }]}>
          <Select
            disabled={!servico}
            placeholder={servico ? 'Selecione' : 'Escolha o serviço primeiro'}
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
          <Form.Item name="duracao" style={{ display: 'inline-block', width: 'calc(35% - 16px)' }}>
            <InputNumber min={15} step={15} suffix="min" style={{ width: '100%' }} />
          </Form.Item>
        </Form.Item>
        <Form.Item name="status" label="Status">
          <Select options={Object.entries(statusAgendamento).map(([value, s]) => ({ value, label: s.label }))} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
