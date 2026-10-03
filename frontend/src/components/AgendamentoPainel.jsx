import { useEffect, useRef, useState } from 'react'
import { Alert, App, Button, Col, DatePicker, Flex, Form, Input, InputNumber, Row, Select, Spin, TimePicker } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { statusAgendamento } from '../data/dominio.js'
import { rotulosLocal } from '../data/locais.js'
import { agoraNaLoja, lerDataHora } from '../data/api/conversao.js'
import {
  aceitarSolicitacao,
  ajustarMateriais,
  criarAgendamento,
  editarAgendamento,
  mudarStatusAgendamento,
  recusarSolicitacao,
} from '../data/api/agendamentos.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import {
  LIBERAM_HORARIO,
  STATUS_FINAIS,
  opcoesDeStatus,
  useAgendamento,
  useApoioAgendamento,
  useBuscaClientes,
  useDisponibilidade,
} from '../data/useAgendamentos.js'
import { horaCurta, nomeCompleto } from '../utils/formatos.js'
import PainelFormulario from './base/PainelFormulario.jsx'
import { usePainel } from './base/usePainel.js'
import Etiqueta from './base/Etiqueta.jsx'
import { EtiquetaTipoLocal } from './Etiquetas.jsx'
import UltimaAlteracao from './UltimaAlteracao.jsx'
import HistoricoCliente from './HistoricoCliente.jsx'
import ResumoCliente from './ResumoCliente.jsx'
import './agenda/agenda.css'

// Erros 422 da API cujo campo tem outro nome no formulário
const MAPA_ERROS = { inicio: 'hora', duracao_minutos: 'duracao' }
// Conflitos e regras que o servidor devolve sem campo (409 e 422): campo do formulário que fica marcado
const CAMPO_DA_MENSAGEM = [
  [/profissional já tem um agendamento|horário indisponível/i, 'hora'],
  [/local já está ocupado|local não é permitido|local está inativo|escolha o local/i, 'localId'],
  [/fora da jornada|horário bloqueado/i, 'hora'],
  [/profissional não realiza|profissional está inativo|profissional não encontrado/i, 'funcionarioId'],
  [/serviço está inativo|escolha o serviço|serviço não encontrado/i, 'servicoId'],
  [/cliente está inativo|cliente não encontrado/i, 'clienteId'],
  [/motivo do cancelamento/i, 'motivoCancelamento'],
  [/duração/i, 'duracao'],
]

const textoStatus = (s) => statusAgendamento[s]?.label ?? 'Situação desconhecida'

// data (dia) + hora (horário) dos campos -> dayjs do início, na hora da loja
const juntarInicio = (data, hora) =>
  data?.isValid?.() && hora?.isValid?.() ? data.hour(hora.hour()).minute(hora.minute()).second(0).millisecond(0) : null

const materiaisDoForm = (lista) =>
  (lista ?? []).filter((m) => m?.materialId).map((m) => ({ materialId: m.materialId, quantidade: Number(m.quantidade) }))

const mesmosMateriais = (a, b) => {
  const chave = (lista) =>
    JSON.stringify(
      materiaisDoForm(lista)
        .map((m) => [m.materialId, Math.round(m.quantidade * 100)])
        .sort(([x], [y]) => String(x).localeCompare(String(y))),
    )
  return chave(a) === chave(b)
}

// Valores do formulário a partir do agendamento da API
function valoresDe(a) {
  const inicio = lerDataHora(a.inicio)
  return {
    clienteId: a.clienteId ?? undefined,
    servicoId: a.servicoId ?? undefined,
    funcionarioId: a.funcionarioId ?? undefined,
    localId: a.localId ?? undefined,
    linkReuniao: a.linkReuniao ?? undefined,
    data: inicio ?? undefined,
    hora: inicio ?? undefined,
    duracao: a.duracao || undefined,
    preco: a.preco ?? undefined,
    status: a.status ?? undefined,
    observacoes: a.observacoes ?? undefined,
    motivoCancelamento: a.motivoCancelamento ?? undefined,
    ...(a.materiais && { materiais: a.materiais.map((m) => ({ materialId: m.materialId, quantidade: m.quantidade })) }),
  }
}

