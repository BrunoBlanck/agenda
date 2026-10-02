import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, App, Avatar, Button, Col, DatePicker, Form, Input, Popconfirm, Row, Select, Switch, Tabs, Tooltip } from 'antd'
import { EditOutlined, ExportOutlined, KeyOutlined, LockOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { opcoesTipoLoja, statusLoja } from '../../data/plataforma.js'
import UltimaAlteracao from '../../components/UltimaAlteracao.jsx'
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
import { usePlataforma } from '../usePlataforma.js'
import HistoricoAlteracoes from '../HistoricoAlteracoes.jsx'

const FUSOS = ['America/Sao_Paulo', 'America/Manaus', 'America/Cuiaba', 'America/Rio_Branco', 'America/Noronha']

function DadosGerais({ loja }) {
  const { planos } = useData()
  const { editarLoja } = usePlataforma()
  const { message } = App.useApp()

  const salvar = (valores) => {
    editarLoja(loja, valores)
    message.success('Dados da loja salvos.')
  }

  return (
    <Form layout="vertical" initialValues={loja} onFinish={salvar}>
      <h3 className="grupo-formulario">Plataforma</h3>
      <Row gutter={16}>
        <Col xs={24} sm={12} lg={8}>
          <Form.Item name="tipo" label="Tipo" rules={[{ required: true }]} extra="Define o site do consumidor.">
            <Select options={opcoesTipoLoja} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Form.Item name="planoId" label="Plano" rules={[{ required: true }]} extra="Só o valor cobrado. Não muda os módulos.">
            <Select options={planos.itens.map((p) => ({ value: p.id, label: p.nome, disabled: !p.ativo }))} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Form.Item name="status" label="Situação" rules={[{ required: true }]}>
            <Select options={Object.entries(statusLoja).map(([value, s]) => ({ value, label: s.label }))} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Form.Item name="slug" label="Endereço do site" rules={[{ required: true, message: 'Informe o endereço' }]}>
            <Input prefix="/" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Form.Item name="fusoHorario" label="Fuso horário">
            <Select options={FUSOS.map((f) => ({ value: f, label: f }))} />
          </Form.Item>
        </Col>
      </Row>

      <h3 className="grupo-formulario">Dados da loja</h3>
      <p className="texto-ajuda grupo-formulario-ajuda">A própria loja também pode editar estes dados em Configurações.</p>
      <CamposEmpresa />
      <CamposEndereco />

      <div className="rodape-formulario">
        <UltimaAlteracao item={loja} />
        <Button type="primary" htmlType="submit">
          Salvar dados
        </Button>
      </div>
    </Form>
  )
}

function Modulos({ loja }) {
  const { definirModulo } = usePlataforma()

  const colunas = [
    { title: 'Módulo', dataIndex: 'nome', render: (n) => <strong>{n}</strong> },
    {
      title: 'Situação',
      key: 'situacao',
      width: 150,
      render: (_, m) =>
        m.opcional ? (
          <Switch
            checked={!!loja.modulos?.[m.codigo]}
            checkedChildren="Ligado"
            unCheckedChildren="Desligado"
            aria-label={`Ligar ou desligar ${m.nome}`}
            onChange={(ativo) => definirModulo(loja, m.codigo, { ativo })}
          />
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
            key={`${loja.id}-${m.codigo}`}
            defaultValue={loja.modulosInfo?.[m.codigo]?.observacao}
            placeholder='Ex.: "cortesia até dez/2026"'
            aria-label={`Observação sobre ${m.nome}`}
            onBlur={(e) =>
              e.target.value !== (loja.modulosInfo?.[m.codigo]?.observacao ?? '') &&
              definirModulo(loja, m.codigo, { observacao: e.target.value })
            }
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
            value={loja.modulosInfo?.[m.codigo]?.expiraEm ? dayjs(loja.modulosInfo[m.codigo].expiraEm) : null}
            onChange={(d) => definirModulo(loja, m.codigo, { expiraEm: d ? d.endOf('day').toISOString() : null })}
          />
        ),
    },
  ]

  return (
    <div className="pilha">
      <p className="texto-ajuda">
        Ligue só o que a loja usa: o que estiver desligado some do menu dela. Não depende do tipo nem do plano. Desligar não
        apaga dados: tudo volta ao religar.
      </p>
      <Tabela rowKey="codigo" size="small" pagination={false} columns={colunas} dataSource={modulos} />
    </div>
  )
}

function Funcionarios({ loja }) {
  const { funcionariosDe, perfisDe, salvarFuncionario, redefinirSenha: registrarSenha } = usePlataforma()
  const { message } = App.useApp()
  const painel = usePainel()
  const editando = painel.registro
  const [busca, setBusca] = useState('')
  const [form] = Form.useForm()
  const lista = funcionariosDe(loja)
  const visiveis = lista.filter((f) => `${f.nome} ${f.email}`.toLowerCase().includes(busca.trim().toLowerCase()))

  const salvar = (v) => {
    const admins = lista.filter((f) => f.id !== editando.id && f.ativo && f.perfil === 'Administrador')
    if (editando.perfil === 'Administrador' && (v.perfil !== 'Administrador' || !v.ativo) && admins.length === 0) {
      message.error('A loja precisa de pelo menos um Administrador ativo. Defina outro antes de mudar este.')
      return
    }
    salvarFuncionario(loja, v, editando.id)
    message.success('Funcionário salvo.')
    painel.fechar()
  }

  const redefinirSenha = (f) => {
    registrarSenha(loja, f)
    message.success(`Link de nova senha enviado para ${f.email}.`)
  }

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', sorter: (a, b) => a.nome.localeCompare(b.nome), render: (n) => <strong>{n}</strong> },
    { title: 'E-mail (login)', dataIndex: 'email' },
    {
      title: 'Perfil',
      dataIndex: 'perfil',
      render: (p) =>
        p === 'Administrador' ? (
          <Etiqueta tom="tinta" icone={<LockOutlined />}>
            {p}
          </Etiqueta>
        ) : (
          <Etiqueta tom="contorno">{p}</Etiqueta>
        ),
    },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => <EtiquetaSituacao ativo={a} /> },
    {
      title: 'Criado por',
      key: 'origem',
      render: (_, f) => (f.criadoPorSuperadmin ? 'Superadmin' : <span className="texto-apoio">Loja</span>),
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
          <Popconfirm
            title="Redefinir a senha?"
            description={`Enviamos um link para ${f.email} criar uma nova senha.`}
            okText="Enviar link"
            cancelText="Cancelar"
            onConfirm={() => redefinirSenha(f)}
          >
            <Tooltip title="Redefinir senha">
              <Button type="text" size="small" icon={<KeyOutlined />} aria-label="Redefinir senha" />
            </Tooltip>
          </Popconfirm>
        </span>
      ),
    },
  ]

  return (
    <div className="pilha">
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
        dataSource={visiveis}
        destaqueId={painel.destaqueId}
        vazio={<EstadoVazio compacto titulo={busca ? 'Ninguém com esse nome ou e-mail' : 'Nenhum funcionário'} />}
      />
      <p className="texto-ajuda">O superadmin pode criar funcionários com qualquer perfil, inclusive Administrador.</p>
      <PainelFormulario
        titulo={editando?.id ? 'Editar funcionário' : 'Novo funcionário'}
        nome={editando?.nome}
        open={painel.aberto}
        form={form}
        valoresIniciais={editando?.id ? editando : { perfil: 'Administrador', ativo: true }}
        onCancelar={painel.fechar}
        onSalvar={salvar}
        rodape={!editando?.id && <span className="texto-apoio">O funcionário recebe um e-mail para definir a senha.</span>}
      >
        <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
          <Input />
        </Form.Item>
        <Form.Item
          name="email"
          label="E-mail (login)"
          rules={[
            { required: true, message: 'Informe o e-mail' },
            { type: 'email', message: 'E-mail inválido' },
            {
              validator: (_, v) =>
                lista.some((f) => f.id !== editando?.id && f.email === v)
                  ? Promise.reject(new Error('Já existe um funcionário com esse e-mail nesta loja'))
                  : Promise.resolve(),
            },
          ]}
        >
          <Input type="email" />
        </Form.Item>
        <Row gutter={12}>
          <Col xs={16}>
            <Form.Item name="perfil" label="Perfil de acesso" rules={[{ required: true }]}>
              <Select options={perfisDe(loja).map((p) => ({ value: p, label: p }))} />
            </Form.Item>
          </Col>
          <Col xs={8}>
            <Form.Item name="ativo" label="Ativo" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>
      </PainelFormulario>
    </div>
  )
}

