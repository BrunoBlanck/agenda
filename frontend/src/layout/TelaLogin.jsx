import { useState } from 'react'
import { Alert, Button, Form, Input } from 'antd'
import { useTratarErro } from '../data/api/useTratarErro.js'
import MarcaPlataforma from '../superadmin/MarcaPlataforma.jsx'
import './login.css'

// Login das duas áreas: folha de agenda sobre o papel, com a marca e o nome da área no topo.
// campos: Form.Items extras antes do e-mail (ex.: endereço da loja). aoEntrar(valores) => Promise.
// motivo: por que voltou ao login (sessão expirou, loja suspensa).
export default function TelaLogin({ area, titulo, descricao, campos, valoresIniciais, motivo, aoEntrar, rodape }) {
  const [form] = Form.useForm()
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const tratarErro = useTratarErro()

  const enviar = async (valores) => {
    setEnviando(true)
    setErro(null)
    try {
      await aoEntrar(valores)
    } catch (e) {
      // 401/403/429 ficam escritos no formulário (não somem como um aviso); o resto segue o padrão
      if ([401, 403, 429].includes(e?.status)) setErro(e.mensagem)
      else tratarErro(e, { form })
      form.setFieldValue('senha', '')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="login">
      <section className="login-folha" aria-labelledby="login-titulo">
        <header className="login-cabecalho">
          <MarcaPlataforma tamanho={40} />
          <div>
            <span className="login-area">{area}</span>
            <h1 id="login-titulo">{titulo}</h1>
          </div>
        </header>
        {descricao && <p className="login-descricao">{descricao}</p>}

        {(erro || motivo) && (
          <Alert type={erro ? 'error' : 'warning'} showIcon title={erro ?? motivo} className="login-alerta" role="alert" />
        )}

        <Form form={form} layout="vertical" requiredMark={false} initialValues={valoresIniciais} onFinish={enviar} disabled={enviando}>
          {campos}
          <Form.Item
            name="email"
            label="E-mail"
            rules={[
              { required: true, message: 'Informe o e-mail' },
              { type: 'email', message: 'E-mail inválido. Confira o @ e o domínio' },
            ]}
          >
            <Input type="email" autoComplete="username" inputMode="email" />
          </Form.Item>
          <Form.Item name="senha" label="Senha" rules={[{ required: true, message: 'Informe a senha' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={enviando} className="login-entrar">
            Entrar
          </Button>
        </Form>
        {rodape && <footer className="login-rodape">{rodape}</footer>}
      </section>
    </main>
  )
}
