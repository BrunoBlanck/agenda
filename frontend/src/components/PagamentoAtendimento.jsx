import { useId, useState } from 'react'
import { Alert, App, Button, Flex, Form, InputNumber } from 'antd'
import { CheckOutlined } from '@ant-design/icons'
import { formasPagamento } from '../data/dominio.js'
import { registrarPagamento } from '../data/useAgendamentos.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { fraseDoPagamento, quandoFoiPago, resumoPagamento } from '../utils/pagamento.js'
import { EtiquetaStatus } from './Etiquetas.jsx'
import './pagamento.css'

const FORMAS = Object.entries(formasPagamento)

// Ao abrir o registro, o foco vai para a primeira forma (referência estável: roda só ao montar)
const focarPrimeiraForma = (el) => {
  el?.querySelector('input')?.focus({ preventScroll: true })
  el?.closest('.pagamento-registro')?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
}

// Aviso que aparece embaixo do botão: rola até ele para não ficar cortado pela borda do painel
const rolarAteVer = (el) => el?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })

// Situações em que a seção aparece (as demais não têm o que pagar)
const comSecao = (status, podeRegistrar) =>
  status === 'concluido' || (podeRegistrar && (status === 'confirmado' || status === 'agendado'))

// Erros de campo da API: [{ campo, mensagem }] (cliente HTTP) ou { campo: mensagem } (contrato)
const errosDeCampo = (campos) =>
  Array.isArray(campos)
    ? Object.fromEntries(campos.map((c) => [c.campo, c.mensagem]))
    : campos && typeof campos === 'object'
      ? campos
      : {}

