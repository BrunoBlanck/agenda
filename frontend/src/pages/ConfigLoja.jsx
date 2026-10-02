import { useState } from 'react'
import { Card, Form, Input, Button, Row, Col, Upload, Avatar, Flex, Descriptions, Tag, Typography, Alert, message } from 'antd'
import { UploadOutlined, DeleteOutlined, ShopOutlined, SaveOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { modulos } from '../data/acesso.js'
import { statusLoja as situacao } from '../data/plataforma.js'
import UltimaAlteracao from '../components/UltimaAlteracao.jsx'
import { cnpjValido, mascaraCep, mascaraCnpj, mascaraTelefone, soDigitos } from '../utils/formatos.js'

const TIPOS_LOGO = ['image/png', 'image/jpeg', 'image/svg+xml']
const LOGO_MAX_MB = 2


// Configurações > Dados da loja (estrutura.md, 2.18)
export default function ConfigLoja() {
  const { loja, tipos, planos } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const [form] = Form.useForm()
  const [logo, setLogo] = useState(loja.dados.logoUrl)
  const [msg, contextHolder] = message.useMessage()
  const somenteLeitura = !pode('config_loja', 'escrita')
  const dados = loja.dados

  const escolherLogo = (arquivo) => {
    if (!TIPOS_LOGO.includes(arquivo.type)) {
      msg.error('Envie uma imagem PNG, JPG ou SVG.')
    } else if (arquivo.size > LOGO_MAX_MB * 1024 * 1024) {
      msg.error(`A imagem deve ter no máximo ${LOGO_MAX_MB} MB.`)
    } else {
      // No sistema real o arquivo vai para o storage e aqui fica só o caminho
      const leitor = new FileReader()
      leitor.onload = () => setLogo(leitor.result)
      leitor.readAsDataURL(arquivo)
    }
    return Upload.LIST_IGNORE
  }

  const buscarCep = async () => {
    const cep = soDigitos(form.getFieldValue('cep'))
    if (cep.length !== 8) return
    try {
      const resposta = await fetch(`https://viacep.com.br/ws/${cep}/json/`)
      const endereco = await resposta.json()
      if (endereco.erro) {
        msg.warning('CEP não encontrado.')
        return
      }
      form.setFieldsValue({
        logradouro: endereco.logradouro,
        bairro: endereco.bairro,
        cidade: endereco.localidade,
        uf: endereco.uf,
      })
    } catch {
      // Sem conexão: o endereço é preenchido manualmente
    }
  }

  const salvar = async () => {
    const valores = await form.validateFields()
    loja.atualizar({ ...valores, logoUrl: logo })
    msg.success('Dados da loja salvos.')
  }

  return (
    <Flex vertical gap={16}>
      {contextHolder}
      {somenteLeitura && <Alert type="info" showIcon title="Você tem acesso somente para leitura nesta tela." />}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={7}>
          <Card title="Logo da loja" style={{ height: '100%' }}>
            <Flex vertical align="center" gap={16}>
              <Avatar shape="square" size={140} src={logo} icon={!logo && <ShopOutlined />} />
              {!somenteLeitura && (
                <Flex gap={8}>
                  <Upload accept={TIPOS_LOGO.join(',')} showUploadList={false} beforeUpload={escolherLogo}>
                    <Button icon={<UploadOutlined />}>{logo ? 'Trocar' : 'Enviar logo'}</Button>
                  </Upload>
                  {logo && <Button danger icon={<DeleteOutlined />} onClick={() => setLogo(null)} />}
                </Flex>
              )}
              <Typography.Text type="secondary" style={{ textAlign: 'center' }}>
                PNG, JPG ou SVG, até {LOGO_MAX_MB} MB. Aparece no menu lateral.
              </Typography.Text>
            </Flex>
          </Card>
        </Col>

        <Col xs={24} lg={17}>
          <Card
            title="Dados da loja"
            extra={
              !somenteLeitura && (
                <Button type="primary" icon={<SaveOutlined />} onClick={salvar}>
                  Salvar
                </Button>
              )
            }
          >
            <Form form={form} layout="vertical" initialValues={dados} disabled={somenteLeitura}>
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="nomeFantasia" label="Nome da loja" rules={[{ required: true }]}>
                    <Input maxLength={150} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="nome" label="Razão social" rules={[{ required: true }]}>
                    <Input maxLength={150} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item
                    name="cnpj"
                    label="CNPJ"
                    normalize={mascaraCnpj}
                    rules={[
                      {
                        validator: (_, v) =>
                          !v || cnpjValido(v) ? Promise.resolve() : Promise.reject(new Error('CNPJ inválido')),
                      },
                    ]}
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
                  <Form.Item name="email" label="E-mail da loja" rules={[{ type: 'email', message: 'E-mail inválido' }]}>
                    <Input />
                  </Form.Item>
                </Col>
              </Row>

              <Typography.Title level={5}>Endereço</Typography.Title>
              <Row gutter={16}>
                <Col xs={24} md={6}>
                  <Form.Item name="cep" label="CEP" normalize={mascaraCep} extra="Preenche o endereço automaticamente">
                    <Input onBlur={buscarCep} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={14}>
                  <Form.Item name="logradouro" label="Logradouro">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={4}>
                  <Form.Item name="numero" label="Número">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item name="complemento" label="Complemento">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item name="bairro" label="Bairro">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={7}>
                  <Form.Item name="cidade" label="Cidade">
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} md={3}>
                  <Form.Item name="uf" label="UF" normalize={(v) => v?.toUpperCase().slice(0, 2)}>
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
            <UltimaAlteracao item={dados} />
          </Card>
        </Col>
      </Row>

      <Card title="Definido pela plataforma" extra={<Typography.Text type="secondary">Para alterar, fale com o suporte</Typography.Text>}>
        <Descriptions column={{ xs: 1, md: 2, xl: 3 }}>
          <Descriptions.Item label="Tipo">{tipos.itens.find((t) => t.codigo === dados.tipo)?.nome}</Descriptions.Item>
          <Descriptions.Item label="Endereço de acesso">/{dados.slug}</Descriptions.Item>
          <Descriptions.Item label="Plano">{planos.itens.find((p) => p.id === dados.planoId)?.nome}</Descriptions.Item>
          <Descriptions.Item label="Situação">
            <Tag color={situacao[dados.status]?.color}>{situacao[dados.status]?.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Fuso horário">{dados.fusoHorario}</Descriptions.Item>
          <Descriptions.Item label="Módulos opcionais">
            <Flex gap={4} wrap>
              {modulos
                .filter((m) => m.opcional)
                .map((m) => (
                  <Tag key={m.codigo} color={moduloAtivo(m.codigo) ? 'green' : 'default'}>
                    {m.nome}: {moduloAtivo(m.codigo) ? 'ativo' : 'desativado'}
                  </Tag>
                ))}
            </Flex>
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Flex>
  )
}
