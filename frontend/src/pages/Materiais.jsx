import { useState } from 'react'
import { App, Button, Col, Descriptions, Flex, Form, Input, InputNumber, Popconfirm, Row, Segmented, Select, Skeleton, Switch, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  DisconnectOutlined,
  EditOutlined,
  HistoryOutlined,
  InboxOutlined,
  TagsOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PainelLateral from '../components/base/PainelLateral.jsx'
import { usePainel } from '../components/base/usePainel.js'
import { EtiquetaSituacao } from '../components/Etiquetas.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useCategoriasMaterial, useEstoqueMaterial, useMateriais } from '../data/useMateriais.js'
import { MAPA_ERROS_MATERIAL } from '../data/api/materiais.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { dataHoraBR, plural } from '../utils/formatos.js'

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const quantidadeTexto = (q, unidade) => (q == null ? '—' : `${numero.format(q)} ${unidade ?? ''}`.trim())

function EtiquetaEstoque({ repor }) {
  return repor ? (
    <Etiqueta tom="marca" icone={<WarningOutlined />}>
      Repor
    </Etiqueta>
  ) : (
    <Etiqueta tom="sucesso" icone={<CheckCircleOutlined />}>
      Em dia
    </Etiqueta>
  )
}

// Tipos de movimentação de estoque (enum tipo_movimentacao)
const tiposMovimentacao = {
  entrada: { label: 'Entrada', tom: 'sucesso', lancado: 'Entrada lançada.' },
  saida_atendimento: { label: 'Saída por atendimento', tom: 'neutro' },
  ajuste: { label: 'Ajuste', tom: 'tinta', lancado: 'Ajuste lançado.' },
  perda: { label: 'Perda', tom: 'atencao', lancado: 'Perda lançada.' },
}
const tipoMovimentacao = (tipo) => tiposMovimentacao[tipo] ?? { label: String(tipo ?? '—').replace(/_/g, ' '), tom: 'neutro' }

const ajudaQuantidade = {
  entrada: 'Quanto chegou.',
  ajuste: 'Positiva soma ao estoque; negativa subtrai (ex.: -2 depois de uma contagem).',
  perda: 'Quanto foi perdido (vencido, quebrado). Sai do estoque.',
}

// ---------------------------------------------------------------------------------------------
// Estoque de um material: lançar entrada, ajuste ou perda e ver o histórico
// ---------------------------------------------------------------------------------------------

function LancarMovimentacao({ lancar, unidade }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [enviando, setEnviando] = useState(false)
  const tipo = Form.useWatch('tipo', form) ?? 'entrada'

  const enviar = async (v) => {
    setEnviando(true)
    try {
      await lancar(v)
      message.success(tipoMovimentacao(v.tipo).lancado ?? 'Movimentação lançada.')
      form.resetFields()
    } catch (e) {
      tratarErro(e, { form })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Form form={form} layout="vertical" initialValues={{ tipo: 'entrada' }} disabled={enviando} onFinish={enviar}>
      <Form.Item name="tipo" label="O que aconteceu">
        <Segmented
          block
          options={['entrada', 'ajuste', 'perda'].map((t) => ({ value: t, label: tiposMovimentacao[t].label }))}
        />
      </Form.Item>
      <Row gutter={12}>
        <Col xs={24} sm={10}>
          <Form.Item
            name="quantidade"
            label="Quantidade"
            extra={ajudaQuantidade[tipo]}
            rules={[
              { required: true, message: 'Informe a quantidade' },
              {
                validator: (_, q) => (q === 0 ? Promise.reject(new Error('A quantidade não pode ser zero')) : Promise.resolve()),
              },
            ]}
          >
            <InputNumber
              min={tipo === 'ajuste' ? -1000000 : 0.01}
              max={1000000}
              decimalSeparator=","
              suffix={unidade || undefined}
              className="campo-quantidade"
            />
          </Form.Item>
        </Col>
        <Col xs={24} sm={14}>
          <Form.Item
            name="motivo"
            label="Motivo"
            dependencies={['tipo']}
            rules={[
              ({ getFieldValue }) => ({
                validator: (_, motivo) =>
                  getFieldValue('tipo') !== 'entrada' && !motivo?.trim()
                    ? Promise.reject(new Error('Informe o motivo do ajuste ou da perda'))
                    : Promise.resolve(),
              }),
            ]}
          >
            <Input maxLength={200} placeholder={tipo === 'entrada' ? 'Opcional. Ex.: nota 1234' : 'Ex.: contagem do mês, validade vencida'} />
          </Form.Item>
        </Col>
      </Row>
      <Button type="primary" htmlType="submit" loading={enviando}>
        Lançar {tiposMovimentacao[tipo]?.label.toLowerCase()}
      </Button>
    </Form>
  )
}

function PainelEstoque({ painel, somenteLeitura, aoLancar }) {
  const registro = painel.registro
  const estoque = useEstoqueMaterial(registro?.id, { ativo: painel.aberto, aoLancar })
  // Enquanto o material atualizado não chega, mostra o que a lista já tinha
  const material = estoque.material ?? registro
  const mov = estoque.movimentacoes

  const colunas = [
    { title: 'Quando', dataIndex: 'quando', render: dataHoraBR },
    {
      title: 'Movimentação',
      dataIndex: 'tipo',
      cartao: 'etiqueta',
      render: (t) => {
        const tipo = tipoMovimentacao(t)
        return <Etiqueta tom={tipo.tom}>{tipo.label}</Etiqueta>
      },
    },
    {
      title: 'Quantidade',
      dataIndex: 'quantidade',
      align: 'right',
      render: (q) => `${q > 0 ? '+' : ''}${numero.format(q)}`,
    },
    { title: 'Motivo', dataIndex: 'motivo', render: (m) => m || <span className="texto-apoio">—</span> },
    { title: 'Por', dataIndex: 'quem', render: (q) => q || <span className="texto-apoio">—</span> },
  ]

  return (
    <PainelLateral
      titulo="Estoque"
      nome={material?.nome}
      icone={<InboxOutlined />}
      open={painel.aberto}
      onClose={painel.fechar}
      largura={640}
      rodape={
        <Flex justify="end">
          <Button onClick={painel.fechar}>Fechar</Button>
        </Flex>
      }
    >
      {estoque.erroMaterial && !estoque.material ? (
        <EstadoVazio
          icone={<DisconnectOutlined />}
          titulo="Não foi possível carregar o material"
          descricao={estoque.erroMaterial.mensagem}
          acao={<Button onClick={estoque.recarregarMaterial}>Tentar de novo</Button>}
        />
      ) : (
        <Flex vertical gap={24}>
          <Descriptions column={{ xs: 1, sm: 2 }} size="small" colon={false}>
            <Descriptions.Item label="Em estoque">
              <strong>{quantidadeTexto(material?.quantidade, material?.unidade)}</strong>
            </Descriptions.Item>
            <Descriptions.Item label="Mínimo">{quantidadeTexto(material?.minimo, material?.unidade)}</Descriptions.Item>
            <Descriptions.Item label="Situação">
              <EtiquetaEstoque repor={material?.repor} />
            </Descriptions.Item>
            <Descriptions.Item label="Categoria">{material?.categoriaNome ?? 'Sem categoria'}</Descriptions.Item>
          </Descriptions>

          {!somenteLeitura && (
            <section>
              <h3 className="grupo-formulario">Lançar no estoque</h3>
              <LancarMovimentacao key={registro?.id} lancar={estoque.lancar} unidade={material?.unidade} />
            </section>
          )}

          <section>
            <h3 className="grupo-formulario">Histórico</h3>
            <Tabela
              size="small"
              columns={colunas}
              dataSource={mov.itens}
              loading={mov.carregando}
              pagination={{
                current: mov.pagina,
                pageSize: mov.porPagina,
                total: mov.total,
                onChange: mov.mudarPagina,
                showSizeChanger: false,
                hideOnSinglePage: true,
              }}
              vazio={
                mov.erro ? (
                  <EstadoVazio
                    compacto
                    titulo="Não foi possível carregar o histórico"
                    descricao={mov.erro.mensagem}
                    acao={<Button onClick={mov.recarregar}>Tentar de novo</Button>}
                  />
                ) : (
                  'Nenhuma movimentação ainda'
                )
              }
            />
          </section>
        </Flex>
      )}
    </PainelLateral>
  )
}

// ---------------------------------------------------------------------------------------------
// Categorias de material (painel lateral de consulta com ações rápidas)
// ---------------------------------------------------------------------------------------------

function LinhaCategoria({ categoria, somenteLeitura, salvar, excluir }) {
  const [form] = Form.useForm()
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const [editando, setEditando] = useState(false)
  const [ocupado, setOcupado] = useState(false)

  const renomear = async ({ nome }) => {
    setOcupado(true)
    try {
      await salvar({ nome }, categoria.id)
      message.success('Categoria renomeada.')
      setEditando(false)
    } catch (e) {
      tratarErro(e, { form })
    } finally {
      setOcupado(false)
    }
  }

  const remover = async () => {
    setOcupado(true)
    try {
      await excluir(categoria.id)
      message.success('Categoria excluída.')
    } catch (e) {
      tratarErro(e)
      setOcupado(false)
    }
  }

  if (editando) {
    return (
      <Form form={form} layout="inline" initialValues={{ nome: categoria.nome }} disabled={ocupado} onFinish={renomear} className="form-em-linha">
        <Form.Item name="nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
          <Input maxLength={80} aria-label="Nome da categoria" autoFocus />
        </Form.Item>
        <Tooltip title="Salvar" rootClassName="dica-icone">
          <Button htmlType="submit" type="text" icon={<CheckOutlined />} loading={ocupado} aria-label="Salvar nome" />
        </Tooltip>
        <Tooltip title="Cancelar" rootClassName="dica-icone">
          <Button type="text" icon={<CloseOutlined />} aria-label="Cancelar" onClick={() => setEditando(false)} />
        </Tooltip>
      </Form>
    )
  }

  return (
    <Flex align="center" justify="space-between" gap={8}>
      <span>{categoria.nome}</span>
      {!somenteLeitura && (
        <span className="acoes-linha">
          <Tooltip title="Renomear" rootClassName="dica-icone">
            <Button type="text" size="small" icon={<EditOutlined />} aria-label={`Renomear ${categoria.nome}`} onClick={() => setEditando(true)} />
          </Tooltip>
          <Popconfirm
            title="Excluir esta categoria?"
            description="Só dá para excluir categoria sem materiais."
            okText="Excluir"
            okButtonProps={{ danger: true }}
            cancelText="Cancelar"
            onConfirm={remover}
          >
            <Tooltip title="Excluir" rootClassName="dica-icone">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} loading={ocupado} aria-label={`Excluir ${categoria.nome}`} />
            </Tooltip>
          </Popconfirm>
        </span>
      )}
    </Flex>
  )
}

function PainelCategorias({ aberto, fechar, categorias, somenteLeitura }) {
  const [form] = Form.useForm()
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const [criando, setCriando] = useState(false)

  const criar = async ({ nome }) => {
    setCriando(true)
    try {
      await categorias.salvar({ nome })
      message.success('Categoria criada.')
      form.resetFields()
    } catch (e) {
      tratarErro(e, { form })
    } finally {
      setCriando(false)
    }
  }

  return (
    <PainelLateral
      titulo="Categorias de material"
      nome={plural(categorias.itens.length, 'categoria', 'categorias')}
      icone={<TagsOutlined />}
      open={aberto}
      onClose={fechar}
      rodape={
        <Flex justify="end">
          <Button onClick={fechar}>Fechar</Button>
        </Flex>
      }
    >
      <Flex vertical gap={24}>
        {!somenteLeitura && (
          <Form form={form} layout="inline" disabled={criando} onFinish={criar} className="form-em-linha">
            <Form.Item name="nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
              <Input maxLength={80} placeholder="Ex.: Descartáveis" aria-label="Nova categoria" />
            </Form.Item>
            <Button htmlType="submit" loading={criando}>
              Adicionar categoria
            </Button>
          </Form>
        )}
        {categorias.carregando ? (
          <Skeleton active title={false} paragraph={{ rows: 4 }} />
        ) : categorias.erro && !categorias.itens.length ? (
          <EstadoVazio
            compacto
            titulo="Não foi possível carregar as categorias"
            descricao={categorias.erro.mensagem}
            acao={<Button onClick={categorias.recarregar}>Tentar de novo</Button>}
          />
        ) : categorias.itens.length === 0 ? (
          <EstadoVazio compacto titulo="Nenhuma categoria cadastrada" descricao="Categorias ajudam a filtrar a lista de materiais." />
        ) : (
          <Flex vertical gap={8} role="list" aria-label="Categorias">
            {categorias.itens.map((c) => (
              <div key={c.id} role="listitem">
                <LinhaCategoria categoria={c} somenteLeitura={somenteLeitura} salvar={categorias.salvar} excluir={categorias.excluir} />
              </div>
            ))}
          </Flex>
        )}
      </Flex>
    </PainelLateral>
  )
}

// ---------------------------------------------------------------------------------------------

export default function Materiais() {
  const { pode } = useAcesso()
  const somenteLeitura = !pode('materiais', 'escrita')
  const materiais = useMateriais()
  const categorias = useCategoriasMaterial({ aoMudar: materiais.recarregar })
  const estoque = usePainel()
  const [verCategorias, setVerCategorias] = useState(false)

  const filtrosCategoria = [
    ...categorias.itens.map((c) => ({ text: c.nome, value: c.id })),
    { text: 'Sem categoria', value: '' },
  ]

  const colunas = [
    { title: 'Material', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    {
      title: 'Categoria',
      dataIndex: 'categoriaNome',
      filters: filtrosCategoria,
      onFilter: (v, r) => (r.categoriaId ?? '') === v,
      render: (nome) => nome ?? <span className="texto-apoio">—</span>,
    },
    {
      title: 'Em estoque',
      dataIndex: 'quantidade',
      align: 'right',
      render: (q, r) => (
        <Tooltip title="Ver estoque e lançar movimentação" rootClassName="dica-icone">
          <Button type="link" size="small" icon={<HistoryOutlined />} iconPlacement="end" onClick={() => estoque.abrir(r)}>
            {quantidadeTexto(q, r.unidade)}
          </Button>
        </Tooltip>
      ),
    },
    { title: 'Mínimo', dataIndex: 'minimo', align: 'right', render: (q, r) => quantidadeTexto(q, r.unidade) },
    {
      title: 'Estoque',
      dataIndex: 'repor',
      filters: [
        { text: 'Repor', value: true },
        { text: 'Em dia', value: false },
      ],
      onFilter: (v, r) => r.repor === v,
      sorter: (a, b) => Number(b.repor) - Number(a.repor),
      cartao: 'etiqueta',
      render: (repor) => <EtiquetaEstoque repor={repor} />,
    },
    {
      title: 'Situação',
      dataIndex: 'ativo',
      cartao: 'etiqueta',
      filters: [
        { text: 'Ativo', value: true },
        { text: 'Inativo', value: false },
      ],
      onFilter: (v, r) => r.ativo === v,
      render: (ativo) => <EtiquetaSituacao ativo={ativo} />,
    },
  ]

  return (
    <>
      <CadastroTabela
        titulo="Materiais"
        descricao="Estoque da loja. Abaixo do mínimo, o material aparece como Repor aqui e no Início."
        item="material"
        lista={materiais}
        colunas={colunas}
        somenteLeitura={somenteLeitura}
        mapaErros={MAPA_ERROS_MATERIAL}
        valoresNovo={{ unidade: 'un', quantidadeInicial: 0, minimo: 0, ativo: true }}
        textoExcluir="Ele sai das listas, mas o histórico do estoque continua. Material usado em serviços não pode ser excluído: inative-o."
        larguraTabela={900}
        iconeRegistro={() => <InboxOutlined />}
        acoesEdicao={(item, fechar) => (
          <Button icon={<HistoryOutlined />} onClick={() => fechar(() => estoque.abrir(item))}>
            Estoque
          </Button>
        )}
        antes={
          <Secao
            titulo="Categorias"
            descricao="Agrupam os materiais (descartáveis, medicamentos...) para filtrar a lista."
            acoes={
              <Button icon={<TagsOutlined />} onClick={() => setVerCategorias(true)}>
                {somenteLeitura ? 'Ver categorias' : 'Gerenciar categorias'}
              </Button>
            }
          >
            {categorias.carregando ? (
              <Skeleton.Input active size="small" aria-label="Carregando" />
            ) : categorias.erro && !categorias.itens.length ? (
              <span className="texto-apoio">
                Não foi possível carregar as categorias. <Button type="link" size="small" onClick={categorias.recarregar}>Tentar de novo</Button>
              </span>
            ) : categorias.itens.length ? (
              <Flex gap={4} wrap>
                {categorias.itens.map((c) => (
                  <Etiqueta key={c.id} tom="contorno">
                    {c.nome}
                  </Etiqueta>
                ))}
              </Flex>
            ) : (
              <span className="texto-apoio">Nenhuma categoria cadastrada.</span>
            )}
          </Secao>
        }
        campos={
          <>
            <h3 className="grupo-formulario">Material</h3>
            <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
              <Input maxLength={150} placeholder="Ex.: Luvas descartáveis (cx)" />
            </Form.Item>
            <Form.Item name="categoriaId" label="Categoria">
              <Select
                allowClear
                placeholder="Sem categoria"
                loading={categorias.carregando}
                options={categorias.itens.map((c) => ({ value: c.id, label: c.nome }))}
              />
            </Form.Item>

            {/* Unidade primeiro: as quantidades são contadas nela */}
            <h3 className="grupo-formulario">Estoque</h3>
            <Row gutter={12}>
              <Col xs={8}>
                <Form.Item name="unidade" label="Unidade">
                  <Input maxLength={10} placeholder="un, cx, pct" />
                </Form.Item>
              </Col>
              <Form.Item noStyle shouldUpdate>
                {({ getFieldValue }) =>
                  getFieldValue('id') ? (
                    <Col xs={8}>
                      <Form.Item label="Em estoque" extra="Muda por movimentação">
                        <strong>{quantidadeTexto(getFieldValue('quantidade'), getFieldValue('unidade'))}</strong>
                      </Form.Item>
                    </Col>
                  ) : (
                    <Col xs={8}>
                      <Form.Item name="quantidadeInicial" label="Estoque inicial" rules={[{ required: true, message: 'Informe a quantidade' }]}>
                        <InputNumber min={0} max={1000000} decimalSeparator="," />
                      </Form.Item>
                    </Col>
                  )
                }
              </Form.Item>
              <Col xs={8}>
                <Form.Item name="minimo" label="Mínimo">
                  <InputNumber min={0} max={99999999.99} decimalSeparator="," />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="ativo"
              label="Ativo"
              valuePropName="checked"
              extra="Inativo não aparece para novos serviços, mas o histórico do estoque é mantido."
            >
              <Switch />
            </Form.Item>
          </>
        }
      />
      <PainelEstoque painel={estoque} somenteLeitura={somenteLeitura} aoLancar={materiais.recarregar} />
      <PainelCategorias aberto={verCategorias} fechar={() => setVerCategorias(false)} categorias={categorias} somenteLeitura={somenteLeitura} />
    </>
  )
}