// Painel para criar/editar um agendamento. `agendamento` = null cria um novo.
// onSalvo(agendamento | undefined): a tela recarrega a lista do servidor (também após 404).
// O cabeçalho mostra o cliente assim que ele é escolhido. O histórico do cliente abre no lugar
// do agendamento (fecha um, abre o outro), nunca por cima.
export default function AgendamentoPainel({ open, onClose, agendamento, dataInicial, horaInicial, onSalvo }) {
  const { usuario, perfil, loja, moduloAtivo, agenda } = useAcesso()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const historico = usePainel()
  const valores = Form.useWatch([], form) ?? {}
  const [salvando, setSalvando] = useState(false)
  // Conflito (409) ou regra (422 sem campo) devolvida pelo servidor: fica junto do formulário,
  // no campo relacionado (campo) ou num aviso no topo (campo = null). { mensagem, campo }
  const [erroServidor, setErroServidor] = useState(null)
  const [clienteEscolhido, setClienteEscolhido] = useState(null) // { id, nome } escolhido na busca
  const caixaErro = useRef(null)

  const editando = !!agendamento?.id
  const comServicos = moduloAtivo('servicos')
  const comMateriais = moduloAtivo('materiais')
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja)

  // Detalhe atualizado (com os materiais); até chegar, vale o que a lista trouxe
  const detalhe = useAgendamento(agendamento?.id, { ativo: open && editando })
  const original = editando ? (detalhe.agendamento?.id === agendamento.id ? detalhe.agendamento : agendamento) : null
  const statusOriginal = original?.status ?? null
  const finalizado = STATUS_FINAIS.includes(statusOriginal)
  const podeReabrir = !!perfil?.acessoTotal
  const somenteLeitura = editando ? !agenda.editar(original) || (finalizado && !podeReabrir) : !agenda.criar

  const apoioConsulta = useApoioAgendamento({ ativo: open && !somenteLeitura })
  const apoio = apoioConsulta.apoio
  const busca = useBuscaClientes({ ativo: open && !somenteLeitura })

  // Ao abrir: limpa o erro do servidor (calculado na renderização, sem efeito)
  const [abertoAntes, setAbertoAntes] = useState(open)
  if (open !== abertoAntes) {
    setAbertoAntes(open)
    if (open) {
      setErroServidor(null)
      setClienteEscolhido(null)
    }
  }

  // Detalhe chegou: atualiza o formulário se ninguém mexeu ainda (os materiais só vêm no detalhe)
  const detalheCarregado = detalhe.agendamento
  useEffect(() => {
    if (!open || !detalheCarregado || detalheCarregado.id !== agendamento?.id) return
    if (!form.isFieldsTouched()) form.setFieldsValue(valoresDe(detalheCarregado))
    else if (detalheCarregado.materiais && !form.isFieldTouched('materiais')) {
      form.setFieldsValue({ materiais: valoresDe(detalheCarregado).materiais })
    }
  }, [open, detalheCarregado, agendamento?.id, form])

  // Registro que não existe mais (excluído ou sem acesso): fecha o painel e atualiza a lista
  const naoEncontrado = useRef(null)
  useEffect(() => {
    naoEncontrado.current = () => {
      onClose()
      onSalvo?.()
    }
  })
  const erroDetalhe = detalhe.erro
  useEffect(() => {
    if (open && erroDetalhe?.status === 404) tratarErro(erroDetalhe, { aoNaoEncontrado: () => naoEncontrado.current?.() })
  }, [open, erroDetalhe, tratarErro])

  // --- Listas do formulário (do servidor; o que o agendamento já tem continua visível mesmo inativo) ---
  const servicosApoio = apoio?.servicos ?? []
  const servico = servicosApoio.find((s) => s.id === valores.servicoId)
  const servicoAtual = original?.servicoId && { id: original.servicoId, nome: original.servicoNome ?? 'Serviço', duracao: original.duracao }
  const servicos = [
    ...servicosApoio,
    ...(servicoAtual && !servicosApoio.some((s) => s.id === servicoAtual.id) ? [servicoAtual] : []),
  ]

  const profissionaisApoio = apoio?.profissionais ?? []
  const habilitados = agenda.criarParaOutros && comServicos && servico ? servico.funcionarioIds : null
  const profissionalAtual = original?.funcionarioId && { id: original.funcionarioId, nome: original.funcionarioNome ?? '—' }
  const profissionais = [
    ...profissionaisApoio.filter((f) => !habilitados || habilitados.includes(f.id) || f.id === original?.funcionarioId),
    ...(profissionalAtual && !profissionaisApoio.some((f) => f.id === profissionalAtual.id) ? [profissionalAtual] : []),
  ]

  const locaisApoio = apoio?.locais ?? []
  // Serviço sem local vinculado = qualquer local ativo (AGE-12)
  const permitidos = (s) => {
    const vinculados = comServicos ? (s?.localIds ?? []) : []
    return locaisApoio.filter((l) => vinculados.length === 0 || vinculados.includes(l.id))
  }
  const localAtual = original?.localId && { id: original.localId, nome: original.localNome ?? '—', tipo: original.localTipo }
  const opcoesLocal = [
    ...permitidos(servico),
    ...(localAtual && !permitidos(servico).some((l) => l.id === localAtual.id) ? [localAtual] : []),
  ]
  const localEscolhido = opcoesLocal.find((l) => l.id === valores.localId)
  const linkPadrao = locaisApoio.find((l) => l.id === valores.localId)?.linkPadrao ?? null
  const semServico = comServicos && !valores.servicoId

  // --- Disponibilidade (a API decide; aqui só avisa antes de salvar) ---
  const inicioEscolhido = juntarInicio(valores.data, valores.hora)
  const ocupaHorario = !LIBERAM_HORARIO.includes(valores.status)
  const { disponibilidade, consultando, recarregar: reconsultar } = useDisponibilidade(
    { funcionarioId: valores.funcionarioId, inicio: inicioEscolhido, duracao: valores.duracao, agendamentoId: agendamento?.id },
    { ativo: open && !somenteLeitura && ocupaHorario },
  )
  const locaisOcupados = disponibilidade?.locaisOcupados ?? []
  const localOcupado = (id) => locaisOcupados.includes(id)

  // --- Cliente: busca no servidor; o escolhido continua visível mesmo fora do resultado ---
  const clienteAtual =
    clienteEscolhido?.id && clienteEscolhido.id === valores.clienteId
      ? clienteEscolhido
      : original?.clienteId && original.clienteId === valores.clienteId
        ? { id: original.clienteId, nome: original.clienteNome ?? 'Cliente' }
        : null
  const opcoesCliente = [
    ...(clienteAtual && !busca.itens.some((c) => c.id === clienteAtual.id)
      ? [{ value: clienteAtual.id, label: clienteAtual.nome }]
      : []),
    ...busca.itens.map((c) => ({ value: c.id, label: nomeCompleto(c) || 'Cliente sem nome', telefone: c.telefone })),
  ]
  const semClientes = busca.buscando ? (
    <Flex justify="center">
      <Spin size="small" />
    </Flex>
  ) : busca.erro ? (
    busca.erro.mensagem
  ) : busca.curto ? (
    'Digite pelo menos 2 letras do nome, o telefone ou o CPF.'
  ) : (
    'Nenhum cliente ativo encontrado.'
  )

  // --- Situação ---
  const opcoesStatus = opcoesDeStatus(statusOriginal, podeReabrir).map((value) => ({ value, label: textoStatus(value) }))
  const cancelando = valores.status === 'cancelado'

  // --- Materiais usados (só na edição, com o módulo ativo) ---
  const servicoMudou = editando && (valores.servicoId ?? null) !== (original?.servicoId ?? null)
  const baseMateriais = original?.materiais ?? null // null = ainda não veio do detalhe
  const materiaisEditaveis = !somenteLeitura && !finalizado && !servicoMudou && baseMateriais != null
  const catalogo = new Map([
    ...(baseMateriais ?? []).map((m) => [m.materialId, m]),
    ...(apoio?.materiais ?? []).map((m) => [m.id, { materialId: m.id, nome: m.nome, unidade: m.unidade }]),
  ])
  const usados = new Set((valores.materiais ?? []).map((m) => m?.materialId))
  const paraAdicionar = (apoio?.materiais ?? []).filter((m) => !usados.has(m.id))

  const resumoMateriais =
    comMateriais &&
    !editando &&
    servico?.materiais
      ?.map((m) => `${m.quantidade} ${m.unidade} de ${m.nome}`.replace(/\s+/g, ' ').trim())
      .join(', ')

  // Serviço preenche duração e preço; local e profissional são mantidos se continuarem válidos
  const trocarServico = (id) => {
    const novo = servicosApoio.find((s) => s.id === id)
    if (!novo) return
    form.setFieldsValue({ duracao: novo.duracao ?? undefined, preco: novo.preco ?? undefined })
    if (comLocais && !permitidos(novo).some((l) => l.id === form.getFieldValue('localId'))) {
      const lista = permitidos(novo)
      form.setFieldsValue({ localId: lista.length === 1 ? lista[0].id : undefined })
    }
    if (agenda.criarParaOutros && !novo.funcionarioIds.includes(form.getFieldValue('funcionarioId'))) {
      form.setFieldsValue({ funcionarioId: novo.funcionarioIds.length === 1 ? novo.funcionarioIds[0] : undefined })
    }
  }

  const valoresIniciais = editando
    ? valoresDe(original)
    : {
        data: dataInicial ?? agoraNaLoja(),
        hora: horaInicial ? lerDataHora(`2000-01-01T${horaInicial}`) : undefined,
        duracao: 30,
        status: 'agendado',
        funcionarioId: agenda.criarParaOutros ? undefined : usuario?.id,
      }

  const mostrarErroServidor = (e) => {
    const mapeado = CAMPO_DA_MENSAGEM.find(([padrao]) => padrao.test(e.mensagem ?? ''))?.[1]
    const campo = mapeado && form.getFieldsError().some((f) => f.name[0] === mapeado) ? mapeado : null
    setErroServidor({ mensagem: e.mensagem, campo })
    if (e.status === 409) reconsultar()
    if (campo) {
      form.setFields([{ name: campo, errors: [e.mensagem] }])
      form.scrollToField(campo, { block: 'center', behavior: 'smooth' })
    } else {
      requestAnimationFrame(() => caixaErro.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }))
    }
  }

  const salvar = async (campos) => {
    const inicio = juntarInicio(campos.data, campos.hora)
    const dados = { ...campos, inicio }
    setErroServidor(null)
    setSalvando(true)
    try {
      let resultado
      if (!editando) {
        resultado = await criarAgendamento(dados)
        message.success(`Agendado para ${inicio.format('DD/MM')} às ${horaCurta(inicio.format('HH:mm'))}.`)
      } else {
        const id = agendamento.id
        const statusMudou = campos.status !== statusOriginal
        const materiaisMudaram =
          comMateriais && materiaisEditaveis && !mesmosMateriais(campos.materiais, baseMateriais)
        const igual = (a, b) => (a ?? null) === (b ?? null)
        const camposMudaram =
          !igual(campos.clienteId, original.clienteId) ||
          (comServicos && !igual(campos.servicoId, original.servicoId)) ||
          !igual(campos.funcionarioId, original.funcionarioId) ||
          (comLocais && !igual(campos.localId, original.localId)) ||
          (comLocais && !igual(campos.linkReuniao?.trim() || null, original.linkReuniao)) ||
          inicio.format('YYYY-MM-DDTHH:mm') !== original.inicio ||
          Number(campos.duracao) !== Number(original.duracao) ||
          !igual(campos.preco, original.preco) ||
          !igual(campos.observacoes?.trim() || null, original.observacoes)

        // Materiais antes da conclusão: depois de concluído o servidor não aceita mais (AGE-05)
        if (materiaisMudaram) resultado = await ajustarMateriais(id, materiaisDoForm(campos.materiais))
        if (camposMudaram) {
          resultado = await editarAgendamento(id, { ...dados, status: statusMudou ? campos.status : undefined })
        } else if (statusMudou && statusOriginal === 'pendente' && campos.status === 'confirmado') {
          resultado = await aceitarSolicitacao(id)
        } else if (statusMudou && statusOriginal === 'pendente' && campos.status === 'cancelado') {
          resultado = await recusarSolicitacao(id, campos.motivoCancelamento)
        } else if (statusMudou) {
          resultado = await mudarStatusAgendamento(id, campos.status, campos.motivoCancelamento)
        }
        message.success(resultado ? 'Agendamento salvo.' : 'Nada foi alterado.')
      }
      onSalvo?.(resultado)
      onClose()
    } catch (e) {
      if (e?.status === 409 || (e?.status === 422 && !e.campos?.length)) mostrarErroServidor(e)
      else {
        tratarErro(e, {
          form,
          mapa: MAPA_ERROS,
          aoNaoEncontrado: () => naoEncontrado.current?.(),
        })
      }
      // Os materiais podem ter sido gravados antes do erro: a lista e o detalhe refletem o servidor
      if (editando) {
        detalhe.recarregar()
        onSalvo?.()
      }
    } finally {
      setSalvando(false)
    }
  }

  // Mudou o horário, o profissional, o local...: o erro anterior do servidor não vale mais
  const aoMudar = (mudados) => {
    if (!erroServidor || !Object.keys(mudados).some((c) => c !== 'observacoes')) return
    if (erroServidor.campo) form.setFields([{ name: erroServidor.campo, errors: [] }])
    setErroServidor(null)
  }

  const titulo = somenteLeitura ? 'Agendamento' : editando ? 'Editar agendamento' : 'Novo agendamento'
  const avisoLeitura =
    editando && finalizado && !podeReabrir && agenda.editar(original)
      ? `Agendamento "${textoStatus(statusOriginal)}": só o Administrador pode reabrir.`
      : null

  return (
    <>
      <PainelFormulario
        titulo={titulo}
        nome={clienteAtual?.nome}
        open={open}
        form={form}
        valoresIniciais={valoresIniciais}
        somenteLeitura={somenteLeitura}
        salvando={salvando}
        textoSalvar={editando ? 'Salvar' : 'Agendar'}
        largura={560}
        onCancelar={onClose}
        onSalvar={salvar}
        onValuesChange={aoMudar}
        rodape={<UltimaAlteracao item={original} />}
      >
        {(fechar) => (
          <>
            {avisoLeitura && <Alert type="info" showIcon title={avisoLeitura} className="alerta-formulario" />}
            {apoioConsulta.erro && !somenteLeitura && (
              <Alert
                type="error"
                showIcon
                title="Não foi possível carregar serviços, profissionais e locais."
                description={apoioConsulta.erro.mensagem}
                action={
                  <Button size="small" onClick={apoioConsulta.recarregar}>
                    Tentar de novo
                  </Button>
                }
                className="alerta-formulario"
              />
            )}
            <div ref={caixaErro}>
              {erroServidor && !erroServidor.campo && (
                <Alert
                  type="error"
                  showIcon
                  title={erroServidor.mensagem}
                  closable={{ onClose: () => setErroServidor(null) }}
                  className="alerta-formulario"
                />
              )}
            </div>

            <h3 className="grupo-formulario">Cliente</h3>
            <Form.Item name="clienteId" label="Cliente" rules={[{ required: true, message: 'Escolha o cliente' }]}>
              <Select
                showSearch={{ filterOption: false, onSearch: busca.buscar }}
                placeholder="Busque pelo nome, telefone ou CPF"
                options={opcoesCliente}
                notFoundContent={semClientes}
                optionRender={(o) => (
                  <Flex justify="space-between" gap={8}>
                    <span>{o.label}</span>
                    {o.data.telefone && <span className="texto-apoio numeros">{o.data.telefone}</span>}
                  </Flex>
                )}
                popupRender={(menu) => (
                  <>
                    {menu}
                    {busca.total > busca.itens.length && (
                      <p className="texto-apoio busca-clientes-rodape">
                        Mostrando {busca.itens.length} de {busca.total}. Continue digitando para encontrar.
                      </p>
                    )}
                  </>
                )}
                onChange={(id, opcao) => setClienteEscolhido(id ? { id, nome: opcao?.label } : null)}
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
                  showSearch={{ optionFilterProp: 'label' }}
                  onChange={trocarServico}
                  loading={apoioConsulta.carregando}
                  placeholder="Selecione"
                  options={servicos.map((s) => ({
                    value: s.id,
                    label: s.duracao ? `${s.nome} (${s.duracao} min)` : s.nome,
                  }))}
                />
              </Form.Item>
            )}
            <Form.Item name="funcionarioId" label="Profissional" rules={[{ required: true, message: 'Escolha o profissional' }]}>
              <Select
                disabled={!agenda.criarParaOutros || semServico}
                loading={apoioConsulta.carregando}
                placeholder={semServico ? 'Escolha o serviço primeiro' : 'Selecione'}
                options={profissionais.map((f) => ({ value: f.id, label: f.cargo ? `${f.nome} (${f.cargo})` : f.nome }))}
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
                  <InputNumber min={5} max={1440} step={15} precision={0} suffix="min" />
                </Form.Item>
              </Col>
            </Row>
            {!somenteLeitura && ocupaHorario && (
              <div aria-live="polite">
                {consultando && <p className="texto-apoio agendamento-nota">Conferindo o horário…</p>}
                {disponibilidade?.aviso && <Alert type="warning" showIcon title={disponibilidade.aviso} className="alerta-formulario" />}
                {disponibilidade?.profissionalOcupado && (
                  <Alert
                    type="warning"
                    showIcon
                    title="O profissional já tem outro agendamento neste horário."
                    className="alerta-formulario"
                  />
                )}
              </div>
            )}
            {comLocais && (
              <Form.Item
                name="localId"
                label={rotulos.singular}
                rules={[{ required: true, message: 'Escolha onde será o atendimento' }]}
                extra={
                  !somenteLeitura && ocupaHorario && valores.localId && localOcupado(valores.localId)
                    ? 'Já existe outro agendamento aqui neste horário. Escolha outro horário ou local.'
                    : undefined
                }
              >
                <Select
                  disabled={semServico}
                  loading={apoioConsulta.carregando}
                  placeholder={semServico ? 'Escolha o serviço primeiro' : 'Selecione'}
                  options={opcoesLocal.map((l) => {
                    const ocupado = ocupaHorario && localOcupado(l.id)
                    return {
                      value: l.id,
                      disabled: ocupado && l.id !== valores.localId,
                      label: (
                        <span className="local-info">
                          {l.nome} {l.tipo && <EtiquetaTipoLocal tipo={l.tipo} />}
                          {ocupado && <Etiqueta tom="atencao">Ocupado</Etiqueta>}
                        </span>
                      ),
                    }
                  })}
                />
              </Form.Item>
            )}
            {comLocais && localEscolhido?.tipo === 'online' && (
              <Form.Item
                name="linkReuniao"
                label="Link da reunião"
                extra={linkPadrao ? 'Se ficar vazio, usa o link fixo do local.' : 'Informe o link deste atendimento, se o local não tiver link fixo.'}
                rules={[{ type: 'url', message: 'Informe um link completo, começando com https://' }]}
              >
                <Input placeholder={linkPadrao ?? 'https://'} maxLength={500} />
              </Form.Item>
            )}

            {editando && comMateriais && (
              <>
                <h3 className="grupo-formulario">Materiais usados</h3>
                {servicoMudou ? (
                  <p className="texto-apoio agendamento-nota">Ao trocar o serviço, os materiais passam a ser os do novo serviço.</p>
                ) : baseMateriais == null ? (
                  detalhe.erro ? (
                    <Alert
                      type="error"
                      showIcon
                      title="Não foi possível carregar os materiais."
                      action={
                        <Button size="small" onClick={detalhe.recarregar}>
                          Tentar de novo
                        </Button>
                      }
                      className="alerta-formulario"
                    />
                  ) : (
                    <p className="texto-apoio agendamento-nota">Carregando os materiais…</p>
                  )
                ) : (
                  <Form.List name="materiais">
                    {(linhas, { add, remove }) => (
                      <>
                        {linhas.length === 0 && <p className="texto-apoio agendamento-nota">Nenhum material neste atendimento.</p>}
                        {linhas.map((linha) => {
                          const materialId = form.getFieldValue(['materiais', linha.name, 'materialId'])
                          const material = catalogo.get(materialId)
                          return (
                            <Flex key={linha.key} align="flex-start" gap={8}>
                              {/* preserve: a linha remonta quando o detalhe chega; o valor não pode sumir */}
                              <Form.Item name={[linha.name, 'materialId']} hidden preserve>
                                <Input />
                              </Form.Item>
                              <span className="material-usado-nome">{material?.nome ?? 'Material'}</span>
                              <Form.Item
                                name={[linha.name, 'quantidade']}
                                preserve
                                rules={[{ required: true, message: 'Informe a quantidade' }]}
                              >
                                <InputNumber
                                  min={0.01}
                                  max={1000000}
                                  step={1}
                                  precision={2}
                                  decimalSeparator=","
                                  suffix={material?.unidade}
                                  disabled={!materiaisEditaveis}
                                  aria-label={`Quantidade de ${material?.nome ?? 'material'}`}
                                />
                              </Form.Item>
                              {materiaisEditaveis && (
                                <Button
                                  type="text"
                                  danger
                                  icon={<DeleteOutlined />}
                                  aria-label={`Tirar ${material?.nome ?? 'material'}`}
                                  onClick={() => remove(linha.name)}
                                />
                              )}
                            </Flex>
                          )
                        })}
                        {materiaisEditaveis && paraAdicionar.length > 0 && (
                          <Select
                            value={null}
                            placeholder={
                              <span>
                                <PlusOutlined /> Adicionar material
                              </span>
                            }
                            aria-label="Adicionar material"
                            showSearch={{ optionFilterProp: 'label' }}
                            options={paraAdicionar.map((m) => ({ value: m.id, label: m.unidade ? `${m.nome} (${m.unidade})` : m.nome }))}
                            onChange={(id) => id && add({ materialId: id, quantidade: 1 })}
                          />
                        )}
                        {statusOriginal === 'concluido' && <p className="texto-apoio agendamento-nota">Já baixados do estoque na conclusão.</p>}
                        {materiaisEditaveis && (
                          <p className="texto-apoio agendamento-nota">Ajuste o que foi usado antes de concluir: na conclusão eles saem do estoque.</p>
                        )}
                      </>
                    )}
                  </Form.List>
                )}
              </>
            )}

            <h3 className="grupo-formulario">Valor e situação</h3>
            <Row gutter={12}>
              <Col xs={24} sm={12}>
                <Form.Item
                  name="preco"
                  label="Preço"
                  extra={comServicos ? 'Copiado do serviço. Mudar o serviço depois não altera este valor.' : undefined}
                >
                  <InputNumber min={0} max={99999999.99} step={10} precision={2} prefix="R$" decimalSeparator="," />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="status" label="Situação">
                  <Select options={opcoesStatus} />
                </Form.Item>
              </Col>
            </Row>
            {cancelando && (
              <Form.Item
                name="motivoCancelamento"
                label="Motivo do cancelamento"
                rules={[{ required: statusOriginal !== 'cancelado', whitespace: true, message: 'Informe o motivo do cancelamento' }]}
              >
                <Input.TextArea rows={2} maxLength={2000} showCount />
              </Form.Item>
            )}
            <Form.Item name="observacoes" label="Observações">
              <Input.TextArea rows={3} maxLength={2000} />
            </Form.Item>
          </>
        )}
      </PainelFormulario>
      <HistoricoCliente clienteId={historico.registro?.id} open={historico.aberto} onClose={historico.fechar} />
    </>
  )
}
