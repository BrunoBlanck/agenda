import { useDeferredValue, useState } from 'react'
import { App, Avatar, Button, Checkbox, Col, Form, Input, Row, Select } from 'antd'
import { PlusOutlined, RightOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { opcoesTipoLoja, statusLoja } from '../../data/plataforma.js'
import { usePlataforma } from '../usePlataforma.js'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import BarraFiltros from '../../components/base/BarraFiltros.jsx'
import Tabela from '../../components/base/Tabela.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import PainelFormulario from '../../components/base/PainelFormulario.jsx'
import { EtiquetaLoja } from '../../components/Etiquetas.jsx'

const opcionais = modulos.filter((m) => m.opcional)

const gerarSlug = (texto = '') =>
  texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

export default function Lojas() {
  const { lojas, planos } = useData()
  const { nomeTipo, plano, funcionariosDe, criarLoja, ehAtual } = usePlataforma()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [busca, setBusca] = useState('')
  const termo = useDeferredValue(busca.trim().toLowerCase())
  const [tipo, setTipo] = useState(null)
  const [status, setStatus] = useState(null)
  const [nova, setNova] = useState(false)
  const [form] = Form.useForm()
  const abrir = (l) => navigate(`/superadmin/lojas/${l.id}`)

  const dados = lojas.itens
    .filter((l) => `${l.nomeFantasia} ${l.nome} ${l.slug} ${l.cidade}`.toLowerCase().includes(termo))
    .filter((l) => !tipo || l.tipo === tipo)
    .filter((l) => !status || l.status === status)

  const salvar = (v) => {
    const id = criarLoja(v)
    setNova(false)
    message.success('Loja criada. O Administrador recebe o e-mail para definir a senha.')
    navigate(`/superadmin/lojas/${id}`)
  }

  const colunas = [
    {
      title: 'Loja',
      key: 'loja',
      sorter: (a, b) => a.nomeFantasia.localeCompare(b.nomeFantasia),
      render: (_, l) => (
        <span className="loja-nome">
          <Avatar shape="square" size={32} src={l.logoUrl} className="marca-loja">
            {l.nomeFantasia[0]}
          </Avatar>
          <span>
            <button type="button" className="link-tabela" onClick={() => abrir(l)}>
              {l.nomeFantasia}
            </button>
            <span className="texto-apoio">
              /{l.slug}
              {ehAtual(l) && ', aberta no painel da loja'}
            </span>
          </span>
        </span>
      ),
    },
    { title: 'Tipo', dataIndex: 'tipo', render: nomeTipo },
    { title: 'Plano', dataIndex: 'planoId', render: (id) => plano(id)?.nome ?? '—' },
    { title: 'Cidade', key: 'cidade', render: (_, l) => (l.cidade ? `${l.cidade}/${l.uf}` : '—') },
    {
      title: 'Módulos ligados',
      key: 'modulos',
      render: (_, l) => {
        const ligados = opcionais.filter((m) => l.modulos?.[m.codigo])
        return ligados.length ? ligados.map((m) => m.nome).join(', ') : <span className="texto-apoio">Nenhum</span>
      },
    },
    {
      title: 'Funcionários',
      key: 'funcionarios',
      align: 'right',
      render: (_, l) => funcionariosDe(l).filter((f) => f.ativo).length,
    },
    { title: 'Situação', dataIndex: 'status', render: (s) => <EtiquetaLoja status={s} /> },
    {
      title: <span className="sr-only">Abrir</span>,
      key: 'abrir',
      width: 48,
      align: 'right',
      render: (_, l) => <Button type="text" size="small" icon={<RightOutlined />} aria-label={`Abrir ${l.nomeFantasia}`} onClick={() => abrir(l)} />,
    },
  ]

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
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
          <Select allowClear placeholder="Todos os tipos" aria-label="Tipo" value={tipo} onChange={setTipo} options={opcoesTipoLoja} />
          <Select
            allowClear
            placeholder="Todas as situações"
            aria-label="Situação"
            value={status}
            onChange={setStatus}
            options={Object.entries(statusLoja).map(([value, s]) => ({ value, label: s.label }))}
          />
        </BarraFiltros>
        <Tabela
          columns={colunas}
          dataSource={dados}
          vazio={<EstadoVazio compacto titulo="Nenhuma loja com esses filtros" />}
        />
      </Secao>

      <PainelFormulario
        titulo="Nova loja"
        open={nova}
        form={form}
        valoresIniciais={{ modulos: [] }}
        textoSalvar="Criar loja"
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
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="nome" label="Razão social" rules={[{ required: true, whitespace: true, message: 'Informe a razão social' }]}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="tipo" label="Tipo" rules={[{ required: true, message: 'Escolha o tipo' }]} extra="Define o site do consumidor.">
              <Select options={opcoesTipoLoja} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="planoId" label="Plano" rules={[{ required: true, message: 'Escolha o plano' }]}>
              <Select options={planos.itens.filter((p) => p.ativo).map((p) => ({ value: p.id, label: p.nome }))} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="slug"
              label="Endereço do site"
              rules={[
                { required: true, message: 'Informe o endereço' },
                {
                  validator: (_, v) =>
                    lojas.todos.some((l) => l.slug === v) ? Promise.reject(new Error('Já está em uso por outra loja')) : Promise.resolve(),
                },
              ]}
            >
              <Input prefix="/" />
            </Form.Item>
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
              <Input />
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
        </Row>
        <p className="texto-ajuda">O Administrador recebe um e-mail para definir a senha. Os perfis padrão são criados junto com a loja.</p>
      </PainelFormulario>
    </Pagina>
  )
}
