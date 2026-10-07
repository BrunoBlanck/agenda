import { useState } from 'react'
import { Alert, App, Button, Col, Form, Input, InputNumber, Row, Segmented, Select, Skeleton, Switch } from 'antd'
import { DisconnectOutlined, SendOutlined } from '@ant-design/icons'
import { useTratarErro } from '../data/api/useTratarErro.js'
import EstadoVazio from './base/EstadoVazio.jsx'
import UltimaAlteracao from './UltimaAlteracao.jsx'
import './avisos-email.css'

const MAX_MINUTOS = 10080 // 7 dias (CFG-05)

const PORTAS = [587, 465, 25, 2525].map((p) => ({ value: p, label: String(p) }))
const SEGURANCAS = [
  { value: 'starttls', label: 'STARTTLS' },
  { value: 'ssl', label: 'SSL/TLS' },
]
const UNIDADES = [
  { value: 'minutos', label: 'minutos' },
  { value: 'horas', label: 'horas' },
]

const texto = (v) => (typeof v === 'string' ? v.trim() || null : (v ?? null))
const emMinutos = ({ valor, unidade } = {}) => (valor == null ? null : unidade === 'horas' ? Math.round(valor * 60) : valor)

const antecedenciaValida = (_, valor) => {
  if (valor?.valor == null) return Promise.reject(new Error('Informe a antecedência (0 para nenhuma).'))
  return emMinutos(valor) > MAX_MINUTOS
    ? Promise.reject(new Error('No máximo 7 dias (168 horas ou 10080 minutos).'))
    : Promise.resolve()
}

const servidorValido = (_, valor) => {
  const v = valor?.trim()
  if (!v) return Promise.resolve()
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(v)) return Promise.reject(new Error('Informe só o nome do servidor, sem http:// (ex.: smtp.gmail.com).'))
  if (/[\s/]/.test(v)) return Promise.reject(new Error('Informe só o nome do servidor (ex.: smtp.gmail.com), sem espaços nem barras.'))
  return Promise.resolve()
}

const valoresIniciais = (config) => {
  const m = config.antecedenciaClienteMinutos ?? 120
  const emHoras = m > 0 && m % 60 === 0
  const e = config.email ?? {}
  return {
    antecedencia: { valor: emHoras ? m / 60 : m, unidade: emHoras ? 'horas' : 'minutos' },
    email: {
      ativo: !!e.ativo,
      servidor: e.servidor ?? '',
      porta: e.porta ?? null,
      seguranca: e.seguranca ?? null,
      usuario: e.usuario ?? '',
      senha: '',
      remetenteEmail: e.remetenteEmail ?? '',
      remetenteNome: e.remetenteNome ?? '',
    },
  }
}

/**
 * Configurações > Dados da loja > Avisos e e-mail (CFG-05, CFG-06): antecedência do cliente (lembrete e
 * prazo para cancelar/remarcar pelo site) e o SMTP da loja, com envio de teste.
 * estado: o retorno de useConfigNotificacoes() ({ config, carregando, erro, recarregar, salvar, testarEmail }).
 */
export default function AvisosEmail({ estado, nomeLoja, somenteLeitura = false }) {
  const { config, carregando, erro, recarregar } = estado

  if (carregando) return <AvisosEmailCarregando />
  if (!config) {
    return (
      <EstadoVazio
        compacto
        icone={<DisconnectOutlined />}
        titulo="Não foi possível carregar os avisos e o e-mail da loja"
        descricao={erro?.mensagem}
        acao={<Button onClick={recarregar}>Tentar de novo</Button>}
      />
    )
  }

  return <FormularioAvisos config={config} nomeLoja={nomeLoja} somenteLeitura={somenteLeitura} salvar={estado.salvar} testarEmail={estado.testarEmail} />
}

