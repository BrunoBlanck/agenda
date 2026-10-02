import { Button, Col, Flex, Form, Input, InputNumber, Row, Select } from 'antd'
import { MinusCircleOutlined, PlusOutlined, TagOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { duracaoTexto, moeda } from '../utils/formatos.js'
import { rotulosLocal } from '../data/locais.js'

// Lista de nomes dentro de uma célula: separados por vírgula, sem virar uma fileira de etiquetas
const nomesEmLinha = (nomes) => nomes.join(', ')

export default function Servicos() {
  const { servicos, funcionarios, materiais, locais, loja } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const comMateriais = moduloAtivo('materiais')
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja.dados)

  const nomeFunc = (id) => funcionarios.todos.find((f) => f.id === id)?.nome ?? '—'
  const material = (id) => materiais.todos.find((m) => m.id === id)
  const nomeLocal = (id) => locais.todos.find((l) => l.id === id)?.nome ?? '—'

  const colunas = [
    { title: 'Serviço', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    { title: 'Duração', dataIndex: 'duracao', align: 'right', render: duracaoTexto },
    { title: 'Preço', dataIndex: 'preco', align: 'right', render: moeda },
    { title: 'Profissionais', dataIndex: 'funcionarioIds', render: (ids = []) => nomesEmLinha(ids.map(nomeFunc)) },
    comLocais && {
      title: rotulos.plural,
      dataIndex: 'localIds',
      render: (ids = []) => (ids.length === 0 ? <Etiqueta tom="contorno">Qualquer um</Etiqueta> : nomesEmLinha(ids.map(nomeLocal))),
    },
    comMateriais && {
      title: 'Materiais por atendimento',
      dataIndex: 'materiais',
      render: (lista = []) =>
        lista.length === 0 ? (
          <span className="texto-apoio">Nenhum</span>
        ) : (
          lista.map((m) => (
            <div key={m.materialId}>
              {m.quantidade} {material(m.materialId)?.unidade} de {material(m.materialId)?.nome}
            </div>
          ))
        ),
    },
  ].filter(Boolean)

  return (
    <CadastroTabela
      titulo="Serviços"
      descricao="O que a loja oferece. A duração e o preço preenchem o agendamento automaticamente."
      item="serviço"
      lista={servicos}
      colunas={colunas}
      somenteLeitura={!pode('servicos', 'escrita')}
      larguraPainel={560}
      valoresNovo={{ duracao: 30, localIds: [] }}
      iconeRegistro={() => <TagOutlined />}
      campos={
        <>
          <h3 className="grupo-formulario">Serviço</h3>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={100} placeholder="Ex.: Limpeza, Avaliação" />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={12}>
              <Form.Item name="duracao" label="Duração" rules={[{ required: true, message: 'Informe a duração' }]}>
                <InputNumber min={5} step={5} suffix="min" />
              </Form.Item>
            </Col>
            <Col xs={12}>
              <Form.Item name="preco" label="Preço">
                <InputNumber min={0} step={10} prefix="R$" decimalSeparator="," />
              </Form.Item>
            </Col>
          </Row>

          <h3 className="grupo-formulario">{comLocais ? 'Quem atende e onde' : 'Quem atende'}</h3>
          <Form.Item
            name="funcionarioIds"
            label="Profissionais que realizam"
            rules={[{ required: true, message: 'Escolha ao menos um profissional' }]}
          >
            <Select mode="multiple" options={funcionarios.itens.filter((f) => f.ativo).map((f) => ({ value: f.id, label: f.nome }))} />
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
                placeholder={`Qualquer ${rotulos.singular.toLowerCase()}`}
                options={locais.itens.filter((l) => l.ativo).map((l) => ({ value: l.id, label: l.nome }))}
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
                            <Select
                              placeholder="Material"
                              showSearch
                              optionFilterProp="label"
                              options={materiais.itens.map((m) => ({ value: m.id, label: m.nome }))}
                            />
                          </Form.Item>
                          <Form.Item name={[name, 'quantidade']} preserve className="item-lista">
                            <InputNumber min={1} aria-label="Quantidade" className="campo-quantidade" />
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
        </>
      }
    />
  )
}
