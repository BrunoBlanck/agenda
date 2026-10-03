import { useState } from 'react'
import { App, Avatar, Button, Checkbox, Col, Form, Input, Row, Select } from 'antd'
import { DisconnectOutlined, PlusOutlined, RightOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { modulos } from '../../data/acesso.js'
import { opcoesTipoLoja, statusLoja, tiposLoja } from '../../data/dominio.js'
import { useTratarErro } from '../../data/api/useTratarErro.js'
import { entregarSenhaDaLojaNova, useAtrasado, useLojas, usePlanos } from '../usePlataforma.js'
import { erroNoCampo } from '../erroNoCampo.js'
import CampoEnderecoLoja from '../CampoEnderecoLoja.jsx'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import BarraFiltros from '../../components/base/BarraFiltros.jsx'
import Tabela from '../../components/base/Tabela.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import PainelFormulario from '../../components/base/PainelFormulario.jsx'
import { EtiquetaLoja } from '../../components/Etiquetas.jsx'

const opcionais = modulos.filter((m) => m.opcional)
const nomeModulo = (codigo) => opcionais.find((m) => m.codigo === codigo)?.nome ?? codigo.replace(/_/g, ' ')
const opcoesStatus = Object.entries(statusLoja).map(([value, s]) => ({ value, label: s.label }))
const valido = (valor, mapa) => (valor && valor in mapa ? valor : null)

// 409 da criação que tem campo certo no formulário (o resto vira mensagem)
const CONFLITOS = [{ trecho: 'endereço de acesso', campo: 'slug' }]

const gerarSlug = (texto = '') =>
  texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

export default function Lojas() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const tratarErro = useTratarErro()
  const { message } = App.useApp()
  const [busca, setBusca] = useState('')
  const termo = useAtrasado(busca.trim())
  const [tipo, setTipo] = useState(() => valido(params.get('tipo'), tiposLoja))
  const [status, setStatus] = useState(() => valido(params.get('status'), statusLoja))
  const [pagina, setPagina] = useState(1)
  const lojas = useLojas({ busca: termo, tipo, status, pagina })
  const planos = usePlanos()
  const [nova, setNova] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [form] = Form.useForm()
  const abrir = (l) => navigate(`/superadmin/lojas/${l.id}`)

  // Filtro novo volta para a primeira página
  const filtrar = (mudar) => (valor) => {
    mudar(valor ?? null)
    setPagina(1)
  }
  const [termoAnterior, setTermoAnterior] = useState(termo)
  if (termo !== termoAnterior) {
    setTermoAnterior(termo)
    setPagina(1)
  }

  const salvar = async (v) => {
    setSalvando(true)
    try {
      const { loja, admin, senhaProvisoria } = await lojas.criar(v)
      setNova(false)
      message.success('Loja criada.')
      // A senha provisória vai para o detalhe da loja, que mostra uma única vez. Vai pela memória da aba, nunca
      // pelo state da navegação (ficaria em history.state e voltaria no F5 e no voltar/avançar)
      entregarSenhaDaLojaNova(loja.id, { nome: admin?.nome, email: admin?.email, senha: senhaProvisoria })
      navigate(`/superadmin/lojas/${loja.id}`)
    } catch (e) {
      if (!erroNoCampo(e, form, CONFLITOS)) tratarErro(e, { form, mapa: { plano_id: 'planoId' } })
    } finally {
      setSalvando(false)
    }
  }

  const colunas = [
    {
      title: 'Loja',
      key: 'loja',
      render: (_, l) => (
        <span className="loja-nome">
          <Avatar shape="square" size={32} src={l.logoUrl || undefined} className="marca-loja">
            {l.nomeFantasia?.[0] ?? '?'}
          </Avatar>
          <span>
            <button type="button" className="link-tabela" onClick={() => abrir(l)}>
              {l.nomeFantasia}
            </button>
            <span className="texto-apoio">/{l.slug}</span>
          </span>
        </span>
      ),
    },
    { title: 'Tipo', dataIndex: 'tipo', render: (t) => tiposLoja[t]?.nome ?? t ?? '—' },
    { title: 'Plano', dataIndex: 'planoNome', render: (n) => n ?? '—' },
    { title: 'Cidade', key: 'cidade', render: (_, l) => (l.cidade ? [l.cidade, l.uf].filter(Boolean).join('/') : '—') },
    {
      title: 'Módulos ligados',
      key: 'modulos',
      render: (_, l) => {
        const ligados = Object.entries(l.modulos ?? {})
          .filter(([, ativo]) => ativo)
          .map(([codigo]) => nomeModulo(codigo))
        return ligados.length ? ligados.join(', ') : <span className="texto-apoio">Nenhum</span>
      },
    },
    { title: 'Funcionários', dataIndex: 'funcionariosAtivos', align: 'right' },
    { title: 'Situação', dataIndex: 'status', render: (s) => <EtiquetaLoja status={s} /> },
    {
      title: <span className="sr-only">Abrir</span>,
      key: 'abrir',
      width: 48,
      align: 'right',
      render: (_, l) => <Button type="text" size="small" icon={<RightOutlined />} aria-label={`Abrir ${l.nomeFantasia}`} onClick={() => abrir(l)} />,
    },
  ]

  const comFiltro = !!(termo || tipo || status)
  const vazio = lojas.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar as lojas"
      descricao={lojas.erro.mensagem}
      acao={<Button onClick={lojas.recarregar}>Tentar de novo</Button>}
    />
  ) : comFiltro ? (
    <EstadoVazio compacto titulo="Nenhuma loja com esses filtros" />
  ) : (
    <EstadoVazio titulo="Nenhuma loja cadastrada" acao={<Button onClick={() => setNova(true)}>Nova loja</Button>} />
  )

  return (
    <Pagina
      titulo="Lojas"
      descricao="Todas as lojas da plataforma. Abra uma loja para mudar dados, módulos e funcionários."
      acoes={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setNova(true)}>
          Nova loja
        </Button>
      }
    >
      <Secao rente>
        <BarraFiltros>
          <Input
            className="busca"
            prefix={<SearchOutlined />}
            placeholder="Buscar por nome, endereço ou cidade"
            aria-label="Buscar loja"
            allowClear
            maxLength={100}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
          <Select allowClear placeholder="Todos os tipos" aria-label="Tipo" value={tipo} onChange={filtrar(setTipo)} options={opcoesTipoLoja} />
          <Select
            allowClear
            placeholder="Todas as situações"
            aria-label="Situação"
            value={status}
            onChange={filtrar(setStatus)}
            options={opcoesStatus}
          />
        </BarraFiltros>
        <Tabela
          columns={colunas}
          dataSource={lojas.erro ? [] : lojas.itens}
          loading={lojas.carregando || lojas.atualizando}
          pagination={{
            current: lojas.pagina,
            pageSize: lojas.porPagina,
            total: lojas.total,
            onChange: setPagina,
            showSizeChanger: false,
            hideOnSinglePage: true,
          }}
          vazio={vazio}
        />
      </Secao>

      <PainelFormulario
        titulo="Nova loja"
        open={nova}
        form={form}
        valoresIniciais={{ modulos: [] }}
        textoSalvar="Criar loja"
        salvando={salvando}
        largura={560}
        onCancelar={() => setNova(false)}
        onSalvar={salvar}
        onValuesChange={(mudou) => {
          if ('nomeFantasia' in mudou) form.setFieldsValue({ slug: gerarSlug(mudou.nomeFantasia) })
        }}
      >
        <h3 className="grupo-formulario">Dados da loja</h3>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item name="nomeFantasia" label="Nome da loja" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
              <Input maxLength={150} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="nome" label="Razão social" rules={[{ required: true, whitespace: true, message: 'Informe a razão social' }]}>
              <Input maxLength={150} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="tipo" label="Tipo" rules={[{ required: true, message: 'Escolha o tipo' }]} extra="Define o site do consumidor.">
              <Select options={opcoesTipoLoja} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="planoId" label="Plano" rules={[{ required: true, message: 'Escolha o plano' }]}>
              <Select
                loading={planos.carregando}
                notFoundContent={planos.erro ? 'Não foi possível carregar os planos' : 'Nenhum plano ativo'}
                options={planos.itens.filter((p) => p.ativo).map((p) => ({ value: p.id, label: p.nome }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <CampoEnderecoLoja />
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="email" label="E-mail da loja" rules={[{ type: 'email', message: 'E-mail inválido' }]}>
              <Input type="email" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="modulos"
          label="Módulos que a loja vai usar"
          extra="O que ficar desmarcado não aparece no menu da loja. Dá para mudar depois, em Módulos."
        >
          <Checkbox.Group options={opcionais.map((m) => ({ value: m.codigo, label: m.nome }))} />
        </Form.Item>
        <h3 className="grupo-formulario">Primeiro funcionário (Administrador)</h3>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item name={['admin', 'nome']} label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
              <Input maxLength={150} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name={['admin', 'email']}
              label="E-mail (login)"
              rules={[
                { required: true, message: 'Informe o e-mail' },
                { type: 'email', message: 'E-mail inválido' },
              ]}
            >
              <Input type="email" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name={['admin', 'senha']}
              label="Senha"
              rules={[{ min: 8, message: 'Use pelo menos 8 caracteres' }]}
              extra="Em branco, o sistema gera uma senha provisória."
            >
              <Input.Password autoComplete="new-password" maxLength={200} />
            </Form.Item>
          </Col>
        </Row>
        <p className="texto-ajuda">Os perfis padrão são criados junto com a loja. A senha provisória aparece uma única vez, depois de criar.</p>
      </PainelFormulario>
    </Pagina>
  )
}
