import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, App, Avatar, Button, Col, DatePicker, Form, Input, Popconfirm, Row, Select, Skeleton, Switch, Tabs, Tooltip } from 'antd'
import { DeleteOutlined, DesktopOutlined, DisconnectOutlined, EditOutlined, GlobalOutlined, KeyOutlined, LockOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { opcoesTipoLoja, tiposLoja } from '../../data/dominio.js'
import { agoraNaLoja, lerDataHora } from '../../data/api/conversao.js'
import { useTratarErro } from '../../data/api/useTratarErro.js'
import { mascaraTelefone } from '../../utils/formatos.js'
import UltimaAlteracao from '../../components/UltimaAlteracao.jsx'
import EnvioLogo from '../../components/EnvioLogo.jsx'
import { CamposEmpresa, CamposEndereco } from '../../components/CamposLoja.jsx'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import BarraFiltros from '../../components/base/BarraFiltros.jsx'
import Tabela from '../../components/base/Tabela.jsx'
import Etiqueta from '../../components/base/Etiqueta.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import PainelFormulario from '../../components/base/PainelFormulario.jsx'
import { usePainel } from '../../components/base/usePainel.js'
import { EtiquetaLoja, EtiquetaSituacao } from '../../components/Etiquetas.jsx'
import { useFuncionariosLoja, useLoja, useModulosLoja, usePerfisLoja, usePlanos, useSenhaDaLojaNova } from '../usePlataforma.js'
import { erroNoCampo } from '../erroNoCampo.js'
import CampoEnderecoLoja from '../CampoEnderecoLoja.jsx'
import { caminhoPainel, caminhoSite } from '../../layout/caminhos.js'
import HistoricoAlteracoes from '../HistoricoAlteracoes.jsx'
import SenhaProvisoria from '../SenhaProvisoria.jsx'

const FUSOS = ['America/Sao_Paulo', 'America/Manaus', 'America/Cuiaba', 'America/Rio_Branco', 'America/Noronha']

// 409 de unicidade que tem campo certo no formulário
const CONFLITOS_LOJA = [
  { trecho: 'endereço de acesso', campo: 'slug' },
  { trecho: 'CNPJ', campo: 'cnpj' },
]
const CONFLITOS_FUNCIONARIO = [{ trecho: 'e-mail', campo: 'email' }]

function ErroCarregar({ titulo, erro, recarregar }) {
  return (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo={titulo}
      descricao={erro?.mensagem}
      acao={recarregar && <Button onClick={recarregar}>Tentar de novo</Button>}
    />
  )
}

function DadosGerais({ loja, salvar, enviarLogo, removerLogo, aoNaoEncontrado }) {
  const planos = usePlanos()
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [salvando, setSalvando] = useState(false)

  const enviar = async (valores) => {
    setSalvando(true)
    try {
      const salva = await salvar(valores)
      form.setFieldsValue(salva) // o servidor normaliza (CNPJ, telefone, UF)
      message.success('Dados da loja salvos.')
    } catch (e) {
      if (!erroNoCampo(e, form, CONFLITOS_LOJA)) tratarErro(e, { form, aoNaoEncontrado })
    } finally {
      setSalvando(false)
    }
  }

  // Plano inativo não pode ser escolhido, mas o atual da loja continua valendo
  const opcoesPlano = planos.itens.map((p) => ({ value: p.id, label: p.nome, disabled: !p.ativo && p.id !== loja.planoId }))
  if (loja.planoId && !planos.itens.some((p) => p.id === loja.planoId)) {
    opcoesPlano.push({ value: loja.planoId, label: loja.planoNome ?? 'Plano atual' })
  }
  const fusos = FUSOS.includes(loja.fusoHorario) || !loja.fusoHorario ? FUSOS : [loja.fusoHorario, ...FUSOS]

  return (
    <>
      <div className="bloco-logo">
        <h3 className="grupo-formulario">Logo</h3>
        <p className="texto-ajuda grupo-formulario-ajuda">Aparece no menu do painel e no site da loja.</p>
        <EnvioLogo
          logoUrl={loja.logoUrl}
          nome={loja.nomeFantasia}
          podeAlterar
          enviar={enviarLogo}
          remover={removerLogo}
          aoNaoEncontrado={aoNaoEncontrado}
        />
      </div>
      <Form form={form} name="dadosLoja" layout="vertical" initialValues={loja} onFinish={enviar} disabled={salvando} scrollToFirstError>
        <h3 className="grupo-formulario">Plataforma</h3>
        <Row gutter={16}>
          <Col xs={24} sm={12} lg={8}>
            <Form.Item name="tipo" label="Tipo" rules={[{ required: true, message: 'Escolha o tipo' }]} extra="Define o site do consumidor.">
              <Select options={opcoesTipoLoja} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <Form.Item name="planoId" label="Plano" rules={[{ required: true, message: 'Escolha o plano' }]} extra="Só o valor cobrado. Não muda os módulos.">
              <Select loading={planos.carregando} options={opcoesPlano} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <CampoEnderecoLoja />
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <Form.Item name="fusoHorario" label="Fuso horário" rules={[{ required: true, message: 'Escolha o fuso' }]}>
              <Select options={fusos.map((f) => ({ value: f, label: f }))} />
            </Form.Item>
          </Col>
        </Row>

        <h3 className="grupo-formulario">Dados da loja</h3>
        <p className="texto-ajuda grupo-formulario-ajuda">A própria loja também pode editar estes dados em Configurações.</p>
        <CamposEmpresa />
        <CamposEndereco />

        <div className="rodape-formulario">
          <UltimaAlteracao item={loja} />
          <Button type="primary" htmlType="submit" loading={salvando} disabled={false}>
            Salvar dados
          </Button>
        </div>
      </Form>
    </>
  )
}

function Modulos({ lojaId }) {
  const { itens, carregando, erro, recarregar, definir } = useModulosLoja(lojaId)
  const tratarErro = useTratarErro()
  const [pendente, setPendente] = useState({}) // { codigo: campo em envio }
  const [versao, setVersao] = useState(0) // recria as observações depois de um erro (volta ao valor salvo)

  const alterar = async (m, campos) => {
    setPendente((p) => ({ ...p, [m.codigo]: Object.keys(campos)[0] }))
    try {
      await definir(m.codigo, campos)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: recarregar })
      setVersao((v) => v + 1)
    } finally {
      setPendente((atual) => {
        const resto = { ...atual }
        delete resto[m.codigo]
        return resto
      })
    }
  }

  if (carregando) return <Skeleton active paragraph={{ rows: 6 }} />
  if (erro && !itens.length) return <ErroCarregar titulo="Não foi possível carregar os módulos" erro={erro} recarregar={recarregar} />

  const colunas = [
    {
      title: 'Módulo',
      key: 'nome',
      render: (_, m) => (
        <span className="recurso">
          <strong>{m.nome}</strong>
          {m.opcional && m.atualizadoEm && <UltimaAlteracao item={m} />}
        </span>
      ),
    },
    {
      title: 'Situação',
      key: 'situacao',
      width: 170,
      render: (_, m) =>
        m.opcional ? (
          <span className="recurso">
            <Switch
              checked={m.habilitado}
              loading={pendente[m.codigo] === 'habilitado'}
              disabled={!!pendente[m.codigo]}
              checkedChildren="Ligado"
              unCheckedChildren="Desligado"
              aria-label={`Ligar ou desligar ${m.nome}`}
              onChange={(habilitado) => alterar(m, { habilitado })}
            />
            {m.habilitado && !m.ativo && <span className="texto-apoio">Prazo vencido: sem efeito</span>}
          </span>
        ) : (
          <Etiqueta tom="contorno" icone={<LockOutlined />}>
            Sempre ligado
          </Etiqueta>
        ),
    },
    {
      title: 'Observação',
      key: 'observacao',
      render: (_, m) =>
        m.opcional && (
          <Input
            key={`${m.codigo}-${m.observacao ?? ''}-${versao}`}
            defaultValue={m.observacao ?? ''}
            maxLength={500}
            disabled={pendente[m.codigo] === 'observacao'}
            placeholder='Ex.: "cortesia até dez/2026"'
            aria-label={`Observação sobre ${m.nome}`}
            onBlur={(e) => e.target.value.trim() !== (m.observacao ?? '') && alterar(m, { observacao: e.target.value })}
          />
        ),
    },
    {
      title: 'Expira em',
      key: 'expira',
      width: 170,
      render: (_, m) =>
        m.opcional && (
          <DatePicker
            format="DD/MM/YYYY"
            placeholder="Sem prazo"
            aria-label={`Prazo de ${m.nome}`}
            disabled={pendente[m.codigo] === 'expiraEm'}
            value={lerDataHora(m.expiraEm)}
            // Prazo no passado desligaria o módulo na hora: para desligar, use o interruptor
            disabledDate={(d) => d.isBefore(agoraNaLoja(), 'day')}
            onChange={(d) => alterar(m, { expiraEm: d ? d.endOf('day') : null })}
          />
        ),
    },
  ]

  return (
    <div className="pilha">
      <p className="texto-ajuda">
        Ligue só o que a loja usa: o que estiver desligado some do menu dela. Não depende do tipo nem do plano. Desligar não
        apaga dados: tudo volta ao religar. O prazo vale até o fim do dia, no horário da loja.
      </p>
      <Tabela rowKey="codigo" size="small" pagination={false} columns={colunas} dataSource={itens} />
    </div>
  )
}

