import { Checkbox, Flex, Tooltip } from 'antd'
import { ShopOutlined, WhatsAppOutlined, GlobalOutlined } from '@ant-design/icons'
import { canaisCliente } from '../data/mock.js'

const icones = {
  loja: { icone: <ShopOutlined />, cor: '#0f766e' },
  whatsapp: { icone: <WhatsAppOutlined />, cor: '#25d366' },
  site: { icone: <GlobalOutlined />, cor: '#2563eb' },
}

// Ícones dos canais em que o cliente está conectado; os não usados ficam apagados
export function IconesCanais({ canais = [] }) {
  return (
    <Flex gap={10} style={{ fontSize: 18 }}>
      {Object.entries(canaisCliente).map(([codigo, nome]) => {
        const ativo = canais.includes(codigo)
        return (
          <Tooltip key={codigo} title={ativo ? nome : `${nome}: não conectado`}>
            <span style={{ color: ativo ? icones[codigo].cor : '#d9d9d9' }}>{icones[codigo].icone}</span>
          </Tooltip>
        )
      })}
    </Flex>
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
            <span style={{ color: icones[value].cor }}>{icones[value].icone}</span>
            {nome}
          </Flex>
        ),
      }))}
    />
  )
}
