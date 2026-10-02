import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Card, Tabs, Form, Input, Select, Button, Row, Col, Flex, Avatar, Tag, Typography, Table, Switch, DatePicker,
  Modal, Popconfirm, Result, Alert, message,
} from 'antd'
import { ArrowLeftOutlined, SaveOutlined, PlusOutlined, EditOutlined, KeyOutlined, ExportOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { opcoesTipoLoja, statusLoja } from '../../data/plataforma.js'
import { cnpjValido, mascaraCep, mascaraCnpj, mascaraTelefone } from '../../utils/formatos.js'
import UltimaAlteracao from '../../components/UltimaAlteracao.jsx'
import { usePlataforma } from '../usePlataforma.js'
import HistoricoAlteracoes from '../HistoricoAlteracoes.jsx'

function DadosGerais({ loja }) {
  const { planos } = useData()
  const { editarLoja } = usePlataforma()
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()

  const salvar = async () => {
    editarLoja(loja, await form.validateFields())
    msg.success('Loja atualizada.')
  }

  return (
    <>
      {contextHolder}
      <Form form={form} layout="vertical" initialValues={loja}>
        <Typography.Title level={5}>Plataforma</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={6}>
            <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]} extra="Define o site do consumidor final.">
              <Select options={opcoesTipoLoja} />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="planoId" label="Plano" rules={[{ required: true }]} extra="Só o valor cobrado. Não altera os módulos.">
              <Select options={planos.itens.map((p) => ({ value: p.id, label: p.nome, disabled: !p.ativo }))} />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="status" label="Situação" rules={[{ required: true }]}>
              <Select options={Object.entries(statusLoja).map(([value, s]) => ({ value, label: s.label }))} />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="slug" label="Endereço de acesso" rules={[{ required: true }]}>
              <Input prefix="/" />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="fusoHorario" label="Fuso horário">
              <Select
                options={['America/Sao_Paulo', 'America/Manaus', 'America/Cuiaba', 'America/Rio_Branco', 'America/Noronha'].map((f) => ({ value: f, label: f }))}
              />
            </Form.Item>
          </Col>
        </Row>

        <Typography.Title level={5}>Dados da loja</Typography.Title>
        <Typography.Paragraph type="secondary">A própria loja também pode editar estes dados em Configurações.</Typography.Paragraph>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="nomeFantasia" label="Nome da loja" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="nome" label="Razão social" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="cnpj"
              label="CNPJ"
              normalize={mascaraCnpj}
              rules={[{ validator: (_, v) => (!v || cnpjValido(v) ? Promise.resolve() : Promise.reject(new Error('CNPJ inválido'))) }]}
            >
              <Input placeholder="Opcional" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="telefone" label="Telefone" normalize={mascaraTelefone}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="email" label="E-mail" rules={[{ type: 'email' }]}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item name="cep" label="CEP" normalize={mascaraCep}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={10}>
            <Form.Item name="logradouro" label="Logradouro">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={3}>
            <Form.Item name="numero" label="Número">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={7}>
            <Form.Item name="complemento" label="Complemento">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={10}>
            <Form.Item name="bairro" label="Bairro">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={10}>
            <Form.Item name="cidade" label="Cidade">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item name="uf" label="UF" normalize={(v) => v?.toUpperCase().slice(0, 2)}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
      </Form>
      <Flex justify="space-between" align="center">
        <UltimaAlteracao item={loja} />
        <Button type="primary" icon={<SaveOutlined />} onClick={salvar}>
          Salvar
        </Button>
      </Flex>
    </>
  )
}

