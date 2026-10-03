import { Checkbox, Flex, Tooltip } from 'antd'
import { ShopOutlined, WhatsAppOutlined, GlobalOutlined } from '@ant-design/icons'
import { canaisCliente } from '../data/dominio.js'

const icones = { loja: <ShopOutlined />, whatsapp: <WhatsAppOutlined />, site: <GlobalOutlined /> }

// Ícones dos canais em que o cliente está conectado; os não usados ficam apagados
export function IconesCanais({ canais }) {
  const lista = Array.isArray(canais) ? canais : []
  const conectados = Object.entries(canaisCliente).filter(([codigo]) => lista.includes(codigo))
  return (
    <span className="canais" role="img" aria-label={`Canais: ${conectados.map(([, nome]) => nome).join(', ') || 'nenhum'}`}>
      {Object.entries(canaisCliente).map(([codigo, nome]) => {
        const ativo = lista.includes(codigo)
        return (
          <Tooltip key={codigo} title={ativo ? nome : `${nome}: não conectado`}>
            <span className={ativo ? `canal-${codigo}` : undefined}>{icones[codigo]}</span>
          </Tooltip>
        )
      })}
    </span>
  )
}

// Campo do formulário: marca um ou mais canais
export function SeletorCanais(props) {
  return (
    <Checkbox.Group
      {...props}
      options={Object.entries(canaisCliente).map(([value, nome]) => ({
        value,
        label: (
          <Flex gap={6} align="center">
            <span className={`canal-${value}`}>{icones[value]}</span>
            {nome}
          </Flex>
        ),
      }))}
    />
  )
}