function FormularioAvisos({ config, nomeLoja, somenteLeitura, salvar, testarEmail }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const [salvando, setSalvando] = useState(false)
  const [gravacoes, setGravacoes] = useState(0)
  const [alterado, setAlterado] = useState(false)
  const [removerSenha, setRemoverSenha] = useState(false)
  const [testeAberto, setTesteAberto] = useState(false)

  const iniciais = valoresIniciais(config)
  const ativo = Form.useWatch(['email', 'ativo'], form) ?? iniciais.email.ativo
  const valorAntecedencia = Form.useWatch(['antecedencia', 'valor'], form) ?? iniciais.antecedencia.valor
  const senhaDefinida = !!config.email?.senhaDefinida
  // Trocar servidor ou usuário com senha salva exige a senha de novo (decisão A4; a API responde 422 em email.senha)
  const servidorDigitado = Form.useWatch(['email', 'servidor'], form) ?? iniciais.email.servidor
  const usuarioDigitado = Form.useWatch(['email', 'usuario'], form) ?? iniciais.email.usuario
  const trocouAcesso =
    (servidorDigitado?.trim() || null) !== (config.email?.servidor || null) ||
    (usuarioDigitado?.trim() || null) !== (config.email?.usuario || null)
  const pedirSenhaDeNovo = senhaDefinida && trocouAcesso && !removerSenha && !somenteLeitura
  const bloqueado = somenteLeitura || salvando
  const exigirQuandoAtivo = (mensagem) => ({ required: ativo, message: mensagem })
  const dependeDoAtivo = [['email', 'ativo']]

  // Porta 465 usa SSL; as outras, STARTTLS (dá para trocar depois)
  const trocarPorta = (porta) => form.setFieldValue(['email', 'seguranca'], porta === 465 ? 'ssl' : 'starttls')

  const enviar = async (valores) => {
    const e = valores.email
    const email = {
      ativo: !!e.ativo,
      servidor: texto(e.servidor),
      porta: e.porta ?? null,
      seguranca: e.seguranca ?? null,
      usuario: texto(e.usuario),
      remetenteEmail: texto(e.remetenteEmail),
      remetenteNome: texto(e.remetenteNome),
    }
    // senha: ausente = mantém a salva; null = remove; texto = troca
    if (e.senha) email.senha = e.senha
    else if (removerSenha) email.senha = null

    setSalvando(true)
    try {
      await salvar({ antecedenciaClienteMinutos: emMinutos(valores.antecedencia), email })
      setGravacoes((n) => n + 1)
      setAlterado(false)
      setRemoverSenha(false)
      message.success('Avisos e e-mail salvos.')
    } catch (erro) {
      tratarErro(erro, { form, mapa: { antecedencia_cliente_minutos: 'antecedencia' } })
    } finally {
      setSalvando(false)
    }
  }

  let ajudaSenha = senhaDefinida ? null : 'Nenhuma senha salva.'
  if (somenteLeitura) ajudaSenha = senhaDefinida ? 'Senha salva.' : 'Nenhuma senha salva.'
  else if (removerSenha) {
    ajudaSenha = (
      <span className="avisos-senha-ajuda">
        A senha salva será removida ao salvar.
        <Button type="link" size="small" onClick={() => setRemoverSenha(false)}>
          Desfazer
        </Button>
      </span>
    )
  } else if (senhaDefinida) {
    const remover = (
      <Button
        type="link"
        size="small"
        className="avisos-remover-senha"
        onClick={() => {
          setRemoverSenha(true)
          setAlterado(true)
          form.setFieldValue(['email', 'senha'], '')
        }}
      >
        Remover senha
      </Button>
    )
    ajudaSenha = pedirSenhaDeNovo ? (
      <span className="avisos-senha-ajuda">
        Ao trocar o servidor ou o usuário, informe a senha de novo.
        {remover}
      </span>
    ) : (
      remover
    )
  }

  return (
    <div className="avisos-email">
      <Form
        key={gravacoes}
        form={form}
        name="avisos"
        layout="vertical"
        initialValues={iniciais}
        disabled={bloqueado}
        onFinish={enviar}
        onValuesChange={() => setAlterado(true)}
      >
        <Form.Item
          label="Antecedência do cliente"
          htmlFor="avisos_antecedencia_valor"
          required
          extra={
            <>
              O cliente recebe o lembrete com essa antecedência e só pode cancelar ou remarcar pelo site até esse momento.
              {valorAntecedencia === 0 && ' Com 0, não há lembrete e o cliente pode cancelar até o horário do atendimento.'}
            </>
          }
        >
          <Form.Item name="antecedencia" noStyle rules={[{ validator: antecedenciaValida }]}>
            <CampoAntecedencia bloqueado={bloqueado} />
          </Form.Item>
        </Form.Item>

        <h3 className="grupo-formulario avisos-grupo">E-mail da loja (SMTP)</h3>
        <p className="texto-ajuda avisos-grupo-ajuda">
          Os avisos aos clientes saem deste endereço. Peça os dados ao seu provedor de e-mail; o mais comum é a porta 587 com STARTTLS.
        </p>
        <Form.Item
          name={['email', 'ativo']}
          label="Enviar avisos por e-mail"
          valuePropName="checked"
          extra={ativo ? 'Ligado: os clientes com e-mail no cadastro recebem os avisos.' : 'Desligado: os avisos ficam só no site da loja.'}
        >
          <Switch />
        </Form.Item>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name={['email', 'servidor']}
              label="Servidor"
              dependencies={dependeDoAtivo}
              validateTrigger="onBlur"
              rules={[exigirQuandoAtivo('Informe o servidor para ativar o envio.'), { validator: servidorValido }]}
            >
              <Input placeholder="smtp.seuprovedor.com.br" maxLength={255} spellCheck={false} autoComplete="off" autoCapitalize="none" />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name={['email', 'porta']} label="Porta" dependencies={dependeDoAtivo} rules={[exigirQuandoAtivo('Escolha a porta.')]}>
              <Select options={PORTAS} placeholder="Escolha" onChange={trocarPorta} allowClear />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name={['email', 'seguranca']} label="Segurança" dependencies={dependeDoAtivo} rules={[exigirQuandoAtivo('Escolha a segurança.')]}>
              <Select options={SEGURANCAS} placeholder="Escolha" allowClear />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name={['email', 'usuario']} label="Usuário" extra="Quase sempre é o próprio endereço de e-mail.">
              <Input maxLength={255} spellCheck={false} autoComplete="off" autoCapitalize="none" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name={['email', 'senha']} label="Senha" extra={ajudaSenha}>
              <Input.Password
                maxLength={255}
                autoComplete="new-password"
                disabled={bloqueado || removerSenha}
                visibilityToggle={!somenteLeitura}
                placeholder={senhaDefinida && !removerSenha && !somenteLeitura && !pedirSenhaDeNovo ? 'Senha salva — deixe em branco para manter' : undefined}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name={['email', 'remetenteEmail']}
              label="E-mail do remetente"
              dependencies={dependeDoAtivo}
              validateTrigger="onBlur"
              rules={[
                exigirQuandoAtivo('Informe o e-mail do remetente para ativar o envio.'),
                { type: 'email', message: 'Informe um e-mail válido, como avisos@sualoja.com.br.' },
              ]}
            >
              <Input type="email" inputMode="email" maxLength={254} placeholder="avisos@sualoja.com.br" autoComplete="off" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name={['email', 'remetenteNome']} label="Nome do remetente" extra="Como aparece na caixa de entrada do cliente.">
              <Input maxLength={120} placeholder={nomeLoja || undefined} />
            </Form.Item>
          </Col>
        </Row>

        {!config.whatsappDisponivel && (
          <p className="avisos-whatsapp">
            <strong>WhatsApp:</strong> em breve. Por enquanto os avisos não saem por WhatsApp.
          </p>
        )}

        <div className="rodape-formulario">
          <UltimaAlteracao item={config} />
          {!somenteLeitura && (
            <div className="avisos-acoes">
              <Button icon={<SendOutlined />} disabled={testeAberto} onClick={() => setTesteAberto(true)}>
                Enviar e-mail de teste
              </Button>
              <Button type="primary" htmlType="submit" loading={salvando} disabled={false}>
                Salvar avisos
              </Button>
            </div>
          )}
        </div>
      </Form>

      {!somenteLeitura && testeAberto && (
        <TesteEmail
          emailAtivo={!!config.email?.ativo}
          alterado={alterado}
          sugestao={config.email?.remetenteEmail ?? ''}
          testarEmail={testarEmail}
          aoFechar={() => setTesteAberto(false)}
        />
      )}
    </div>
  )
}

