import { Form, Input } from 'antd'
import { PADRAO_SLUG, slugValido } from '../utils/formatos.js'
import { caminhoPainel, caminhoSite } from '../layout/caminhos.js'

// O mesmo endereço serve ao site (/slug) e ao painel (/slug/painel); a ajuda mostra os dois com o valor digitado
function AjudaEndereco() {
  const form = Form.useFormInstance()
  const slug = Form.useWatch('slug', form)
  const exemplo = slugValido(slug) ? slug : 'nome-da-loja'
  return (
    <span>
      Site em <span className="endereco">{caminhoSite(exemplo)}</span> e painel em{' '}
      <span className="endereco">{caminhoPainel(exemplo)}</span>.
    </span>
  )
}

// Campo slug da loja (criar e editar). Slug reservado (PLA-16) volta como 422 da API e aparece aqui pelo tratamento de erros[].
export default function CampoEnderecoLoja() {
  return (
    <Form.Item
      name="slug"
      label="Endereço da loja"
      extra={<AjudaEndereco />}
      rules={[
        { required: true, message: 'Informe o endereço' },
        { pattern: PADRAO_SLUG, message: 'Use letras minúsculas, números e hífens (ex.: clinica-sorriso)' },
        { min: 2, max: 60, message: 'Use de 2 a 60 caracteres' },
      ]}
    >
      <Input prefix="/" maxLength={60} autoCapitalize="none" spellCheck={false} />
    </Form.Item>
  )
}