function Modulos({ loja }) {
  const { definirModulo } = usePlataforma()

  const colunas = [
    { title: 'Módulo', dataIndex: 'nome', render: (n) => <Typography.Text strong>{n}</Typography.Text> },
    {
      title: 'Situação',
      key: 'situacao',
      width: 150,
      render: (_, m) =>
        m.opcional ? (
          <Switch
            checked={!!loja.modulos?.[m.codigo]}
            checkedChildren="Ativo"
            unCheckedChildren="Desativado"
            onChange={(ativo) => definirModulo(loja, m.codigo, { ativo })}
          />
        ) : (
          <Tag>Sempre ativo</Tag>
        ),
    },
    {
      title: 'Observação',
      key: 'observacao',
      render: (_, m) =>
        m.opcional && (
          <Input
            key={`${loja.id}-${m.codigo}`}
            defaultValue={loja.modulosInfo?.[m.codigo]?.observacao}
            placeholder='Ex.: "liberado como cortesia até dez/2026"'
            onBlur={(e) =>
              e.target.value !== (loja.modulosInfo?.[m.codigo]?.observacao ?? '') &&
              definirModulo(loja, m.codigo, { observacao: e.target.value })
            }
          />
        ),
    },
    {
      title: 'Expira em',
      key: 'expira',
      width: 180,
      render: (_, m) =>
        m.opcional && (
          <DatePicker
            format="DD/MM/YYYY"
            placeholder="Sem prazo"
            value={loja.modulosInfo?.[m.codigo]?.expiraEm ? dayjs(loja.modulosInfo[m.codigo].expiraEm) : null}
            onChange={(d) => definirModulo(loja, m.codigo, { expiraEm: d ? d.endOf('day').toISOString() : null })}
          />
        ),
    },
  ]

  return (
    <>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="Ligue só o que a loja usa: o que estiver desligado some do menu da loja. Não depende do tipo nem do plano. Desativar não apaga dados: tudo volta ao reativar."
      />
      <Table rowKey="codigo" pagination={false} columns={colunas} dataSource={modulos} />
    </>
  )
}

function Funcionarios({ loja }) {
  const { funcionariosDe, perfisDe, salvarFuncionario, redefinirSenha: registrarSenha } = usePlataforma()
  const [editando, setEditando] = useState(null)
  const [form] = Form.useForm()
  const [msg, contextHolder] = message.useMessage()
  const lista = funcionariosDe(loja)

  const abrir = (f) => {
    setEditando(f)
    form.resetFields()
    form.setFieldsValue(f.id ? f : { perfil: 'Administrador', ativo: true })
  }

  const salvar = async () => {
    const v = await form.validateFields()
    const admins = lista.filter((f) => f.id !== editando.id && f.ativo && f.perfil === 'Administrador')
    if (editando.perfil === 'Administrador' && (v.perfil !== 'Administrador' || !v.ativo) && admins.length === 0) {
      msg.error('A loja precisa de pelo menos um Administrador ativo.')
      return
    }
    salvarFuncionario(loja, v, editando.id)
    setEditando(null)
  }

  const redefinirSenha = (f) => {
    registrarSenha(loja, f)
    msg.success(`Link para criar nova senha enviado para ${f.email}.`)
  }

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome) },
    { title: 'E-mail (login)', dataIndex: 'email' },
    { title: 'Perfil', dataIndex: 'perfil', render: (p) => <Tag color={p === 'Administrador' ? 'gold' : 'default'}>{p}</Tag> },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => (a ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>) },
    {
      title: 'Criado por',
      key: 'origem',
      render: (_, f) => (f.criadoPorSuperadmin ? <Tag color="purple">Superadmin</Tag> : <Tag>Loja</Tag>),
    },
    {
      title: 'Ações',
      key: 'acoes',
      width: 110,
      render: (_, f) => (
        <Flex gap={4}>
          <Button type="text" icon={<EditOutlined />} onClick={() => abrir(f)} />
          <Popconfirm title={`Enviar link de nova senha para ${f.email}?`} onConfirm={() => redefinirSenha(f)}>
            <Button type="text" icon={<KeyOutlined />} title="Redefinir senha" />
          </Popconfirm>
        </Flex>
      ),
    },
  ]

  return (
    <>
      {contextHolder}
      <Flex justify="space-between" align="center" style={{ marginBottom: 16 }}>
        <Typography.Text type="secondary">O superadmin pode criar funcionários com qualquer perfil, inclusive Administrador.</Typography.Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => abrir({})}>
          Novo funcionário
        </Button>
      </Flex>
      <Table rowKey="id" columns={colunas} dataSource={lista} pagination={false} scroll={{ x: true }} />
      <Modal
        title={editando?.id ? 'Editar funcionário' : 'Novo funcionário'}
        open={!!editando}
        onOk={salvar}
        onCancel={() => setEditando(null)}
        okText="Salvar"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="E-mail (login)"
            rules={[
              { required: true },
              { type: 'email' },
              {
                validator: (_, v) =>
                  lista.some((f) => f.id !== editando?.id && f.email === v)
                    ? Promise.reject(new Error('Já existe um funcionário com esse e-mail nesta loja'))
                    : Promise.resolve(),
              },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="perfil" label="Perfil de acesso" rules={[{ required: true }]}>
            <Select options={perfisDe(loja).map((p) => ({ value: p, label: p }))} />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked">
            <Switch />
          </Form.Item>
          {!editando?.id && (
            <Typography.Text type="secondary">O funcionário recebe um e-mail para definir a senha.</Typography.Text>
          )}
        </Form>
      </Modal>
    </>
  )
}

