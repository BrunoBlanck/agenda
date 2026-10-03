import { App, Col, Form, Input, Row } from 'antd'
import { cnpjValido, mascaraCep, mascaraCnpj, mascaraTelefone } from '../utils/formatos.js'
import { buscarEndereco } from '../utils/cep.js'

const validarCnpj = (_, v) => (!v || cnpjValido(v) ? Promise.resolve() : Promise.reject(new Error('CNPJ inválido. Confira os números')))

// Nome, razão social, CNPJ e contato da loja (usado na própria loja e no SUPERADMIN)
export function CamposEmpresa() {
  return (
    <Row gutter={16}>
      <Col xs={24} md={12}>
        <Form.Item name="nomeFantasia" label="Nome da loja" rules={[{ required: true, whitespace: true, message: 'Informe o nome da loja' }]}>
          <Input maxLength={150} />
        </Form.Item>
      </Col>
      <Col xs={24} md={12}>
        <Form.Item name="nome" label="Razão social" rules={[{ required: true, whitespace: true, message: 'Informe a razão social' }]}>
          <Input maxLength={150} />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="cnpj" label="CNPJ" normalize={mascaraCnpj} validateTrigger="onBlur" rules={[{ validator: validarCnpj }]}>
          <Input inputMode="numeric" placeholder="Opcional" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="telefone" label="Telefone" normalize={mascaraTelefone}>
          <Input inputMode="tel" />
        </Form.Item>
      </Col>
      <Col xs={24} md={8}>
        <Form.Item name="email" label="E-mail" validateTrigger="onBlur" rules={[{ type: 'email', message: 'E-mail inválido. Confira o @ e o domínio' }]}>
          <Input type="email" maxLength={254} />
        </Form.Item>
      </Col>
    </Row>
  )
}

// Endereço com preenchimento pelo CEP. somenteLeitura: sem a dica do CEP (o campo não pode ser editado)
export function CamposEndereco({ somenteLeitura = false } = {}) {
  const form = Form.useFormInstance()
  const { message } = App.useApp()

  const preencher = async () => {
    try {
      const endereco = await buscarEndereco(form.getFieldValue('cep'))
      if (endereco) form.setFieldsValue(endereco)
      else if (form.getFieldValue('cep')?.length === 9) message.warning('CEP não encontrado. Preencha o endereço manualmente.')
    } catch {
      // Sem conexão: o endereço é preenchido manualmente
    }
  }

  return (
    <Row gutter={16}>
      <Col xs={24} sm={8} md={6}>
        <Form.Item name="cep" label="CEP" normalize={mascaraCep} extra={somenteLeitura ? undefined : 'Preenche o endereço'}>
          <Input inputMode="numeric" onBlur={preencher} />
        </Form.Item>
      </Col>
      <Col xs={24} sm={16} md={13}>
        <Form.Item name="logradouro" label="Logradouro">
          <Input maxLength={150} />
        </Form.Item>
      </Col>
      <Col xs={8} md={5}>
        <Form.Item name="numero" label="Número">
          <Input maxLength={10} />
        </Form.Item>
      </Col>
      <Col xs={16} md={8}>
        <Form.Item name="complemento" label="Complemento">
          <Input maxLength={80} />
        </Form.Item>
      </Col>
      <Col xs={24} md={6}>
        <Form.Item name="bairro" label="Bairro">
          <Input maxLength={80} />
        </Form.Item>
      </Col>
      <Col xs={16} md={7}>
        <Form.Item name="cidade" label="Cidade">
          <Input maxLength={80} />
        </Form.Item>
      </Col>
      <Col xs={8} md={3}>
        <Form.Item name="uf" label="UF" normalize={(v) => v?.toUpperCase().slice(0, 2)}>
          <Input />
        </Form.Item>
      </Col>
    </Row>
  )
}
