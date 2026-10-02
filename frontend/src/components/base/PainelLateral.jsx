import { Avatar, Drawer } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

// Pronomes de tratamento não entram nas iniciais ("Dr. Carlos Lima" = CL)
const TRATAMENTOS = /^(dra?|profa?|sra?)\.?$/i

const iniciais = (nome = '') => {
  const partes = nome.trim().split(/\s+/).filter((p) => !TRATAMENTOS.test(p))
  return `${partes[0]?.[0] ?? ''}${partes.length > 1 ? partes.at(-1)[0] : ''}`.toUpperCase()
}

// Marca do registro no cabeçalho: iniciais (pessoa), ícone (serviço, local...) ou tracejado (registro novo).
// cor: cor própria do registro (ex.: a cor do profissional na agenda), mostrada como um anel.
function MarcaRegistro({ nome, icone, cor }) {
  if (!nome) return <Avatar size={40} className="painel-lateral-marca novo" icon={<PlusOutlined />} />
  return (
    <Avatar
      size={40}
      className={cor ? 'painel-lateral-marca com-cor' : 'painel-lateral-marca'}
      style={cor ? { '--cor-registro': cor } : undefined}
      icon={icone}
    >
      {!icone && iniciais(nome)}
    </Avatar>
  )
}

// Painel lateral padrão (à direita, altura toda): base de todo formulário e consulta que abre por cima
// de uma tela. Cabeçalho com a ação (titulo) e o registro (nome); X à direita; no celular ocupa a tela.
// semNome: texto no lugar do nome quando o registro ainda não existe.
// extra: ações no cabeçalho. rodape: conteúdo fixo embaixo. rootClassName soma classes ao padrão.
export default function PainelLateral({
  titulo,
  nome,
  semNome,
  icone,
  cor,
  open,
  onClose,
  largura = 480,
  extra,
  rodape,
  rootClassName,
  children,
  ...propsDrawer
}) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      size={largura}
      destroyOnHidden
      closable={{ placement: 'end' }}
      rootClassName={['painel-lateral', rootClassName].filter(Boolean).join(' ')}
      title={
        <div className="painel-lateral-titulo">
          <MarcaRegistro nome={nome} icone={icone} cor={cor} />
          <div className="painel-lateral-textos">
            <span className="painel-lateral-acao">{titulo}</span>
            <span className="painel-lateral-nome">{nome || semNome}</span>
          </div>
        </div>
      }
      extra={extra}
      footer={rodape}
      {...propsDrawer}
    >
      {children}
    </Drawer>
  )
}
