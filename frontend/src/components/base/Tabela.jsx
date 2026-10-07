import { Table } from 'antd'
import EstadoVazio from './EstadoVazio.jsx'
import TabelaCartoes from './TabelaCartoes.jsx'
import { useTelaEstreita } from './useTelaEstreita.js'

const paginacaoPadrao = { pageSize: 20, hideOnSinglePage: true, showSizeChanger: false }

// Table com os padrões do sistema: chave pelo id, rolagem horizontal em telas estreitas,
// paginação só quando precisa e estado vazio com texto (vazio = nó ou texto).
// Tabelas com textos longos passam scroll={{ x: <largura mínima> }} para o texto quebrar linha.
// destaqueId: linha aberta num painel lateral (fica marcada enquanto ele está aberto).
//
// No celular (abaixo de 768 px) a mesma tabela vira cartões empilhados (TabelaCartoes, DIR-004).
// Cada coluna escolhe o seu lugar no cartão com a prop `cartao`:
//   'titulo'    título do cartão (padrão: a primeira coluna)
//   'subtitulo' linha logo abaixo do título (ex.: data e horário)
//   'etiqueta'  canto direito do título (ex.: situação)
//   'bloco'     rótulo em cima e valor na largura toda (texto longo, campo, botões segmentados)
//   'acoes'     rodapé com as ações (padrão para key: 'acoes'; 'rodape' é sinônimo)
//   false       não aparece no cartão
//   (nada)      par rótulo/valor, com o title da coluna como rótulo
// soNoCartao: true na coluna = ela só existe no cartão (ex.: o que no desktop fica numa dica ao passar o mouse).
// expandable.rotuloCartao: texto do botão que abre o conteúdo expandido no cartão (texto ou função do registro).
export default function Tabela({ vazio = 'Nenhum registro', pagination = paginacaoPadrao, destaqueId, rowClassName, ...props }) {
  const estreita = useTelaEstreita()
  const vazioNo = typeof vazio === 'string' ? <EstadoVazio titulo={vazio} compacto /> : vazio
  const classeLinha = (registro, i) =>
    [destaqueId != null && registro.id === destaqueId && 'linha-em-edicao', rowClassName?.(registro, i)].filter(Boolean).join(' ')

  if (estreita) return <TabelaCartoes pagination={pagination} vazio={vazioNo} rowClassName={classeLinha} {...props} />

  // rotuloCartao é só do modo cartão: não vai para o Table do antd
  const { expandable, columns, ...resto } = props
  const expansao = expandable && Object.fromEntries(Object.entries(expandable).filter(([chave]) => chave !== 'rotuloCartao'))

  return (
    <Table
      rowKey="id"
      scroll={{ x: 'max-content' }}
      pagination={pagination}
      locale={{ emptyText: vazioNo }}
      rowClassName={classeLinha}
      {...resto}
      columns={columns?.filter((c) => c && !c.soNoCartao)}
      {...(expansao && { expandable: expansao })}
    />
  )
}
