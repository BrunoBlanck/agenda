import { App, Button, Tooltip } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import './acesso-site.css'

// Código de confirmação do site em dois grupos de três ("482 913"), como a recepção lê ao telefone.
// Copiar leva só os dígitos, para colar no WhatsApp. destaque: marca-texto (o que pede atenção agora).
export default function CodigoConfirmacao({ codigo, destaque = false }) {
  const { message } = App.useApp()

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(codigo)
      message.success('Código copiado.')
    } catch {
      message.error('Não foi possível copiar. Leia o código para o cliente.')
    }
  }

  return (
    <span className="codigo-confirmacao">
      <span className={destaque ? 'codigo-confirmacao-digitos destaque' : 'codigo-confirmacao-digitos'}>
        <span>{codigo.slice(0, 3)}</span>
        <span>{codigo.slice(3)}</span>
      </span>
      <Tooltip title="Copiar código">
        <Button type="text" size="small" icon={<CopyOutlined />} aria-label={`Copiar código ${codigo}`} onClick={copiar} />
      </Tooltip>
    </span>
  )
}
