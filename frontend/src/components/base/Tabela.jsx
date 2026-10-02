import { Table } from 'antd'
import EstadoVazio from './EstadoVazio.jsx'

const paginacaoPadrao = { pageSize: 20, hideOnSinglePage: true, showSizeChanger: false }

// Table com os padrões do sistema: chave pelo id, rolagem horizontal em telas estreitas,
// paginação só quando precisa e estado vazio com texto (vazio = nó ou texto).
// Tabelas com textos longos passam scroll={{ x: <largura mínima> }} para o texto quebrar linha.
// destaqueId: linha aberta num painel lateral (fica marcada enquanto ele está aberto).
export default function Tabela({ vazio = 'Nenhum registro', pagination = paginacaoPadrao, destaqueId, rowClassName, ...props }) {
  return (
    <Table
      rowKey="id"
      scroll={{ x: 'max-content' }}
      pagination={pagination}
      locale={{ emptyText: typeof vazio === 'string' ? <EstadoVazio titulo={vazio} compacto /> : vazio }}
      rowClassName={(registro, i) =>
        [destaqueId != null && registro.id === destaqueId && 'linha-em-edicao', rowClassName?.(registro, i)].filter(Boolean).join(' ')
      }
      {...props}
    />
  )
}
