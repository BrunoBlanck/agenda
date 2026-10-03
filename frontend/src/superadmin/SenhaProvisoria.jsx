import { Alert, App, Button } from 'antd'
import { CopyOutlined } from '@ant-design/icons'

// Senha provisória gerada pela API (criar loja, funcionário ou usuário admin, ou redefinir senha).
// Ela vem uma única vez na resposta: fica à vista, com botão de copiar, até o superadmin fechar o aviso.
// Ainda não há envio de e-mail: quem vê a senha repassa ao usuário.
export default function SenhaProvisoria({ nome, email, senha, aoFechar }) {
  const { message } = App.useApp()
  if (!senha) return null

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(senha)
      message.success('Senha copiada.')
    } catch {
      message.warning('Não foi possível copiar. Selecione a senha e copie manualmente.')
    }
  }

  return (
    <Alert
      type="warning"
      showIcon
      closable
      onClose={aoFechar}
      title={`Senha provisória de ${nome || email || 'acesso'}`}
      description={
        <div className="pilha">
          <span className="com-ponto">
            <code>{senha}</code>
            <Button size="small" icon={<CopyOutlined />} onClick={copiar}>
              Copiar
            </Button>
          </span>
          <span>
            Repasse agora{email ? ` para ${email}` : ''}: esta senha não aparece de novo. Se ela se perder, redefina a
            senha outra vez.
          </span>
        </div>
      }
    />
  )
}
