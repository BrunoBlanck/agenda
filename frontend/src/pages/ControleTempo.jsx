import { useState } from 'react'
import { App, Button, Col, DatePicker, Form, Input, Row, Select, Tooltip } from 'antd'
import { DisconnectOutlined, EditOutlined, LoginOutlined, LogoutOutlined, PlusOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useFuncionariosPonto, usePonto, usePontoAberto } from '../data/usePonto.js'
import { agoraNaLoja } from '../data/api/conversao.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { dataBR, duracaoTexto, horaCurta } from '../utils/formatos.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PainelFormulario from '../components/base/PainelFormulario.jsx'
import { usePainel } from '../components/base/usePainel.js'
import UltimaAlteracao from '../components/UltimaAlteracao.jsx'

const MAX_DIAS = 62 // limite do período na API
const FORMATO_DATA_HORA = 'DD/MM/YYYY HH:mm'

// Saída em outro dia (virada da meia-noite) mostra a data junto
const textoSaida = (p) => (p.saidaOutroDia ? `${horaCurta(p.saidaHora)} (${p.saida.format('DD/MM')})` : horaCurta(p.saidaHora))

// Registrar entrada/saída agora (hora do servidor)
function RegistrarPonto({ usuario, escolherOutro, funcionarios, aoRegistrar }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [escolhido, setEscolhido] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const funcionarioId = escolherOutro ? (escolhido ?? usuario?.id) : usuario?.id
  const situacao = usePontoAberto(funcionarioId, { ativo: !!funcionarioId, aoRegistrar })
  const { aberto } = situacao

  const registrar = async () => {
    setEnviando(true)
    try {
      const { acao, registro } = await situacao.registrar()
      const hora = acao === 'saida' ? registro?.saidaHora : registro?.entradaHora
      message.success(`${acao === 'saida' ? 'Saída' : 'Entrada'} registrada${hora ? ` às ${horaCurta(hora)}` : ''}.`)
    } catch (e) {
      tratarErro(e)
    } finally {
      setEnviando(false)
    }
  }

  const agora = agoraNaLoja()
  const situacaoTexto = situacao.erro
    ? null
    : aberto
      ? `Entrada ${aberto.entrada?.isSame(agora, 'day') ? '' : `em ${aberto.entrada?.format('DD/MM')} `}às ${horaCurta(aberto.entradaHora)}, ${duracaoTexto(Math.max(0, agora.diff(aberto.entrada, 'minute')))} em serviço.`
      : 'Nenhuma entrada em aberto.'

  return (
    <Secao titulo="Registrar ponto">
      <div className="registro-ponto">
        {escolherOutro ? (
          <Select
            aria-label="Funcionário"
            value={funcionarioId}
            onChange={setEscolhido}
            showSearch
            optionFilterProp="label"
            loading={funcionarios.carregando}
            options={(funcionarios.itens.some((f) => f.id === usuario?.id) ? funcionarios.itens : [{ ...usuario, ativo: true }, ...funcionarios.itens])
              .filter((f) => f.ativo)
              .map((f) => ({ value: f.id, label: f.nome }))}
          />
        ) : (
          <strong>{usuario?.nome}</strong>
        )}
        <Button
          type="primary"
          size="large"
          danger={!!aberto}
          // Enquanto a situação deste funcionário não chega (ou é relida), o botão não vale (INT-21)
          disabled={!funcionarioId || situacao.atualizando || !!situacao.erro}
          loading={enviando || situacao.atualizando}
          icon={aberto ? <LogoutOutlined /> : <LoginOutlined />}
          onClick={registrar}
        >
          {aberto ? 'Registrar saída' : 'Registrar entrada'}
        </Button>
        {situacao.erro ? (
          <span className="texto-apoio">
            Não foi possível ver a situação do ponto.{' '}
            <Button type="link" size="small" onClick={situacao.recarregar}>
              Tentar de novo
            </Button>
          </span>
        ) : (
          <span className="texto-apoio">{situacao.carregando ? 'Conferindo a situação…' : situacaoTexto}</span>
        )}
      </div>
    </Secao>
  )
}