// Número + unidade (minutos ou horas) como um campo só: value = { valor, unidade }.
// Trocar a unidade mantém o tempo: 2 horas vira 120 minutos (e não 2 minutos).
function CampoAntecedencia({ value, onChange, bloqueado }) {
  const atual = value ?? { valor: null, unidade: 'minutos' }
  const emHoras = atual.unidade === 'horas'
  const trocarUnidade = (nova) => {
    if (nova === atual.unidade) return
    const { valor } = atual
    const convertido = valor == null ? null : nova === 'horas' ? Math.round((valor / 60) * 100) / 100 : Math.round(valor * 60)
    onChange?.({ valor: convertido, unidade: nova })
  }
  return (
    <div className="avisos-antecedencia">
      <InputNumber
        id="avisos_antecedencia_valor"
        className="avisos-antecedencia-numero"
        value={atual.valor}
        min={0}
        max={emHoras ? MAX_MINUTOS / 60 : MAX_MINUTOS}
        precision={emHoras ? undefined : 0}
        step={emHoras ? 1 : 15}
        decimalSeparator=","
        inputMode="decimal"
        disabled={bloqueado}
        onChange={(valor) => onChange?.({ ...atual, valor })}
      />
      <Segmented options={UNIDADES} value={atual.unidade} disabled={bloqueado} aria-label="Unidade da antecedência" onChange={trocarUnidade} />
    </div>
  )
}

