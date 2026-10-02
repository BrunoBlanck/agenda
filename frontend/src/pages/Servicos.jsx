import { Form, Input, InputNumber, Select, Button, Flex, Tag } from 'antd'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { moeda } from '../utils/formatos.js'
import { rotulosLocal } from '../data/locais.js'

export default function Servicos() {
  const { servicos, funcionarios, materiais, locais, loja } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const comMateriais = moduloAtivo('materiais')
  const comLocais = moduloAtivo('locais')
  const rotulos = rotulosLocal(loja.dados)

  const nomeFunc = (id) => funcionarios.itens.find((f) => f.id === id)?.nome ?? '—'
  const material = (id) => materiais.itens.find((m) => m.id === id)
  const nomeLocal = (id) => locais.itens.find((l) => l.id === id)?.nome ?? '—'

  const colunas = [
    { title: 'Serviço', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
    { title: 'Duração', dataIndex: 'duracao', render: (d) => `${d} min` },
    { title: 'Preço', dataIndex: 'preco', render: moeda },
    {
      title: 'Profissionais',
      dataIndex: 'funcionarioIds',
      render: (ids = []) => ids.map((id) => <Tag key={id}>{nomeFunc(id)}</Tag>),
    },
    comLocais && {
      title: rotulos.plural,
      dataIndex: 'localIds',
      render: (ids = []) =>
        ids.length === 0 ? <Tag color="cyan">Qualquer</Tag> : ids.map((id) => <Tag key={id}>{nomeLocal(id)}</Tag>),
    },
    comMateriais && {
      title: 'Materiais',
      dataIndex: 'materiais',
      render: (lista = []) =>
        lista.length === 0
          ? '—'
          : lista.map((m) => (
              <div key={m.materialId}>
                {m.quantidade} {material(m.materialId)?.unidade} · {material(m.materialId)?.nome}
              </div>
            )),
    },
  ].filter(Boolean)

  return (
    <CadastroTabela
      titulo="Serviço"
      lista={servicos}
      colunas={colunas}
      somenteLeitura={!pode('servicos', 'escrita')}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}><Input /></Form.Item>
          <Flex gap={16}>
            <Form.Item name="duracao" label="Duração" rules={[{ required: true }]} initialValue={30}>
              <InputNumber min={5} step={5} suffix="min" />
            </Form.Item>
            <Form.Item name="preco" label="Preço">
              <InputNumber min={0} step={10} prefix="R$" />
            </Form.Item>
          </Flex>
          <Form.Item
            name="funcionarioIds"
            label="Profissionais que realizam"
            rules={[{ required: true, message: 'Selecione ao menos um profissional' }]}
          >
            <Select
              mode="multiple"
              options={funcionarios.itens.filter((f) => f.ativo).map((f) => ({ value: f.id, label: f.nome }))}
            />
          </Form.Item>
          {comLocais && (
            <Form.Item
              name="localIds"
              label={`${rotulos.plural} onde acontece`}
              initialValue={[]}
              extra="Se ficar vazio, vale qualquer opção ativa da lista. Ex.: aula de piano só na sala do piano; aula de violão em qualquer sala."
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
            <Form.Item label="Materiais utilizados (por atendimento)">
              <Form.List name="materiais">
                {(fields, { add, remove }) => (
                  <Flex vertical gap={8}>
                    {fields.map(({ key, name }) => (
                      <Flex key={key} gap={8} align="start">
                        <Form.Item name={[name, 'materialId']} rules={[{ required: true }]} style={{ flex: 1, marginBottom: 0 }}>
                          <Select
                            placeholder="Material"
                            showSearch
                            optionFilterProp="label"
                            options={materiais.itens.map((m) => ({ value: m.id, label: m.nome }))}
                          />
                        </Form.Item>
                        <Form.Item name={[name, 'quantidade']} initialValue={1} style={{ marginBottom: 0 }}>
                          <InputNumber min={1} style={{ width: 80 }} />
                        </Form.Item>
                        <Button type="text" icon={<MinusCircleOutlined />} onClick={() => remove(name)} />
                      </Flex>
                    ))}
                    <Button type="dashed" icon={<PlusOutlined />} onClick={() => add()}>
                      Adicionar material
                    </Button>
                  </Flex>
                )}
              </Form.List>
            </Form.Item>
          )}
        </>
      }
    />
  )
}
