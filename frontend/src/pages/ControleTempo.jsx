import { useState } from 'react'
import { App, Button, Col, DatePicker, Form, Input, Row, Select, TimePicker, Tooltip } from 'antd'
import { EditOutlined, LoginOutlined, LogoutOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useNomes } from '../data/useNomes.js'
import { dataBR, duracaoTexto, horaCurta } from '../utils/formatos.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import PainelFormulario from '../components/base/PainelFormulario.jsx'
import { usePainel } from '../components/base/usePainel.js'

const minutosTrabalhados = (p) =>
  p.saida ? dayjs(`${p.data} ${p.saida}`).diff(dayjs(`${p.data} ${p.entrada}`), 'minute') : null

export default function ControleTempo() {
  const { pontos, funcionarios } = useData()
  const { usuario, pode } = useAcesso()
  const nomes = useNomes()
  const { message } = App.useApp()
  const [escolhido, setEscolhido] = useState(null)
  const [data, setData] = useState(dayjs())
  const correcao = usePainel()
  const corrigindo = correcao.registro
  const [form] = Form.useForm()

  const verEquipe = pode('ponto_equipe')
  const corrigir = pode('ponto_equipe', 'escrita')
  const registrarProprio = pode('ponto_proprio', 'escrita')

  // Quem corrige o ponto da equipe pode registrar para outro funcionário; os demais, só para si
  const funcionarioId = corrigir ? (escolhido ?? usuario?.id) : usuario?.id
  const hoje = dayjs().format('YYYY-MM-DD')
  const aberto = pontos.itens.find((p) => p.funcionarioId === funcionarioId && p.data === hoje && !p.saida)

  const registrar = () => {
    const agora = dayjs().format('HH:mm')
    if (aberto) {
      pontos.atualizar(aberto.id, { saida: agora })
      message.success(`Saída registrada às ${horaCurta(agora)}.`)
    } else {
      pontos.adicionar({ funcionarioId, data: hoje, entrada: agora, saida: null, origem: 'sistema' })
      message.success(`Entrada registrada às ${horaCurta(agora)}.`)
    }
  }

  const salvarCorrecao = (v) => {
    pontos.atualizar(corrigindo.id, {
      entrada: v.entrada.format('HH:mm'),
      saida: v.saida ? v.saida.format('HH:mm') : null,
      origem: 'manual',
      justificativa: v.justificativa,
      editadoPor: usuario?.id,
    })
    message.success('Correção salva.')
    correcao.fechar()
  }

  const dados = pontos.itens
    .filter((p) => verEquipe || p.funcionarioId === usuario?.id)
    .filter((p) => !data || p.data === data.format('YYYY-MM-DD'))

  const colunas = [
    verEquipe && { title: 'Funcionário', dataIndex: 'funcionarioId', render: (id) => <strong>{nomes.profissional(id)}</strong> },
    { title: 'Data', dataIndex: 'data', render: dataBR },
    { title: 'Entrada', dataIndex: 'entrada', align: 'right', render: horaCurta },
    {
      title: 'Saída',
      dataIndex: 'saida',
      align: 'right',
      render: (s) => (s ? horaCurta(s) : <Etiqueta tom="sucesso">Em serviço</Etiqueta>),
    },
    { title: 'Total', key: 'total', align: 'right', render: (_, p) => (p.saida ? duracaoTexto(minutosTrabalhados(p)) : '—') },
    {
      title: 'Origem',
      dataIndex: 'origem',
      render: (o, p) =>
        o === 'manual' ? (
          <Tooltip title={`${p.justificativa} (por ${nomes.profissional(p.editadoPor)})`}>
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
          <Button type="text" size="small" icon={<EditOutlined />} aria-label="Corrigir registro" onClick={() => correcao.abrir(p)} />
        </Tooltip>
      ),
    },
  ].filter(Boolean)

  return (
    <Pagina
      titulo="Controle de tempo"
      descricao={verEquipe ? 'Entradas e saídas da equipe. Correções ficam marcadas com a justificativa.' : 'Suas entradas e saídas.'}
    >
      {(registrarProprio || corrigir) && (
        <Secao titulo="Registrar ponto">
          <div className="registro-ponto">
            {corrigir ? (
              <Select
                aria-label="Funcionário"
                value={funcionarioId}
                onChange={setEscolhido}
                options={funcionarios.itens.filter((f) => f.ativo).map((f) => ({ value: f.id, label: f.nome }))}
              />
            ) : (
              <strong>{usuario?.nome}</strong>
            )}
            <Button
              type="primary"
              size="large"
              danger={!!aberto}
              disabled={!funcionarioId}
              icon={aberto ? <LogoutOutlined /> : <LoginOutlined />}
              onClick={registrar}
            >
              {aberto ? 'Registrar saída' : 'Registrar entrada'}
            </Button>
            <span className="texto-apoio">
              {aberto ? `Entrada às ${horaCurta(aberto.entrada)}, ${duracaoTexto(dayjs().diff(dayjs(`${aberto.data} ${aberto.entrada}`), 'minute'))} em serviço.` : 'Nenhuma entrada aberta hoje.'}
            </span>
          </div>
        </Secao>
      )}
      <Secao rente titulo={verEquipe ? 'Registros da equipe' : 'Meus registros'}>
        <BarraFiltros>
          <DatePicker format="DD/MM/YYYY" value={data} onChange={setData} placeholder="Todos os dias" aria-label="Dia" />
        </BarraFiltros>
        <Tabela columns={colunas} dataSource={dados} destaqueId={correcao.destaqueId} vazio={data ? `Nenhum registro em ${data.format('DD/MM/YYYY')}` : 'Nenhum registro'} />
      </Secao>
      <PainelFormulario
        titulo={corrigindo ? `Corrigir ponto de ${dataBR(corrigindo.data)}` : 'Corrigir ponto'}
        nome={corrigindo && nomes.profissional(corrigindo.funcionarioId)}
        cor={corrigindo && nomes.corDe(corrigindo.funcionarioId)}
        open={correcao.aberto}
        form={form}
        valoresIniciais={
          corrigindo && {
            entrada: dayjs(corrigindo.entrada, 'HH:mm'),
            saida: corrigindo.saida ? dayjs(corrigindo.saida, 'HH:mm') : null,
          }
        }
        textoSalvar="Salvar correção"
        onCancelar={correcao.fechar}
        onSalvar={salvarCorrecao}
      >
        <Row gutter={12}>
          <Col xs={12}>
            <Form.Item name="entrada" label="Entrada" rules={[{ required: true, message: 'Informe a entrada' }]}>
              <TimePicker format="HH:mm" needConfirm={false} />
            </Form.Item>
          </Col>
          <Col xs={12}>
            <Form.Item
              name="saida"
              label="Saída"
              dependencies={['entrada']}
              rules={[
                ({ getFieldValue }) => ({
                  validator: (_, saida) =>
                    !saida || saida.isAfter(getFieldValue('entrada'))
                      ? Promise.resolve()
                      : Promise.reject(new Error('A saída precisa ser depois da entrada')),
                }),
              ]}
            >
              <TimePicker format="HH:mm" needConfirm={false} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="justificativa" label="Justificativa" rules={[{ required: true, whitespace: true, message: 'Explique o motivo da correção' }]}>
          <Input.TextArea rows={2} placeholder="Ex.: esqueceu de registrar a saída" />
        </Form.Item>
      </PainelFormulario>
    </Pagina>
  )
}
