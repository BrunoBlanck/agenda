import { Button, Col, Flex, Form, Input, InputNumber, Row, Select, Switch } from 'antd'
import { MinusCircleOutlined, PlusOutlined, TagOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import { EtiquetaSituacao } from '../components/Etiquetas.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useOpcoesServico, useServicos } from '../data/useServicos.js'
import { MAPA_ERROS_SERVICO } from '../data/api/servicos.js'
import { duracaoTexto, moeda } from '../utils/formatos.js'
import { rotulosLocal } from '../data/locais.js'

// Lista de nomes dentro de uma célula: separados por vírgula, sem virar uma fileira de etiquetas
const nomesEmLinha = (itens) => itens.map((i) => i.nome).join(', ')

// Opções de um Select: as ativas (vindas da API) + as já vinculadas a algum serviço, que podem estar
// inativas (aparecem marcadas, para dar para ver e retirar). Sem as ativas (só leitura), só as vinculadas.
function opcoesComVinculadas(ativas, vinculadas, rotulo = (i) => i.nome) {
  const porId = new Map()
  for (const item of ativas ?? []) porId.set(item.id, { value: item.id, label: rotulo(item) })
  for (const item of vinculadas) {
    if (!porId.has(item.id)) porId.set(item.id, { value: item.id, label: ativas ? `${rotulo(item)} (inativo)` : rotulo(item) })
  }
  return [...porId.values()].sort((a, b) => a.label.localeCompare(b.label, 'pt-BR'))
}

export default function Servicos() {
  const { pode, moduloAtivo, loja } = useAcesso()
  const somenteLeitura = !pode('servicos', 'escrita')
  const servicos = useServicos()
  const opcoes = useOpcoesServico({ ativo: !somenteLeitura })
  const comMateriais = moduloAtivo('materiais')
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja)

  const vinculados = (campo, id) => {
    const porId = new Map()
    for (const s of servicos.itens) for (const item of s[campo]) porId.set(item[id], { ...item, id: item[id] })
    return [...porId.values()]
  }
  const opcoesProfissionais = opcoesComVinculadas(opcoes.profissionais, vinculados('profissionais', 'id'))
  const opcoesLocais = opcoesComVinculadas(opcoes.locais, vinculados('locais', 'id'))
  // Unidade junto do nome, quando o nome ainda não diz ("Luvas (cx)")
  const opcoesMateriais = opcoesComVinculadas(opcoes.materiais, vinculados('materiais', 'materialId'), (m) =>
    m.unidade && !m.nome.endsWith(`(${m.unidade})`) ? `${m.nome} (${m.unidade})` : m.nome,
  )

  const colunas = [
    { title: 'Serviço', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    { title: 'Duração', dataIndex: 'duracao', align: 'right', render: duracaoTexto },
    { title: 'Preço', dataIndex: 'preco', align: 'right', render: moeda },
    {
      title: 'Profissionais',
      dataIndex: 'profissionais',
      render: (lista = []) => (lista.length ? nomesEmLinha(lista) : <span className="texto-apoio">Nenhum</span>),
    },
    comLocais && {
      title: rotulos.plural,
      dataIndex: 'locais',
      render: (lista = []) => (lista.length === 0 ? <Etiqueta tom="contorno">Qualquer um</Etiqueta> : nomesEmLinha(lista)),
    },
    comMateriais && {
      title: 'Materiais por atendimento',
      dataIndex: 'materiais',
      cartao: 'bloco',
      render: (lista = []) =>
        lista.length === 0 ? (
          <span className="texto-apoio">Nenhum</span>
        ) : (
          lista.map((m) => (
            <div key={m.materialId}>
              {m.quantidade ?? '—'} {m.unidade} de {m.nome}
            </div>
          ))
        ),
    },
    {
      title: 'Situação',
      dataIndex: 'ativo',
      cartao: 'etiqueta',
      filters: [
        { text: 'Ativo', value: true },
        { text: 'Inativo', value: false },
      ],
      onFilter: (v, s) => s.ativo === v,
      render: (ativo) => <EtiquetaSituacao ativo={ativo} />,
    },
  ].filter(Boolean)

  return (
    <CadastroTabela
      titulo="Serviços"
      descricao="O que a loja oferece. A duração e o preço preenchem o agendamento automaticamente."
      item="serviço"
      lista={servicos}
      colunas={colunas}
      somenteLeitura={somenteLeitura}
      larguraPainel={560}
      larguraTabela={comMateriais || comLocais ? 960 : undefined}
      valoresNovo={{ duracao: 30, localIds: [], materiais: [], funcionarioIds: [], ativo: true }}
      mapaErros={MAPA_ERROS_SERVICO}
      textoExcluir="Agendamentos antigos continuam mostrando o serviço. Se houver agendamentos marcados, inative-o."
      iconeRegistro={() => <TagOutlined />}
      campos={
        <>
          <h3 className="grupo-formulario">Serviço</h3>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={120} placeholder="Ex.: Limpeza, Avaliação" />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={12}>
              <Form.Item name="duracao" label="Duração" rules={[{ required: true, message: 'Informe a duração' }]}>
                <InputNumber min={5} max={1440} step={5} precision={0} suffix="min" />
              </Form.Item>
            </Col>
            <Col xs={12}>
              <Form.Item name="preco" label="Preço">
                <InputNumber min={0} max={99999999.99} step={10} precision={2} prefix="R$" decimalSeparator="," />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="descricao" label="Descrição">
            <Input.TextArea rows={2} maxLength={2000} placeholder="Opcional. Ex.: inclui raspagem e polimento" />
          </Form.Item>

          <h3 className="grupo-formulario">{comLocais ? 'Quem atende e onde' : 'Quem atende'}</h3>
          <Form.Item
            name="funcionarioIds"
            label="Profissionais que realizam"
            extra={
              opcoes.erro && (
                <span>
                  Não foi possível carregar as opções do formulário.{' '}
                  <Button type="link" size="small" onClick={opcoes.recarregar}>
                    Tentar de novo
                  </Button>
                </span>
              )
            }
            dependencies={['ativo']}
            rules={[
              ({ getFieldValue }) => ({
                validator: (_, ids) =>
                  !getFieldValue('ativo') || ids?.length
                    ? Promise.resolve()
                    : Promise.reject(new Error('Escolha ao menos um profissional')),
              }),
            ]}
          >
            <Select
              mode="multiple"
              optionFilterProp="label"
              loading={opcoes.carregando}
              options={opcoesProfissionais}
            />
          </Form.Item>
          {comLocais && (
            <Form.Item
              name="localIds"
              label={`${rotulos.plural} onde acontece`}
              extra="Vazio vale qualquer um ativo. Ex.: aula de piano só na sala do piano; aula de violão em qualquer sala."
            >
              <Select
                mode="multiple"
                allowClear
                optionFilterProp="label"
                loading={opcoes.carregando}
                placeholder={`Qualquer ${rotulos.singular.toLowerCase()}`}
                options={opcoesLocais}
              />
            </Form.Item>
          )}
          {comMateriais && (
            <>
              <h3 className="grupo-formulario">Materiais</h3>
              <Form.Item label="Usados em cada atendimento">
                <Form.List name="materiais">
                  {(fields, { add, remove }) => (
                    <Flex vertical gap={8}>
                      {/* preserve nos itens: com o formulário em preserve={false}, desmontar um item da lista
                          (o StrictMode faz isso no desenvolvimento) apagaria o valor dele */}
                      {fields.map(({ key, name }) => (
                        <Flex key={key} gap={8} align="start">
                          <Form.Item name={[name, 'materialId']} preserve rules={[{ required: true, message: 'Escolha o material' }]} className="item-lista item-lista-principal">
                            <Select placeholder="Material" showSearch optionFilterProp="label" loading={opcoes.carregando} options={opcoesMateriais} />
                          </Form.Item>
                          <Form.Item
                            name={[name, 'quantidade']}
                            preserve
                            rules={[{ required: true, message: 'Informe a quantidade' }]}
                            className="item-lista"
                          >
                            <InputNumber min={0.01} max={1000000} decimalSeparator="," aria-label="Quantidade" className="campo-quantidade" />
                          </Form.Item>
                          <Button type="text" icon={<MinusCircleOutlined />} aria-label="Remover material" onClick={() => remove(name)} />
                        </Flex>
                      ))}
                      <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ quantidade: 1 })}>
                        Adicionar material
                      </Button>
                    </Flex>
                  )}
                </Form.List>
              </Form.Item>
            </>
          )}

          <Form.Item
            name="ativo"
            label="Ativo"
            valuePropName="checked"
            extra="Inativo não aparece em novos agendamentos nem no site, mas o histórico é mantido."
          >
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