export default function LojaDetalhe() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { lojas } = useData()
  const { message } = App.useApp()
  const { nomeTipo, plano, ehAtual, editarLoja } = usePlataforma()
  const loja = lojas.itens.find((l) => String(l.id) === id)

  if (!loja) {
    return (
      <Pagina titulo="Loja não encontrada" voltar="/superadmin/lojas">
        <Secao>
          <EstadoVazio
            titulo="Esta loja não existe ou foi excluída"
            acao={<Button onClick={() => navigate('/superadmin/lojas')}>Ver todas as lojas</Button>}
          />
        </Secao>
      </Pagina>
    )
  }

  const mudarSituacao = (status) => {
    editarLoja(loja, { status })
    message.success(status === 'ativa' ? 'Loja reativada.' : 'Loja suspensa.')
  }

  return (
    <Pagina
      voltar="/superadmin/lojas"
      titulo={
        <span className="loja-titulo">
          <Avatar shape="square" size={40} src={loja.logoUrl} className="marca-loja">
            {loja.nomeFantasia[0]}
          </Avatar>
          {loja.nomeFantasia}
          <EtiquetaLoja status={loja.status} />
        </span>
      }
      descricao={`${nomeTipo(loja.tipo)}, plano ${plano(loja.planoId)?.nome ?? '—'}. Site em /${loja.slug}. Cliente desde ${dayjs(loja.criadoEm).format('MM/YYYY')}.`}
      acoes={
        <>
          {ehAtual(loja) && (
            <Button icon={<ExportOutlined />} onClick={() => navigate('/painel')}>
              Abrir painel da loja
            </Button>
          )}
          {loja.status === 'ativa' ? (
            <Popconfirm
              title="Suspender a loja?"
              description="Os funcionários não conseguem mais entrar. Os dados são mantidos."
              okText="Suspender"
              okButtonProps={{ danger: true }}
              cancelText="Cancelar"
              onConfirm={() => mudarSituacao('suspensa')}
            >
              <Button danger>Suspender</Button>
            </Popconfirm>
          ) : (
            <Button type="primary" onClick={() => mudarSituacao('ativa')}>
              Reativar
            </Button>
          )}
        </>
      }
    >
      <title>{`${loja.nomeFantasia} | Agenda`}</title>
      {loja.status !== 'ativa' && (
        <Alert
          type={loja.status === 'suspensa' ? 'warning' : 'error'}
          showIcon
          title={
            loja.status === 'suspensa'
              ? 'Loja suspensa: os funcionários não conseguem entrar, mas os dados estão mantidos.'
              : 'Loja cancelada: dados mantidos pelo período definido antes da remoção.'
          }
        />
      )}
      <Secao>
        <Tabs
          items={[
            // A chave inclui a situação para o formulário recarregar quando ela muda pelos botões do topo
            { key: 'dados', label: 'Dados gerais', children: <DadosGerais key={`${loja.id}-${loja.status}`} loja={loja} /> },
            { key: 'modulos', label: 'Módulos', children: <Modulos loja={loja} /> },
            { key: 'funcionarios', label: 'Funcionários', children: <Funcionarios loja={loja} /> },
            { key: 'historico', label: 'Histórico', children: <HistoricoAlteracoes lojaId={loja.id} /> },
          ]}
        />
      </Secao>
    </Pagina>
  )
}