export default function LojaDetalhe() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { lojas } = useData()
  const { nomeTipo, plano, ehAtual, editarLoja } = usePlataforma()
  const loja = lojas.itens.find((l) => String(l.id) === id)

  if (!loja) {
    return <Result status="404" title="Loja não encontrada" extra={<Button onClick={() => navigate('/superadmin/lojas')}>Voltar</Button>} />
  }

  return (
    <Flex vertical gap={16}>
      <Card>
        <Flex justify="space-between" align="center" wrap gap={16}>
          <Flex align="center" gap={16}>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/superadmin/lojas')} />
            <Avatar shape="square" size={56} src={loja.logoUrl} style={{ background: '#4f46e5', fontSize: 24 }}>
              {loja.nomeFantasia[0]}
            </Avatar>
            <Flex vertical gap={4}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                {loja.nomeFantasia}
              </Typography.Title>
              <Flex gap={4} wrap>
                <Tag>{nomeTipo(loja.tipo)}</Tag>
                <Tag color="blue">Plano {plano(loja.planoId)?.nome}</Tag>
                <Tag color={statusLoja[loja.status]?.color}>{statusLoja[loja.status]?.label}</Tag>
                <Typography.Text type="secondary">
                  /{loja.slug} · cliente desde {dayjs(loja.criadoEm).format('MM/YYYY')}
                </Typography.Text>
              </Flex>
            </Flex>
          </Flex>
          <Flex gap={8}>
            {ehAtual(loja) && (
              <Button icon={<ExportOutlined />} onClick={() => navigate('/painel')}>
                Abrir painel da loja
              </Button>
            )}
            {loja.status === 'ativa' ? (
              <Popconfirm
                title="Suspender a loja?"
                description="Os funcionários não conseguirão entrar. Os dados são mantidos."
                onConfirm={() => editarLoja(loja, { status: 'suspensa' })}
              >
                <Button danger>Suspender</Button>
              </Popconfirm>
            ) : (
              <Button type="primary" onClick={() => editarLoja(loja, { status: 'ativa' })}>
                Reativar
              </Button>
            )}
          </Flex>
        </Flex>
      </Card>
      {loja.status !== 'ativa' && (
        <Alert
          type={loja.status === 'suspensa' ? 'warning' : 'error'}
          showIcon
          title={
            loja.status === 'suspensa'
              ? 'Loja suspensa: os funcionários não conseguem entrar, mas os dados estão mantidos.'
              : 'Loja cancelada: dados mantidos pelo período definido antes da remoção.'
          }
        />
      )}
      <Card>
        <Tabs
          items={[
            { key: 'dados', label: 'Dados gerais', children: <DadosGerais key={`${loja.id}-${loja.status}`} loja={loja} /> },
            { key: 'modulos', label: 'Módulos', children: <Modulos loja={loja} /> },
            { key: 'funcionarios', label: 'Funcionários', children: <Funcionarios loja={loja} /> },
            { key: 'historico', label: 'Histórico', children: <HistoricoAlteracoes lojaId={loja.id} /> },
          ]}
        />
      </Card>
    </Flex>
  )
}
