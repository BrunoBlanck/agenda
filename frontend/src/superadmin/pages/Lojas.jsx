import { useState } from 'react'
import { Card, Table, Input, Select, Flex, Button, Tag, Avatar, Typography, Modal, Form, Row, Col, Divider } from 'antd'
import { PlusOutlined, SearchOutlined, RightOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { statusLoja } from '../../data/plataforma.js'
import { usePlataforma } from '../usePlataforma.js'

const opcionais = modulos.filter((m) => m.opcional)

const gerarSlug = (texto = '') =>
  texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

export default function Lojas() {
  const { lojas, tipos, planos } = useData()
  const { nomeTipo, plano, funcionariosDe, criarLoja, ehAtual } = usePlataforma()
  const navigate = useNavigate()
  const [busca, setBusca] = useState('')
  const [tipo, setTipo] = useState(null)
  const [status, setStatus] = useState(null)
  const [nova, setNova] = useState(false)
  const [form] = Form.useForm()

  const dados = lojas.itens
    .filter((l) => `${l.nomeFantasia} ${l.nome} ${l.slug} ${l.cidade}`.toLowerCase().includes(busca.toLowerCase()))
    .filter((l) => !tipo || l.tipo === tipo)
    .filter((l) => !status || l.status === status)

  const salvar = async () => {
    const v = await form.validateFields()
    const id = criarLoja(v)
    setNova(false)
    navigate(`/superadmin/lojas/${id}`)
  }

  const colunas = [
    {
      title: 'Loja',
      key: 'loja',
      sorter: (a, b) => a.nomeFantasia.localeCompare(b.nomeFantasia),
      render: (_, l) => (
        <Flex align="center" gap={10}>
          <Avatar shape="square" src={l.logoUrl} style={{ background: '#4f46e5', flexShrink: 0 }}>
            {l.nomeFantasia[0]}
          </Avatar>
          <Flex vertical>
            <Typography.Text strong>
              {l.nomeFantasia} {ehAtual(l) && <Tag color="purple">aberta no painel</Tag>}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              /{l.slug}
            </Typography.Text>
          </Flex>
        </Flex>
      ),
    },
    { title: 'Tipo', dataIndex: 'tipo', render: nomeTipo },
    { title: 'Plano', dataIndex: 'planoId', render: (id) => plano(id)?.nome ?? '—' },
    { title: 'Cidade', key: 'cidade', render: (_, l) => (l.cidade ? `${l.cidade}/${l.uf}` : '—') },
    {
      title: 'Módulos opcionais',
      key: 'modulos',
      render: (_, l) => (
        <Flex gap={4} wrap>
          {opcionais.map((m) => (
            <Tag key={m.codigo} color={l.modulos?.[m.codigo] ? 'cyan' : 'default'} style={{ opacity: l.modulos?.[m.codigo] ? 1 : 0.5 }}>
              {m.nome}
            </Tag>
          ))}
        </Flex>
      ),
    },
    {
      title: 'Funcionários',
      key: 'funcionarios',
      align: 'center',
      render: (_, l) => funcionariosDe(l).filter((f) => f.ativo).length,
    },
    {
      title: 'Situação',
      dataIndex: 'status',
      render: (s) => <Tag color={statusLoja[s]?.color}>{statusLoja[s]?.label}</Tag>,
    },
    {
      key: 'abrir',
      width: 60,
      render: (_, l) => <Button type="text" icon={<RightOutlined />} onClick={() => navigate(`/superadmin/lojas/${l.id}`)} />,
    },
  ]

  return (
    <Card>
      <Flex justify="space-between" wrap gap={12} style={{ marginBottom: 16 }}>
        <Flex gap={8} wrap>
          <Input
            prefix={<SearchOutlined />}
            placeholder="Buscar por nome, endereço ou cidade"
            allowClear
            style={{ width: 280 }}
            onChange={(e) => setBusca(e.target.value)}
          />
          <Select
            allowClear
            placeholder="Todos os tipos"
            style={{ width: 160 }}
            onChange={setTipo}
            options={tipos.itens.map((t) => ({ value: t.codigo, label: t.nome }))}
          />
          <Select
            allowClear
            placeholder="Todas as situações"
            style={{ width: 170 }}
            onChange={setStatus}
            options={Object.entries(statusLoja).map(([value, s]) => ({ value, label: s.label }))}
          />
        </Flex>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            form.resetFields()
            setNova(true)
          }}
        >
          Nova loja
        </Button>
      </Flex>

      <Table
        rowKey="id"
        columns={colunas}
        dataSource={dados}
        scroll={{ x: true }}
        onRow={(l) => ({ onDoubleClick: () => navigate(`/superadmin/lojas/${l.id}`), style: { cursor: 'pointer' } })}
      />

      <Modal title="Nova loja" open={nova} onOk={salvar} onCancel={() => setNova(false)} okText="Criar loja" width={640}>
        <Form
          form={form}
          layout="vertical"
          onValuesChange={(mudou) => {
            if ('nomeFantasia' in mudou) form.setFieldsValue({ slug: gerarSlug(mudou.nomeFantasia) })
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="nomeFantasia" label="Nome da loja" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="nome" label="Razão social" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]}>
                <Select options={tipos.itens.filter((t) => t.ativo).map((t) => ({ value: t.codigo, label: t.nome }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="planoId" label="Plano" rules={[{ required: true }]} extra="Define os módulos iniciais da loja.">
                <Select options={planos.itens.filter((p) => p.ativo).map((p) => ({ value: p.id, label: p.nome }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="slug"
                label="Endereço de acesso"
                rules={[
                  { required: true },
                  {
                    validator: (_, v) =>
                      lojas.itens.some((l) => l.slug === v) ? Promise.reject(new Error('Já está em uso')) : Promise.resolve(),
                  },
                ]}
              >
                <Input prefix="/" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="email" label="E-mail da loja" rules={[{ type: 'email' }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Divider titlePlacement="start" plain>
            Primeiro funcionário (Administrador)
          </Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name={['admin', 'nome']} label="Nome" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name={['admin', 'email']} label="E-mail (login)" rules={[{ required: true }, { type: 'email' }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Typography.Text type="secondary">
            O administrador recebe um e-mail para definir a senha. Os perfis padrão são criados junto com a loja.
          </Typography.Text>
        </Form>
      </Modal>
    </Card>
  )
}