export default function ControleTempo() {
  const { usuario, pode } = useAcesso()
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const hoje = agoraNaLoja().startOf('day')
  const [periodo, setPeriodo] = useState(() => [hoje, hoje])
  const [filtroFuncionario, setFiltroFuncionario] = useState(null)
  const painel = usePainel()
  const registro = painel.registro
  const lancamento = !registro?.id
  const [form] = Form.useForm()
  const [salvando, setSalvando] = useState(false)

  const verEquipe = pode('ponto_equipe')
  const corrigir = pode('ponto_equipe', 'escrita')
  const registrarProprio = pode('ponto_proprio', 'escrita')

  const funcionarios = useFuncionariosPonto({ ativo: verEquipe })
  const ponto = usePonto({ inicio: periodo[0], fim: periodo[1], funcionarioId: verEquipe ? filtroFuncionario : null })
  const corDe = (id) => funcionarios.itens.find((f) => f.id === id)?.cor ?? undefined

  const salvar = async (v) => {
    setSalvando(true)
    try {
      if (registro?.id) await ponto.corrigir(registro.id, v)
      else await ponto.lancar(v)
      message.success(registro?.id ? 'Correção salva.' : 'Ponto lançado.')
      painel.fechar()
    } catch (e) {
      tratarErro(e, {
        form,
        aoNaoEncontrado: () => {
          painel.fechar()
          ponto.recarregar()
        },
      })
    } finally {
      setSalvando(false)
    }
  }

  const colunas = [
    verEquipe && { title: 'Funcionário', dataIndex: 'funcionarioNome', render: (n) => <strong>{n}</strong> },
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Entrada', dataIndex: 'entradaHora', align: 'right', render: horaCurta },
    {
      title: 'Saída',
      key: 'saida',
      align: 'right',
      render: (_, p) => (p.saida ? textoSaida(p) : <Etiqueta tom="sucesso">Em serviço</Etiqueta>),
    },
    { title: 'Total', dataIndex: 'minutos', align: 'right', render: (m) => (m == null ? '—' : duracaoTexto(m)) },
    {
      title: 'Origem',
      dataIndex: 'origem',
      render: (o, p) =>
        o === 'manual' ? (
          <Tooltip title={[p.justificativa, p.editadoPorNome && `(por ${p.editadoPorNome})`].filter(Boolean).join(' ') || undefined}>
            <span>
              <Etiqueta tom="atencao" icone={<EditOutlined />}>
                Corrigido
              </Etiqueta>
            </span>
          </Tooltip>
        ) : (
          <span className="texto-apoio">Registro normal</span>
        ),
    },
    corrigir && {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      width: 56,
      align: 'right',
      render: (_, p) => (
        <Tooltip title="Corrigir">
          <Button type="text" size="small" icon={<EditOutlined />} aria-label="Corrigir registro" onClick={() => painel.abrir(p)} />
        </Tooltip>
      ),
    },
  ].filter(Boolean)

  const colunasTotais = [
    verEquipe && { title: 'Funcionário', dataIndex: 'funcionarioNome', render: (n) => <strong>{n}</strong> },
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Horas trabalhadas', dataIndex: 'minutos', align: 'right', render: duracaoTexto },
  ].filter(Boolean)

  const umDia = periodo[0].isSame(periodo[1], 'day')
  const textoPeriodo = umDia ? `em ${periodo[0].format('DD/MM/YYYY')}` : `de ${periodo[0].format('DD/MM')} a ${periodo[1].format('DD/MM/YYYY')}`

  // Período de até 62 dias, nunca no futuro (dia da loja)
  const diaBloqueado = (dia, { from } = {}) =>
    dia.isAfter(hoje, 'day') || (from ? Math.abs(dia.diff(from, 'day')) > MAX_DIAS : false)

  const vazio = ponto.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar os registros"
      descricao={ponto.erro.mensagem}
      acao={<Button onClick={ponto.recarregar}>Tentar de novo</Button>}
    />
  ) : (
    `Nenhum registro ${textoPeriodo}`
  )

  const ativos = funcionarios.itens.filter((f) => f.ativo)
  const validarSaida = ({ getFieldValue }) => ({
    validator: (_, saida) =>
      !saida || !getFieldValue('entrada') || saida.isAfter(getFieldValue('entrada'))
        ? Promise.resolve()
        : Promise.reject(new Error('A saída precisa ser depois da entrada')),
  })

  return (
    <Pagina
      titulo="Controle de tempo"
      descricao={verEquipe ? 'Entradas e saídas da equipe. Correções ficam marcadas com a justificativa.' : 'Suas entradas e saídas.'}
      acoes={
        corrigir && (
          <Button icon={<PlusOutlined />} onClick={() => painel.abrir({})}>
            Lançar ponto
          </Button>
        )
      }
    >
      {(registrarProprio || corrigir) && (
        <RegistrarPonto usuario={usuario} escolherOutro={corrigir} funcionarios={funcionarios} aoRegistrar={ponto.recarregar} />
      )}
      <Secao rente titulo={verEquipe ? 'Registros da equipe' : 'Meus registros'}>
        <BarraFiltros>
          <DatePicker.RangePicker
            format="DD/MM/YYYY"
            value={periodo}
            allowClear={false}
            disabledDate={diaBloqueado}
            presets={[
              { label: 'Hoje', value: [hoje, hoje] },
              { label: 'Esta semana', value: [hoje.startOf('week'), hoje] },
              { label: 'Este mês', value: [hoje.startOf('month'), hoje] },
            ]}
            onChange={(datas) => datas?.[0] && datas?.[1] && setPeriodo([datas[0].startOf('day'), datas[1].startOf('day')])}
            aria-label="Período"
          />
          {verEquipe && (
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="Todos os funcionários"
              aria-label="Funcionário"
              value={filtroFuncionario}
              onChange={(v) => setFiltroFuncionario(v ?? null)}
              loading={funcionarios.carregando}
              options={funcionarios.itens.map((f) => ({ value: f.id, label: f.ativo ? f.nome : `${f.nome} (inativo)` }))}
            />
          )}
        </BarraFiltros>
        <Tabela
          columns={colunas}
          dataSource={ponto.registros}
          loading={ponto.carregando || ponto.atualizando}
          destaqueId={painel.destaqueId}
          vazio={vazio}
        />
      </Secao>
      {ponto.totais.length > 0 && (
        <Secao rente titulo="Horas por dia" descricao="Soma dos registros com saída, por dia.">
          <Tabela size="small" columns={colunasTotais} dataSource={ponto.totais} />
        </Secao>
      )}
      <PainelFormulario
        titulo={registro?.id ? `Corrigir ponto de ${dataBR(registro.data)}` : 'Lançar ponto'}
        nome={registro?.id ? registro.funcionarioNome : undefined}
        cor={registro?.id ? corDe(registro.funcionarioId) : undefined}
        open={painel.aberto}
        form={form}
        valoresIniciais={
          registro?.id
            ? { entrada: registro.entrada, saida: registro.saida }
            : { funcionarioId: filtroFuncionario ?? undefined }
        }
        salvando={salvando}
        textoSalvar={registro?.id ? 'Salvar correção' : 'Lançar ponto'}
        onCancelar={painel.fechar}
        onSalvar={salvar}
        rodape={registro?.id && <UltimaAlteracao item={registro} />}
      >
        {lancamento && (
          <Form.Item name="funcionarioId" label="Funcionário" rules={[{ required: true, message: 'Escolha o funcionário' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              loading={funcionarios.carregando}
              options={ativos.map((f) => ({ value: f.id, label: f.nome }))}
            />
          </Form.Item>
        )}
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item name="entrada" label="Entrada" rules={[{ required: true, message: 'Informe a entrada' }]}>
              <DatePicker showTime={{ format: 'HH:mm' }} format={FORMATO_DATA_HORA} disabledDate={(d) => d.isAfter(hoje, 'day')} needConfirm={false} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="saida" label="Saída" dependencies={['entrada']} extra="Vazio = ainda em serviço" rules={[validarSaida]}>
              <DatePicker showTime={{ format: 'HH:mm' }} format={FORMATO_DATA_HORA} disabledDate={(d) => d.isAfter(hoje, 'day')} needConfirm={false} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="justificativa"
          label="Justificativa"
          rules={[{ required: true, whitespace: true, message: registro?.id ? 'Explique o motivo da correção' : 'Explique o motivo do lançamento' }]}
        >
          <Input.TextArea rows={2} maxLength={2000} placeholder="Ex.: esqueceu de registrar a saída" />
        </Form.Item>
      </PainelFormulario>
    </Pagina>
  )
}