// Envio de teste (usa a configuração salva): campo de destino e o resultado na própria seção
function TesteEmail({ emailAtivo, alterado, sugestao, testarEmail, aoFechar }) {
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState(null)

  const enviar = async ({ destino }) => {
    setEnviando(true)
    setResultado(null)
    try {
      const r = await testarEmail(destino.trim())
      setResultado(
        r?.enviado
          ? { tipo: 'success', titulo: `E-mail de teste enviado para ${destino.trim()}.`, descricao: 'Confira a caixa de entrada (e a de spam).' }
          : { tipo: 'error', titulo: 'O e-mail de teste não foi enviado.', descricao: r?.erro || 'Confira o servidor, a porta, a segurança, o usuário e a senha.' },
      )
    } catch (erro) {
      if (erro?.status === 422 && erro.campos?.length) tratarErro(erro, { form })
      else if (erro?.status === 401) tratarErro(erro)
      else if (erro?.name !== 'AbortError') {
        setResultado({ tipo: erro?.status === 409 || erro?.status === 429 ? 'warning' : 'error', titulo: erro?.mensagem ?? 'Não foi possível enviar o teste.' })
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="avisos-teste" aria-labelledby="avisos-teste-titulo">
      <div className="avisos-teste-cabecalho">
        <h3 id="avisos-teste-titulo" className="grupo-formulario">
          Enviar e-mail de teste
        </h3>
        <Button type="text" size="small" onClick={aoFechar}>
          Fechar
        </Button>
      </div>
      {emailAtivo ? (
        <>
          <p className="texto-ajuda">
            {alterado ? 'Há alterações não salvas: o teste usa a configuração salva. Salve antes de testar.' : 'O teste usa a configuração salva.'}
          </p>
          <Form form={form} name="testeEmail" layout="vertical" initialValues={{ destino: sugestao }} onFinish={enviar} disabled={enviando}>
            <div className="avisos-teste-linha">
              <Form.Item
                name="destino"
                label="Enviar para"
                validateTrigger="onBlur"
                rules={[
                  { required: true, message: 'Informe o e-mail que vai receber o teste.' },
                  { type: 'email', message: 'Informe um e-mail válido, como voce@sualoja.com.br.' },
                ]}
              >
                <Input type="email" inputMode="email" autoComplete="email" maxLength={254} autoFocus />
              </Form.Item>
              <Button htmlType="submit" icon={<SendOutlined />} loading={enviando} disabled={false}>
                Enviar teste
              </Button>
            </div>
          </Form>
        </>
      ) : (
        <Alert type="info" showIcon title="Ligue o envio por e-mail, preencha os dados e salve antes de testar." />
      )}
      {resultado && (
        <Alert type={resultado.tipo} showIcon title={resultado.titulo} description={resultado.descricao} className="avisos-teste-resultado" role="status" />
      )}
    </section>
  )
}

function AvisosEmailCarregando() {
  return (
    <div className="avisos-email avisos-email-carregando" aria-busy="true" aria-label="Carregando os avisos e o e-mail da loja">
      <Skeleton.Input active size="small" />
      <div className="avisos-antecedencia">
        <Skeleton.Input active />
        <Skeleton.Button active />
      </div>
      <Skeleton active title={{ width: '30%' }} paragraph={{ rows: 1, width: '80%' }} />
      <div className="avisos-email-fantasma-grade">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton.Input key={i} active block />
        ))}
      </div>
    </div>
  )
}
