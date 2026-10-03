import { useDeferredValue, useState } from 'react'
import { Alert, App, Button, Form, Input, Popconfirm, Tooltip } from 'antd'
import { DeleteOutlined, DisconnectOutlined, EditOutlined, EyeOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
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
import { useTratarErro } from '../data/api/useTratarErro.js'

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
//
// lista (dados da API, hook da área):
//   itens, carregando, atualizando, erro, recarregar()
//   salvar(valores, registro) => Promise   (registro.id presente = edição)
//   excluir(registro) => Promise
//   carregarRegistro?(registro) => Promise<registro completo>  (ficha antes de abrir o painel)
//   paginacao?: { pagina, porPagina, total, mudarPagina(p) }    (paginação no servidor)
//   busca?: { valor, mudar(texto) }                              (busca no servidor; sem ela, filtra a lista carregada)
// mapaErros: { campo_da_api: 'campoDoForm' } para o 422 cair no campo certo quando o nome muda.
// textoExcluir: descrição da confirmação de exclusão.
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
  mapaErros,
  textoExcluir = 'Ele sai das listas, mas continua no histórico de alterações.',
}) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [buscaLocal, setBuscaLocal] = useState('')
  const busca = lista.busca?.valor ?? buscaLocal
  const mudarBusca = lista.busca?.mudar ?? setBuscaLocal
  const termo = useDeferredValue(busca.trim().toLowerCase())
  const painel = usePainel()
  const { registro: editando } = painel
  const [form] = Form.useForm()
  const [salvando, setSalvando] = useState(false)
  const [abrindoId, setAbrindoId] = useState(null)
  const [excluindoId, setExcluindoId] = useState(null)

  const naoEncontrado = () => {
    painel.fechar()
    lista.recarregar?.()
  }

  // Edição de registro com ficha própria (vínculos, campos que a lista não traz): busca antes de abrir
  const abrir = async (registro) => {
    if (!registro?.id || !lista.carregarRegistro) return painel.abrir(registro)
    setAbrindoId(registro.id)
    try {
      painel.abrir(await lista.carregarRegistro(registro))
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: () => lista.recarregar?.() })
    } finally {
      setAbrindoId(null)
    }
  }

  const salvar = async (valores) => {
    const erro = validar?.(valores, editando)
    if (erro) {
      message.error(erro)
      return
    }
    setSalvando(true)
    try {
      await lista.salvar(valores, editando)
      message.success(textoSalvo)
      painel.fechar()
    } catch (e) {
      tratarErro(e, { form, mapa: mapaErros, aoNaoEncontrado: naoEncontrado })
    } finally {
      setSalvando(false)
    }
  }

  const excluir = async (registro) => {
    setExcluindoId(registro.id)
    try {
      await lista.excluir(registro)
      message.success(`${capitalizar(item)} excluído.`)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: () => lista.recarregar?.() })
    } finally {
      setExcluindoId(null)
    }
  }

  const itens = lista.itens ?? []
  const textoBusca = typeof campoBusca === 'function' ? campoBusca : (i) => i[campoBusca]
  const dados = lista.busca ? itens : itens.filter((i) => String(textoBusca(i) ?? '').toLowerCase().includes(termo))
  const paginacao = lista.paginacao && {
    current: lista.paginacao.pagina,
    pageSize: lista.paginacao.porPagina,
    total: lista.paginacao.total,
    onChange: lista.paginacao.mudarPagina,
    showSizeChanger: false,
    hideOnSinglePage: true,
  }

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
            loading={abrindoId === registro.id}
            aria-label={somenteLeitura ? 'Ver' : 'Editar'}
            onClick={() => abrir(registro)}
          />
        </Tooltip>
        {permitirExcluir && !somenteLeitura && (
          <Popconfirm
            title={`Excluir este ${item}?`}
            description={textoExcluir}
            okText="Excluir"
            okButtonProps={{ danger: true }}
            cancelText="Cancelar"
            onConfirm={() => excluir(registro)}
          >
            <Tooltip title="Excluir">
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={excluindoId === registro.id}
                aria-label="Excluir"
              />
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

  const vazio = lista.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar a lista"
      descricao={lista.erro.mensagem}
      acao={lista.recarregar && <Button onClick={lista.recarregar}>Tentar de novo</Button>}
    />
  ) : termo ? (
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
            onChange={(e) => mudarBusca(e.target.value)}
          />
        </BarraFiltros>
        {/* Recarga falhou com linhas na tela: elas ficam, com o aviso de que podem estar desatualizadas */}
        {lista.erro && dados.length > 0 && (
          <Alert
            type="warning"
            showIcon
            className="alerta-lista"
            title={`Não foi possível atualizar a lista: ${lista.erro.mensagem}`}
            action={
              lista.recarregar && (
                <Button size="small" onClick={lista.recarregar}>
                  Tentar de novo
                </Button>
              )
            }
          />
        )}
        <Tabela
          columns={[...colunas, colunaAcoes]}
          dataSource={dados}
          loading={!!(lista.carregando || lista.atualizando)}
          {...(paginacao && { pagination: paginacao })}
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
        salvando={salvando}
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