// Seção "Pagamento" do painel do agendamento (AGE-26 a AGE-29). Concluir = registrar o pagamento,
// sempre a partir de Confirmado. Fica dentro do formulário do painel, mas não usa campos do Form:
// escolher a forma não conta como alteração do agendamento.
// Os botões e as opções nunca enviam o formulário do painel (Enter registra o pagamento).
// podeRegistrar: o usuário altera este agendamento. alterado: o formulário tem alterações não salvas
// (abrir e confirmar avisam e não enviam: o pagamento traz o agendamento do servidor para o formulário).
// reabrindo: o Administrador mudou a Situação de um concluído (o pagamento será desfeito ao salvar).
// onEnviando(bool): o painel trava o formulário enquanto o pagamento é gravado.
// onPago(agendamento): já Concluído. onConflito() → Promise<agendamento atual | null>: reconsultar.
// onNaoEncontrado: fechar o painel.
export default function PagamentoAtendimento({
  agendamento,
  podeRegistrar,
  alterado,
  reabrindo,
  onEnviando,
  onPago,
  onConflito,
  onNaoEncontrado,
}) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const id = useId()
  const [aberto, setAberto] = useState(false)
  const [forma, setForma] = useState(null)
  const [valor, setValor] = useState(null)
  const [erros, setErros] = useState({})
  const [erro, setErro] = useState(null)
  const [avisoAlterado, setAvisoAlterado] = useState(false)
  const [enviando, setEnviando] = useState(false)

  const status = agendamento?.status
  const pagamento = agendamento?.pagamento ?? null
  const confirmado = status === 'confirmado'
  // Pendente, cancelado e não compareceu: sem seção. Agendado só interessa a quem pode confirmar.
  if (!comSecao(status, podeRegistrar)) return null
  const registrando = aberto && confirmado && podeRegistrar

  const abrir = () => {
    if (alterado) {
      setAvisoAlterado(true)
      return
    }
    setForma(null)
    setValor(agendamento.preco ?? null)
    setErros({})
    setErro(null)
    setAvisoAlterado(false)
    setAberto(true)
  }

  const voltar = () => {
    setAberto(false)
    setErros({})
    setErro(null)
  }

  const validar = () => {
    const novos = {}
    if (!forma) novos.forma = 'Escolha a forma de pagamento'
    if (valor == null || valor === '') novos.valor = 'Informe o valor pago'
    setErros(novos)
    return Object.keys(novos).length === 0
  }

  const confirmar = async () => {
    if (enviando) return
    // Editaram o formulário com o registro aberto: pagar agora trocaria a edição pelo que está salvo
    if (alterado) {
      setAvisoAlterado(true)
      return
    }
    if (!validar()) return
    setErro(null)
    setAvisoAlterado(false)
    setEnviando(true)
    onEnviando?.(true)
    try {
      const resultado = await registrarPagamento(agendamento.id, { forma, valor: Number(valor) })
      setAberto(false)
      message.success('Pagamento registrado. Atendimento concluído.')
      onPago?.(resultado)
    } catch (e) {
      if (e?.status === 401 || e?.status === 404) {
        tratarErro(e, { aoNaoEncontrado: onNaoEncontrado })
      } else {
        const campos = errosDeCampo(e?.campos)
        const doFormulario = { forma: campos.forma, valor: campos.valor }
        if (doFormulario.forma || doFormulario.valor) setErros(doFormulario)
        else setErro(e?.mensagem ?? 'Não foi possível registrar o pagamento. Tente de novo.')
        if (e?.status === 409) {
          const atual = await onConflito?.()
          // Cancelado ou não compareceu: a seção some junto com o aviso, então diz por que não passou
          if (atual && !comSecao(atual.status, podeRegistrar)) message.warning(e.mensagem ?? 'A situação do atendimento mudou.')
        }
      }
    } finally {
      setEnviando(false)
      onEnviando?.(false)
    }
  }

  // Enter no valor ou numa forma confirma o pagamento (e não envia o formulário do agendamento)
  const aoEnter = (e) => {
    e.preventDefault()
    confirmar()
  }

  const avisoDeAlteracoes = avisoAlterado && alterado && (
    <div ref={rolarAteVer} className="pagamento-aviso">
      <Alert type="warning" showIcon title="Salve ou descarte as alterações antes de registrar o pagamento." />
    </div>
  )

  const quando = pagamento && quandoFoiPago(pagamento)

  return (
    <>
      <h3 className="grupo-formulario">Pagamento</h3>
      <div aria-live="polite">
        {erro && (
          <Alert type="error" showIcon title={erro} closable={{ onClose: () => setErro(null) }} className="alerta-formulario" />
        )}
      </div>

      {status === 'concluido' &&
        (pagamento ? (
          <div className="pagamento-resumo">
            <p className="pagamento-resumo-forma numeros">{fraseDoPagamento(pagamento)}</p>
            {quando && <p className="texto-apoio pagamento-resumo-quando">{quando}</p>}
          </div>
        ) : (
          <p className="texto-apoio agendamento-nota">Pagamento não registrado.</p>
        ))}
      {status === 'concluido' && reabrindo && pagamento && (
        <Alert
          type="warning"
          showIcon
          title="Ao salvar, este pagamento é desfeito e o atendimento volta a ficar em aberto."
          className="alerta-formulario"
        />
      )}

      {status === 'agendado' && <p className="texto-apoio agendamento-nota">Confirme o atendimento para registrar o pagamento.</p>}

      {confirmado && podeRegistrar && !registrando && (
        <div className="pagamento-pendente">
          <p className="texto-apoio">Ao fim do atendimento, registre o pagamento para concluí-lo.</p>
          <Button onClick={abrir}>Registrar pagamento</Button>
          {avisoDeAlteracoes}
        </div>
      )}

      {registrando && (
        <div className="pagamento-registro">
          <Form.Item
            label={<span id={`${id}-forma`}>Forma</span>}
            required
            validateStatus={erros.forma ? 'error' : undefined}
            help={erros.forma}
          >
            <div
              ref={focarPrimeiraForma}
              className={`pagamento-formas${erros.forma ? ' com-erro' : ''}`}
              role="radiogroup"
              aria-labelledby={`${id}-forma`}
              aria-required="true"
              aria-invalid={erros.forma ? 'true' : undefined}
              onKeyDown={(e) => {
                if (e.key === 'Enter') aoEnter(e)
              }}
            >
              {FORMAS.map(([valorForma, f]) => {
                const escolhida = forma === valorForma
                return (
                  <label key={valorForma} className={`pagamento-forma${escolhida ? ' escolhida' : ''}`}>
                    <input
                      type="radio"
                      className="sr-only"
                      name={`${id}-forma`}
                      value={valorForma}
                      checked={escolhida}
                      disabled={enviando}
                      onChange={() => {
                        setForma(valorForma)
                        setErros((atual) => ({ ...atual, forma: undefined }))
                      }}
                    />
                    {escolhida && <CheckOutlined aria-hidden="true" />}
                    {f.label}
                  </label>
                )
              })}
            </div>
          </Form.Item>
          <Form.Item
            label="Valor"
            htmlFor={`${id}-valor`}
            required
            validateStatus={erros.valor ? 'error' : undefined}
            help={erros.valor}
          >
            <InputNumber
              id={`${id}-valor`}
              className="campo-valor"
              min={0}
              max={99999999.99}
              step={10}
              precision={2}
              prefix="R$"
              decimalSeparator=","
              inputMode="decimal"
              value={valor}
              disabled={enviando}
              onChange={(v) => {
                setValor(v)
                if (v != null) setErros((atual) => ({ ...atual, valor: undefined }))
              }}
              onBlur={() => {
                if (valor == null || valor === '') setErros((atual) => ({ ...atual, valor: 'Informe o valor pago' }))
              }}
              onPressEnter={aoEnter}
            />
          </Form.Item>
          <Flex justify="flex-end" gap={8} wrap className="pagamento-acoes">
            <Button onClick={voltar} disabled={enviando}>
              Voltar
            </Button>
            {/* Enviando, o painel trava o formulário: o botão continua primário, com o carregamento */}
            <Button type="primary" loading={enviando} disabled={enviando ? false : undefined} onClick={confirmar}>
              Confirmar pagamento
            </Button>
          </Flex>
          {avisoDeAlteracoes}
        </div>
      )}
    </>
  )
}

// Lista de agendamentos: etiqueta Concluído com "Pix · R$ 50,00" logo abaixo (tabela e cartão)
export function SituacaoComPagamento({ agendamento }) {
  return (
    <span className="situacao-com-pagamento">
      <EtiquetaStatus status={agendamento.status} />
      <span className="texto-apoio">{resumoPagamento(agendamento.pagamento)}</span>
    </span>
  )
}