function Funcionarios({ lojaId }) {
  const lista = useFuncionariosLoja(lojaId)
  const { perfis, carregando: carregandoPerfis } = usePerfisLoja(lojaId)
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const painel = usePainel()
  const painelSenha = usePainel()
  const editando = painel.registro
  const [busca, setBusca] = useState('')
  const [form] = Form.useForm()
  const [formSenha] = Form.useForm()
  const [salvando, setSalvando] = useState(false)
  const [senhaGerada, setSenhaGerada] = useState(null)
  const termo = busca.trim().toLowerCase()
  const visiveis = lista.itens.filter((f) => `${f.nome} ${f.email}`.toLowerCase().includes(termo))

  const naoEncontrado = (fechar) => () => {
    fechar()
    lista.recarregar()
  }

  const salvar = async (v) => {
    setSalvando(true)
    try {
      const { funcionario, senhaProvisoria } = await lista.salvar(v, editando)
      message.success('Funcionário salvo.')
      setSenhaGerada(senhaProvisoria ? { nome: funcionario?.nome, email: funcionario?.email, senha: senhaProvisoria } : null)
      painel.fechar()
    } catch (e) {
      if (!erroNoCampo(e, form, CONFLITOS_FUNCIONARIO)) tratarErro(e, { form, aoNaoEncontrado: naoEncontrado(painel.fechar) })
    } finally {
      setSalvando(false)
    }
  }

  const redefinirSenha = async (v) => {
    const f = painelSenha.registro
    setSalvando(true)
    try {
      const { mensagem, senhaProvisoria } = await lista.redefinirSenha(f, v.senha)
      message.success(mensagem)
      setSenhaGerada(senhaProvisoria ? { nome: f.nome, email: f.email, senha: senhaProvisoria } : null)
      painelSenha.fechar()
    } catch (e) {
      tratarErro(e, { form: formSenha, aoNaoEncontrado: naoEncontrado(painelSenha.fechar) })
    } finally {
      setSalvando(false)
    }
  }

  // Perfil excluído ainda aparece no funcionário que o usa
  const opcoesPerfil = perfis.map((p) => ({ value: p.id, label: p.nome }))
  if (editando?.perfilId && !perfis.some((p) => p.id === editando.perfilId)) {
    opcoesPerfil.push({ value: editando.perfilId, label: editando.perfilNome ?? 'Perfil excluído' })
  }
  const perfilAdmin = perfis.find((p) => p.acessoTotal)

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    { title: 'E-mail (login)', dataIndex: 'email' },
    {
      title: 'Perfil',
      key: 'perfil',
      render: (_, f) =>
        f.perfilAcessoTotal ? (
          <Etiqueta tom="tinta" icone={<LockOutlined />}>
            {f.perfilNome ?? 'Administrador'}
          </Etiqueta>
        ) : (
          <Etiqueta tom="contorno">{f.perfilNome ?? '—'}</Etiqueta>
        ),
    },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => <EtiquetaSituacao ativo={a} /> },
    {
      title: 'Criado por',
      dataIndex: 'criadoPor',
      render: (c) => (c === 'superadmin' ? 'Superadmin' : c === 'loja' ? <span className="texto-apoio">Loja</span> : <span className="texto-apoio">—</span>),
    },
    {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      width: 96,
      align: 'right',
      fixed: 'right',
      render: (_, f) => (
        <span className="acoes-linha">
          <Tooltip title="Editar">
            <Button type="text" size="small" icon={<EditOutlined />} aria-label="Editar" onClick={() => painel.abrir(f)} />
          </Tooltip>
          <Tooltip title="Redefinir senha">
            <Button type="text" size="small" icon={<KeyOutlined />} aria-label="Redefinir senha" onClick={() => painelSenha.abrir(f)} />
          </Tooltip>
        </span>
      ),
    },
  ]

  const vazio = lista.erro ? (
    <ErroCarregar titulo="Não foi possível carregar os funcionários" erro={lista.erro} recarregar={lista.recarregar} />
  ) : (
    <EstadoVazio compacto titulo={busca ? 'Ninguém com esse nome ou e-mail' : 'Nenhum funcionário'} />
  )

  return (
    <div className="pilha">
      {senhaGerada && <SenhaProvisoria {...senhaGerada} aoFechar={() => setSenhaGerada(null)} />}
      <BarraFiltros
        acoes={
          <Button icon={<PlusOutlined />} onClick={() => painel.abrir({})}>
            Novo funcionário
          </Button>
        }
      >
        <Input
          className="busca"
          prefix={<SearchOutlined />}
          placeholder="Buscar por nome ou e-mail"
          aria-label="Buscar funcionário"
          allowClear
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </BarraFiltros>
      <Tabela
        size="small"
        columns={colunas}
        dataSource={lista.erro ? [] : visiveis}
        loading={lista.carregando || lista.atualizando}
        destaqueId={painel.destaqueId ?? painelSenha.destaqueId}
        vazio={vazio}
      />
      <p className="texto-ajuda">O superadmin pode criar funcionários com qualquer perfil, inclusive Administrador.</p>
      <PainelFormulario
        titulo={editando?.id ? 'Editar funcionário' : 'Novo funcionário'}
        nome={editando?.nome}
        open={painel.aberto}
        form={form}
        name="funcionario"
        valoresIniciais={editando?.id ? editando : { perfilId: perfilAdmin?.id, ativo: true }}
        salvando={salvando}
        onCancelar={painel.fechar}
        onSalvar={salvar}
      >
        <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
          <Input maxLength={150} />
        </Form.Item>
        <Form.Item
          name="email"
          label="E-mail (login)"
          rules={[
            { required: true, message: 'Informe o e-mail' },
            { type: 'email', message: 'E-mail inválido' },
          ]}
        >
          <Input type="email" />
        </Form.Item>
        <Form.Item name="telefone" label="Telefone" normalize={mascaraTelefone}>
          <Input inputMode="tel" placeholder="Opcional" />
        </Form.Item>
        <Row gutter={12}>
          <Col xs={16}>
            <Form.Item name="perfilId" label="Perfil de acesso" rules={[{ required: true, message: 'Escolha o perfil' }]}>
              <Select loading={carregandoPerfis} options={opcoesPerfil} />
            </Form.Item>
          </Col>
          <Col xs={8}>
            <Form.Item name="ativo" label="Ativo" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>
        {!editando?.id && (
          <Form.Item
            name="senha"
            label="Senha"
            rules={[{ min: 8, message: 'Use pelo menos 8 caracteres' }]}
            extra="Em branco, o sistema gera uma senha provisória, mostrada uma única vez depois de salvar."
          >
            <Input.Password autoComplete="new-password" maxLength={200} />
          </Form.Item>
        )}
      </PainelFormulario>
      <PainelFormulario
        titulo="Redefinir senha"
        nome={painelSenha.registro?.nome}
        open={painelSenha.aberto}
        form={formSenha}
        name="redefinirSenha"
        textoSalvar="Redefinir senha"
        salvando={salvando}
        onCancelar={painelSenha.fechar}
        onSalvar={redefinirSenha}
      >
        <p className="texto-ajuda">
          A senha atual de {painelSenha.registro?.email ?? 'o funcionário'} deixa de valer na hora. Repasse a nova senha a ele.
        </p>
        <Form.Item
          name="senha"
          label="Nova senha"
          rules={[{ min: 8, message: 'Use pelo menos 8 caracteres' }]}
          extra="Em branco, o sistema gera uma senha provisória, mostrada uma única vez."
        >
          <Input.Password autoComplete="new-password" maxLength={200} />
        </Form.Item>
      </PainelFormulario>
    </div>
  )
}

