import { useState } from 'react'
import { Card, Row, Col, Table, Segmented, Tag, Button, Flex, Typography, Alert, Modal, Form, Input, Popconfirm, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined, LockOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { modulos, niveis, recursos } from '../data/acesso.js'

const opcoesNivel = Object.entries(niveis).map(([value, n]) => ({ value, label: n.label }))
const nomeModulo = (codigo) => modulos.find((m) => m.codigo === codigo)?.nome

// Configurações > Perfis de acesso: nível (nenhum, leitura, escrita) de cada perfil em cada recurso (2.1 e 2.2)
export default function PerfisAcesso() {
  const { perfis, funcionarios } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const somenteLeitura = !pode('perfis_acesso', 'escrita')
  const [selecionadoId, setSelecionadoId] = useState(perfis.itens[0]?.id)
  const [novo, setNovo] = useState(false)
  const [form] = Form.useForm()

  const perfil = perfis.itens.find((p) => p.id === selecionadoId) ?? perfis.itens[0]
  const usuarios = (id) => funcionarios.itens.filter((f) => f.perfilId === id).length
  const bloqueado = somenteLeitura || perfil?.acessoTotal

  const definirNivel = (codigo, nivel) =>
    perfis.atualizar(perfil.id, { acessos: { ...perfil.acessos, [codigo]: nivel } })

  const criar = async () => {
    const v = await form.validateFields()
    setSelecionadoId(perfis.adicionar({ ...v, padrao: false, acessos: {} }))
    setNovo(false)
  }

  const excluir = () => {
    perfis.remover(perfil.id)
    setSelecionadoId(perfis.itens[0]?.id)
  }

  const colunas = [
    {
      title: 'Recurso',
      key: 'recurso',
      render: (_, r) => (
        <Flex vertical gap={2}>
          <Typography.Text strong>{r.nome}</Typography.Text>
          <Flex gap={4}>
            <Tag>{nomeModulo(r.modulo)}</Tag>
            {!moduloAtivo(r.modulo) && <Tag color="red">Módulo desativado</Tag>}
          </Flex>
        </Flex>
      ),
    },
    {
      title: 'O que permite',
      key: 'descricao',
      render: (_, r) => (
        <Flex vertical>
          <Typography.Text type="secondary">
            <b>Leitura:</b> {r.leitura}
          </Typography.Text>
          <Typography.Text type="secondary">
            <b>Escrita:</b> {r.escrita}
          </Typography.Text>
        </Flex>
      ),
    },
    {
      title: 'Nível',
      key: 'nivel',
      width: 250,
      render: (_, r) => (
        <Segmented
          options={opcoesNivel}
          value={perfil.acessoTotal ? 'escrita' : (perfil.acessos[r.codigo] ?? 'nenhum')}
          disabled={bloqueado}
          onChange={(nivel) => definirNivel(r.codigo, nivel)}
        />
      ),
    },
  ]

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={7}>
        <Card
          title="Perfis"
          extra={
            !somenteLeitura && (
              <Button
                icon={<PlusOutlined />}
                onClick={() => {
                  form.resetFields()
                  setNovo(true)
                }}
              >
                Novo
              </Button>
            )
          }
        >
          <Flex vertical gap={8}>
            {perfis.itens.map((p) => (
              <Card
                key={p.id}
                size="small"
                hoverable
                onClick={() => setSelecionadoId(p.id)}
                style={p.id === perfil?.id ? { borderColor: '#0f766e', background: '#f0fdfa' } : undefined}
              >
                <Flex justify="space-between" align="center">
                  <Typography.Text strong>
                    {p.acessoTotal && <LockOutlined style={{ marginRight: 6 }} />}
                    {p.nome}
                  </Typography.Text>
                  <Flex gap={4}>
                    {p.padrao && <Tag>Padrão</Tag>}
                    <Tag color="blue">{usuarios(p.id)} func.</Tag>
                  </Flex>
                </Flex>
                {p.descricao && <Typography.Text type="secondary">{p.descricao}</Typography.Text>}
              </Card>
            ))}
          </Flex>
        </Card>
      </Col>
      <Col xs={24} lg={17}>
        {perfil && (
          <Card
            title={
              <Typography.Text
                strong
                editable={!somenteLeitura && !perfil.padrao ? { onChange: (nome) => nome && perfis.atualizar(perfil.id, { nome }) } : false}
              >
                {perfil.nome}
              </Typography.Text>
            }
            extra={
              !somenteLeitura &&
              !perfil.padrao &&
              (usuarios(perfil.id) > 0 ? (
                <Tooltip title="Há funcionários com este perfil. Troque o perfil deles antes de excluir.">
                  <Button danger icon={<DeleteOutlined />} disabled>
                    Excluir
                  </Button>
                </Tooltip>
              ) : (
                <Popconfirm title="Excluir este perfil?" onConfirm={excluir}>
                  <Button danger icon={<DeleteOutlined />}>
                    Excluir
                  </Button>
                </Popconfirm>
              ))
            }
          >
            {perfil.acessoTotal && (
              <Alert
                type="warning"
                showIcon
                title="O Administrador tem escrita em tudo o que estiver ativo na loja e não pode ser alterado."
                style={{ marginBottom: 16 }}
              />
            )}
            {somenteLeitura && !perfil.acessoTotal && (
              <Alert type="info" showIcon title="Você tem acesso somente para leitura nesta tela." style={{ marginBottom: 16 }} />
            )}
            <Table rowKey="codigo" pagination={false} columns={colunas} dataSource={recursos} scroll={{ x: true }} />
          </Card>
        )}
      </Col>
      <Modal title="Novo perfil" open={novo} onOk={criar} onCancel={() => setNovo(false)} okText="Criar">
        <Form form={form} layout="vertical">
          <Form.Item
            name="nome"
            label="Nome"
            rules={[
              { required: true },
              {
                validator: (_, v) =>
                  perfis.itens.some((p) => p.nome.toLowerCase() === v?.trim().toLowerCase())
                    ? Promise.reject(new Error('Já existe um perfil com esse nome'))
                    : Promise.resolve(),
              },
            ]}
          >
            <Input maxLength={60} />
          </Form.Item>
          <Form.Item name="descricao" label="Descrição">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Typography.Text type="secondary">O perfil começa sem acesso a nada. Defina os níveis depois de criar.</Typography.Text>
        </Form>
      </Modal>
    </Row>
  )
}
