import { useDeferredValue, useState } from 'react'
import { App, Button, Form, Input, Popconfirm, Tooltip } from 'antd'
import { DeleteOutlined, EditOutlined, EyeOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import Pagina from './base/Pagina.jsx'
import Secao from './base/Secao.jsx'
import BarraFiltros from './base/BarraFiltros.jsx'
import Tabela from './base/Tabela.jsx'
import EstadoVazio from './base/EstadoVazio.jsx'
import Etiqueta from './base/Etiqueta.jsx'
import PainelFormulario from './base/PainelFormulario.jsx'
import { usePainel } from './base/usePainel.js'
import UltimaAlteracao from './UltimaAlteracao.jsx'
import { capitalizar } from '../utils/formatos.js'

// Tela de cadastro completa: cabeçalho, busca, tabela e formulário no painel lateral.
// titulo: nome da tela (plural). item: nome de um registro, em minúsculas ("cliente"), usado nos textos.
// somenteLeitura: perfil com nível "leitura" (vê os registros, sem criar, editar ou excluir).
// validar(valores, item): regra extra antes de salvar; retorna a mensagem de erro ou nada.
// campoBusca: campo (ou função que recebe o item) usado na busca.
// larguraTabela: largura mínima da tabela quando há textos longos (eles quebram linha em vez de esticar a coluna).
// antes: conteúdo entre o cabeçalho e a lista (ex.: um aviso ou uma configuração da tela).
// valoresNovo: valores iniciais de um registro novo (na edição o formulário abre com o próprio registro).
// nomeRegistro(item): nome no cabeçalho do painel na edição (padrão: item.nome).
// iconeRegistro(item) e corRegistro(item): marca do registro no cabeçalho no lugar das iniciais
// (ex.: ícone do tipo de local, cor do profissional na agenda).
// acoesEdicao(item, fechar): ações no cabeçalho do painel (ex.: atalho para o histórico).
// destaqueId: outra linha a destacar, aberta pela própria tela (ex.: histórico do cliente).
// larguraPainel: só quando os campos pedirem mais que os 480 px padrão.
export default function CadastroTabela({
  titulo,
  descricao,
  item,
  textoNovo = `Novo ${item}`,
  textoSalvo = `${capitalizar(item)} salvo.`,
  lista,
  colunas,
  campos,
  campoBusca = 'nome',
  placeholderBusca = 'Buscar por nome',
  somenteLeitura = false,
  permitirExcluir = true,
  validar,
  expandable,
  larguraPainel,
  larguraTabela,
  antes,
  valoresNovo,
  nomeRegistro = (r) => r.nome,
  iconeRegistro,
  corRegistro,
  acoesEdicao,
  destaqueId,
}) {
  const { message } = App.useApp()
  const [busca, setBusca] = useState('')
  const termo = useDeferredValue(busca.trim().toLowerCase())
  const painel = usePainel()
  const { registro: editando, abrir } = painel
  const [form] = Form.useForm()

  const salvar = (valores) => {
    const erro = validar?.(valores, editando)
    if (erro) {
      message.error(erro)
      return
    }
    if (editando.id) lista.atualizar(editando.id, valores)
    else lista.adicionar(valores)
    message.success(textoSalvo)
    painel.fechar()
  }

  const textoBusca = typeof campoBusca === 'function' ? campoBusca : (i) => i[campoBusca]
  const dados = lista.itens.filter((i) => String(textoBusca(i) ?? '').toLowerCase().includes(termo))

  const colunaAcoes = {
    title: <span className="sr-only">Ações</span>,
    key: 'acoes',
    width: 96,
    align: 'right',
    fixed: 'right',
    render: (_, registro) => (
      <span className="acoes-linha">
        <Tooltip title={somenteLeitura ? 'Ver' : 'Editar'}>
          <Button
            type="text"
            size="small"
            icon={somenteLeitura ? <EyeOutlined /> : <EditOutlined />}
            aria-label={somenteLeitura ? 'Ver' : 'Editar'}
            onClick={() => abrir(registro)}
          />
        </Tooltip>
        {permitirExcluir && !somenteLeitura && (
          <Popconfirm
            title={`Excluir este ${item}?`}
            description="Ele sai das listas, mas continua no histórico de alterações."
            okText="Excluir"
            okButtonProps={{ danger: true }}
            cancelText="Cancelar"
            onConfirm={() => {
              lista.remover(registro.id)
              message.success(`${capitalizar(item)} excluído.`)
            }}
          >
            <Tooltip title="Excluir">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label="Excluir" />
            </Tooltip>
          </Popconfirm>
        )}
      </span>
    ),
  }

  const botaoNovo = (
    <Button type="primary" icon={<PlusOutlined />} onClick={() => abrir({})}>
      {textoNovo}
    </Button>
  )

  const vazio = termo ? (
    <EstadoVazio compacto titulo={`Nada encontrado para "${busca.trim()}"`} descricao="Confira a grafia ou busque por outra parte do nome." />
  ) : (
    <EstadoVazio
      titulo={`Nenhum ${item} cadastrado`}
      acao={!somenteLeitura && <Button onClick={() => abrir({})}>{textoNovo}</Button>}
    />
  )

  return (
    <Pagina
      titulo={titulo}
      descricao={descricao}
      acoes={
        somenteLeitura ? (
          <Etiqueta icone={<EyeOutlined />} title="Seu perfil permite consultar, mas não alterar">
            Somente leitura
          </Etiqueta>
        ) : (
          botaoNovo
        )
      }
    >
      {antes}
      <Secao rente>
        <BarraFiltros>
          <Input
            className="busca"
            prefix={<SearchOutlined />}
            placeholder={placeholderBusca}
            aria-label={placeholderBusca}
            allowClear
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </BarraFiltros>
        <Tabela
          columns={[...colunas, colunaAcoes]}
          dataSource={dados}
          expandable={expandable}
          vazio={vazio}
          destaqueId={painel.destaqueId ?? destaqueId}
          {...(larguraTabela && { scroll: { x: larguraTabela } })}
        />
      </Secao>
      <PainelFormulario
        titulo={somenteLeitura ? capitalizar(item) : editando?.id ? `Editar ${item}` : textoNovo}
        {...(editando?.id && {
          nome: nomeRegistro(editando),
          icone: iconeRegistro?.(editando),
          cor: corRegistro?.(editando),
          extra: acoesEdicao && ((fechar) => acoesEdicao(editando, fechar)),
        })}
        open={painel.aberto}
        form={form}
        valoresIniciais={editando?.id ? editando : valoresNovo}
        somenteLeitura={somenteLeitura}
        largura={larguraPainel}
        onCancelar={painel.fechar}
        onSalvar={salvar}
        rodape={<UltimaAlteracao item={editando} />}
      >
        {campos}
      </PainelFormulario>
    </Pagina>
  )
}