// Ações de situação da loja, sempre com confirmação
function AcoesSituacao({ loja, mudarStatus, excluir }) {
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [enviando, setEnviando] = useState(null)

  const mudar = async (status, texto) => {
    setEnviando(status)
    try {
      await mudarStatus(status)
      message.success(texto)
    } catch (e) {
      tratarErro(e)
    } finally {
      setEnviando(null)
    }
  }

  const remover = async () => {
    setEnviando('excluir')
    try {
      await excluir()
      message.success('Loja excluída.')
      navigate('/superadmin/lojas')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: () => navigate('/superadmin/lojas') })
      setEnviando(null)
    }
  }

  const ocupado = enviando !== null
  return (
    <>
      {loja.status === 'ativa' && (
        <Popconfirm
          title="Suspender a loja?"
          description="Os funcionários não conseguem mais entrar e o site sai do ar. Os dados são mantidos."
          okText="Suspender"
          okButtonProps={{ danger: true }}
          cancelText="Voltar"
          onConfirm={() => mudar('suspensa', 'Loja suspensa.')}
        >
          <Button danger loading={enviando === 'suspensa'} disabled={ocupado}>
            Suspender
          </Button>
        </Popconfirm>
      )}
      {loja.status !== 'ativa' && (
        <Popconfirm
          title="Reativar a loja?"
          description="Os funcionários voltam a entrar e o site volta ao ar."
          okText="Reativar"
          cancelText="Voltar"
          onConfirm={() => mudar('ativa', 'Loja reativada.')}
        >
          <Button type="primary" loading={enviando === 'ativa'} disabled={ocupado}>
            Reativar
          </Button>
        </Popconfirm>
      )}
      {loja.status !== 'cancelada' && (
        <Popconfirm
          title="Cancelar a loja?"
          description="Ninguém entra mais e o site sai do ar. Os dados ficam guardados e dá para reativar."
          okText="Cancelar loja"
          okButtonProps={{ danger: true }}
          cancelText="Voltar"
          onConfirm={() => mudar('cancelada', 'Loja cancelada.')}
        >
          <Button danger type="text" loading={enviando === 'cancelada'} disabled={ocupado}>
            Cancelar loja
          </Button>
        </Popconfirm>
      )}
      {loja.status === 'cancelada' && (
        <Popconfirm
          title="Excluir a loja?"
          description="Ela sai da lista de lojas e o endereço do site fica livre. O histórico continua na auditoria."
          okText="Excluir"
          okButtonProps={{ danger: true }}
          cancelText="Voltar"
          onConfirm={remover}
        >
          <Button danger icon={<DeleteOutlined />} loading={enviando === 'excluir'} disabled={ocupado}>
            Excluir
          </Button>
        </Popconfirm>
      )}
    </>
  )
}

