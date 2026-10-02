import { useState } from 'react'
import { Card, Row, Col, Table, Segmented, Tag, Button, Flex, Typography, Alert, Modal, Form, Input, Popconfirm, Tooltip, Tabs, Select } from 'antd'
import { PlusOutlined, DeleteOutlined, LockOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { modulos, niveis, recursos } from '../data/acesso.js'
import JornadaPerfil from '../components/perfis/JornadaPerfil.jsx'
import BloqueiosPerfil from '../components/perfis/BloqueiosPerfil.jsx'

const opcoesNivel = Object.entries(niveis).map(([value, n]) => ({ value, label: n.label }))
const nomeModulo = (codigo) => modulos.find((m) => m.codigo === codigo)?.nome

// Configurações > Perfis e horários: o perfil reúne os níveis de acesso (2.1 e 2.2), a jornada semanal (2.5)
// e os bloqueios (2.6). O funcionário é vinculado ao perfil uma vez só e herda tudo isso.
export default function PerfisAcesso() {
  const { perfis, funcionarios, jornadas, bloqueios } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const verAcessos = pode('perfis_acesso')
  const somenteLeitura = !pode('perfis_acesso', 'escrita')
  const verHorarios = pode('config_agendamentos')
  const horariosSomenteLeitura = !pode('config_agendamentos', 'escrita')
  const [selecionadoId, setSelecionadoId] = useState(perfis.itens[0]?.id)
  const [novo, setNovo] = useState(false)
  const [form] = Form.useForm()

  const perfil = perfis.itens.find((p) => p.id === selecionadoId) ?? perfis.itens[0]
  const doPerfil = (id) => funcionarios.itens.filter((f) => f.perfilId === id)
  const usuarios = (id) => doPerfil(id).length
  const bloqueado = somenteLeitura || perfil?.acessoTotal

  const definirNivel = (codigo, nivel) =>
    perfis.atualizar(perfil.id, { acessos: { ...perfil.acessos, [codigo]: nivel } })

  // Novo perfil pode partir de outro: copia os níveis e a jornada (útil para o mesmo cargo em outro horário)
  const criar = async () => {
    const { copiarDe, ...v } = await form.validateFields()
    const base = perfis.itens.find((p) => p.id === copiarDe)
    const id = perfis.adicionar({ ...v, padrao: false, acessos: base && !base.acessoTotal ? { ...base.acessos } : {} })
    jornadas.itens
      .filter((j) => j.perfilId === copiarDe)
      .forEach(({ diaSemana, inicio, fim }) => jornadas.adicionar({ perfilId: id, diaSemana, inicio, fim }))
    setSelecionadoId(id)
    setNovo(false)
  }

  // Jornada e bloqueios do perfil saem junto com ele
  const excluir = () => {
    jornadas.itens.filter((j) => j.perfilId === perfil.id).forEach((j) => jornadas.remover(j.id))
    bloqueios.itens.filter((b) => b.perfilId === perfil.id).forEach((b) => bloqueios.remover(b.id))
    perfis.remover(perfil.id)
    setSelecionadoId(perfis.itens.find((p) => p.id !== perfil.id)?.id)
  }

  const semJornada = (id) => !jornadas.itens.some((j) => j.perfilId === id)

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
                    {verHorarios && semJornada(p.id) && <Tag color="orange">Sem jornada</Tag>}
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
            <Flex gap={6} wrap align="center" style={{ marginBottom: 8 }}>
              <Typography.Text type="secondary">Funcionários neste perfil:</Typography.Text>
              {doPerfil(perfil.id).length ? (
                doPerfil(perfil.id).map((f) => (
                  <Tag key={f.id}>
                    {f.nome}
                    {!f.ativo && ' (inativo)'}
                  </Tag>
                ))
              ) : (
                <Typography.Text type="secondary">nenhum</Typography.Text>
              )}
            </Flex>
            <Tabs
              items={[
                verAcessos && {
                  key: 'acessos',
                  label: 'Níveis de acesso',
                  children: (
                    <>
                      {perfil.acessoTotal && (
                        <Alert
                          type="warning"
                          showIcon
                          title="O Administrador tem escrita em tudo o que estiver ativo na loja e não pode ser alterado."
                          style={{ marginBottom: 16 }}
                        />
                      )}
                      {somenteLeitura && !perfil.acessoTotal && (
                        <Alert type="info" showIcon title="Você tem acesso somente para leitura nesta parte." style={{ marginBottom: 16 }} />
                      )}
                      <Table rowKey="codigo" pagination={false} columns={colunas} dataSource={recursos} scroll={{ x: true }} />
                    </>
                  ),
                },
                verHorarios && {
                  key: 'jornada',
                  label: 'Jornada semanal',
                  children: <JornadaPerfil perfil={perfil} somenteLeitura={horariosSomenteLeitura} />,
                },
                verHorarios && {
                  key: 'bloqueios',
                  label: 'Bloqueios, folgas e feriados',
                  children: <BloqueiosPerfil perfil={perfil} somenteLeitura={horariosSomenteLeitura} />,
                },
              ].filter(Boolean)}
            />
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
          <Form.Item
            name="copiarDe"
            label="Copiar níveis e jornada de"
            extra="Em branco, o perfil começa sem acesso a nada e sem jornada. Ajuste depois de criar."
          >
            <Select allowClear placeholder="Começar do zero" options={perfis.itens.map((p) => ({ value: p.id, label: p.nome }))} />
          </Form.Item>
        </Form>
      </Modal>
    </Row>
  )
}