function Detalhe({ id }) {
  const navigate = useNavigate()
  const { loja, carregando, erro, recarregar, salvar, mudarStatus, excluir, enviarLogo, removerLogo } = useLoja(id)

  // Senha provisória do primeiro Administrador (vem da tela Lojas pela memória da aba; aparece uma única vez)
  const [senhaAdmin, esquecerSenhaAdmin] = useSenhaDaLojaNova(id)

  if (carregando) {
    return (
      <Pagina titulo="Loja" voltar="/superadmin/lojas">
        <Secao>
          <Skeleton active paragraph={{ rows: 8 }} />
        </Secao>
      </Pagina>
    )
  }

  if (!loja) {
    const naoExiste = erro?.status === 404 || erro?.status === 422
    return (
      <Pagina titulo={naoExiste ? 'Loja não encontrada' : 'Loja'} voltar="/superadmin/lojas">
        <Secao>
          {naoExiste ? (
            <EstadoVazio
              titulo="Esta loja não existe ou foi excluída"
              acao={<Button onClick={() => navigate('/superadmin/lojas')}>Ver todas as lojas</Button>}
            />
          ) : (
            <ErroCarregar titulo="Não foi possível carregar a loja" erro={erro} recarregar={recarregar} />
          )}
        </Secao>
      </Pagina>
    )
  }

  const criadaEm = lerDataHora(loja.criadoEm)?.format('MM/YYYY')

  return (
    <Pagina
      voltar="/superadmin/lojas"
      titulo={
        <span className="loja-titulo">
          <Avatar shape="square" size={40} src={loja.logoUrl || undefined} className="marca-loja">
            {loja.nomeFantasia?.[0] ?? '?'}
          </Avatar>
          {loja.nomeFantasia}
          <EtiquetaLoja status={loja.status} />
        </span>
      }
      descricao={
        <>
          {`${tiposLoja[loja.tipo]?.nome ?? loja.tipo ?? '—'}, plano ${loja.planoNome ?? '—'}.${criadaEm ? ` Cliente desde ${criadaEm}.` : ''}`}
          {loja.slug && <EnderecosLoja slug={loja.slug} />}
        </>
      }
      acoes={<AcoesSituacao loja={loja} mudarStatus={mudarStatus} excluir={excluir} />}
    >
      <title>{`${loja.nomeFantasia} | Agenda`}</title>
      {senhaAdmin && <SenhaProvisoria {...senhaAdmin} aoFechar={esquecerSenhaAdmin} />}
      {loja.status !== 'ativa' && (
        <Alert
          type={loja.status === 'suspensa' ? 'warning' : 'error'}
          showIcon
          title={
            loja.status === 'suspensa'
              ? 'Loja suspensa: os funcionários não conseguem entrar, mas os dados estão mantidos.'
              : 'Loja cancelada: ninguém entra e o site está fora do ar. Os dados ficam guardados até a exclusão.'
          }
        />
      )}
      <Secao>
        <Tabs
          items={[
            {
              key: 'dados',
              label: 'Dados gerais',
              children: (
                <DadosGerais
                  key={loja.id}
                  loja={loja}
                  salvar={salvar}
                  enviarLogo={enviarLogo}
                  removerLogo={removerLogo}
                  aoNaoEncontrado={() => navigate('/superadmin/lojas')}
                />
              ),
            },
            { key: 'modulos', label: 'Módulos', children: <Modulos lojaId={loja.id} /> },
            { key: 'funcionarios', label: 'Funcionários', children: <Funcionarios lojaId={loja.id} /> },
            { key: 'historico', label: 'Histórico', children: <HistoricoAlteracoes lojaId={loja.id} /> },
          ]}
        />
      </Secao>
    </Pagina>
  )
}

// Site (página do back-end) e painel da loja abrem em outra aba: links de página inteira, fora da SPA do SUPERADMIN
function EnderecosLoja({ slug }) {
  return (
    <span className="loja-enderecos">
      <a href={caminhoSite(slug)} target="_blank" rel="noopener">
        <GlobalOutlined aria-hidden="true" /> Abrir site <span className="texto-apoio endereco">{caminhoSite(slug)}</span>
      </a>
      <a href={caminhoPainel(slug)} target="_blank" rel="noopener">
        <DesktopOutlined aria-hidden="true" /> Abrir painel <span className="texto-apoio endereco">{caminhoPainel(slug)}</span>
      </a>
    </span>
  )
}

export default function LojaDetalhe() {
  const { id } = useParams()
  // Outra loja = tela nova (sem estado da anterior)
  return <Detalhe key={id} id={id} />
}
