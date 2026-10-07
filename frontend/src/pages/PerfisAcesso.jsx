import { useState } from 'react'
import { Alert, App, Button, Form, Input, Popconfirm, Segmented, Select, Skeleton, Tabs, Tooltip, Typography } from 'antd'
import { DeleteOutlined, DisconnectOutlined, EyeOutlined, LockOutlined, PlusOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { usePerfis, useRecursos } from '../data/usePerfis.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { modulos, niveis } from '../data/acesso.js'
import JornadaPerfil from '../components/perfis/JornadaPerfil.jsx'
import BloqueiosPerfil from '../components/perfis/BloqueiosPerfil.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PainelFormulario from '../components/base/PainelFormulario.jsx'
import { plural } from '../utils/formatos.js'

const opcoesNivel = Object.entries(niveis).map(([value, n]) => ({ value, label: n.label }))
// O catálogo de recursos (API) traz o código do módulo; o nome dele vem da lista fixa de módulos
const nomeModulo = (codigo) => modulos.find((m) => m.codigo === codigo)?.nome ?? codigo

// Configurações > Perfis e horários: o perfil reúne os níveis de acesso (2.1 e 2.2), a jornada semanal (2.5)
// e os bloqueios (2.6). O funcionário é vinculado ao perfil uma vez só e herda tudo isso.
export default function PerfisAcesso() {
  const { pode, perfil: meuPerfil } = useAcesso()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const verAcessos = pode('perfis_acesso')
  const somenteLeitura = !pode('perfis_acesso', 'escrita')
  const verHorarios = pode('config_agendamentos')
  const horariosSomenteLeitura = !pode('config_agendamentos', 'escrita')
  // Cada parte da tela tem a sua permissão: níveis (Perfis de acesso) e jornada/bloqueios (Horários e bloqueios)
  const tudoSomenteLeitura = somenteLeitura && (!verHorarios || horariosSomenteLeitura)
  const perfis = usePerfis({ ativo: verAcessos || verHorarios })
  const recursos = useRecursos({ ativo: verAcessos })
  const [selecionadoId, setSelecionadoId] = useState(null)
  const [novo, setNovo] = useState(false)
  const [criando, setCriando] = useState(false)
  const [excluindo, setExcluindo] = useState(false)
  const [salvandoNivel, setSalvandoNivel] = useState(null)
  const [aba, setAba] = useState(null)
  const [form] = Form.useForm()

  const perfil = perfis.itens.find((p) => p.id === selecionadoId) ?? perfis.itens[0]
  // A API recusa alterar o próprio perfil (quem não é Administrador); o Administrador não muda
  const ehMeuPerfil = !!perfil && perfil.id === meuPerfil?.id && !meuPerfil?.acessoTotal
  const bloqueado = somenteLeitura || !perfil || perfil.acessoTotal || ehMeuPerfil
  const editavel = !somenteLeitura && !ehMeuPerfil

  const definirNivel = async (codigo, nivel) => {
    setSalvandoNivel(codigo)
    try {
      await perfis.definirNivel(perfil.id, codigo, nivel)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: perfis.recarregar })
    } finally {
      setSalvandoNivel(null)
    }
  }

  const editar = async (valores, sucesso) => {
    try {
      await perfis.editar(perfil.id, { nome: perfil.nome, descricao: perfil.descricao, ...valores })
      message.success(sucesso)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: perfis.recarregar })
    }
  }

  // Novo perfil pode partir de outro: a API copia os níveis e a jornada (útil para o mesmo cargo em outro horário)
  const criar = async (valores) => {
    setCriando(true)
    try {
      const criado = await perfis.criar(valores)
      setSelecionadoId(criado.id)
      setNovo(false)
      message.success('Perfil criado.')
    } catch (e) {
      tratarErro(e, { form, mapa: { copiar_de: 'copiarDe' }, aoNaoEncontrado: perfis.recarregar })
    } finally {
      setCriando(false)
    }
  }

  // A API leva junto a jornada e os bloqueios do perfil
  const excluir = async () => {
    setExcluindo(true)
    try {
      await perfis.excluir(perfil.id)
      setSelecionadoId(perfis.itens.find((p) => p.id !== perfil.id)?.id ?? null)
      message.success('Perfil excluído.')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: perfis.recarregar })
    } finally {
      setExcluindo(false)
    }
  }

  const colunas = [
    {
      title: 'Área',
      key: 'recurso',
      render: (_, r) => (
        <span className="recurso">
          <strong>{r.nome}</strong>
          <span className="texto-apoio">
            {nomeModulo(r.modulo)}
            {!r.moduloAtivo && ' (módulo desligado nesta loja)'}
          </span>
        </span>
      ),
    },
    {
      title: 'O que cada nível permite',
      key: 'descricao',
      cartao: 'bloco',
      render: (_, r) =>
        r.leitura || r.escrita ? (
          <div className="recurso texto-ajuda">
            <span>
              <strong>Leitura:</strong> {r.leitura ?? '—'}
            </span>
            <span>
              <strong>Escrita:</strong> {r.escrita ?? '—'}
            </span>
          </div>
        ) : (
          <span className="texto-ajuda">{r.descricao ?? '—'}</span>
        ),
    },
    {
      title: 'Nível',
      key: 'nivel',
      width: 250,
      cartao: 'bloco',
      render: (_, r) => (
        <Segmented
          size="small"
          options={opcoesNivel}
          value={perfil.acessoTotal ? 'escrita' : (perfil.acessos?.[r.codigo] ?? 'nenhum')}
          disabled={bloqueado || salvandoNivel !== null}
          aria-label={`Nível de acesso: ${r.nome}`}
          aria-busy={salvandoNivel === r.codigo}
          onChange={(nivel) => definirNivel(r.codigo, nivel)}
        />
      ),
    },
  ]

  const abas = perfil
    ? [
        verAcessos && {
          key: 'acessos',
          label: 'Níveis de acesso',
          children: (
            <div className="pilha">
              {perfil.acessoTotal && (
                <Alert type="info" showIcon icon={<LockOutlined />} title="O Administrador tem escrita em tudo o que estiver ativo na loja. Esses níveis não mudam." />
              )}
              {ehMeuPerfil && (
                <Alert type="info" showIcon icon={<LockOutlined />} title="Este é o seu perfil. Os níveis dele só podem ser alterados por outra pessoa com acesso a perfis." />
              )}
              <Tabela
                rowKey="codigo"
                size="small"
                pagination={false}
                scroll={{ x: 760 }}
                columns={colunas}
                dataSource={recursos.itens}
                loading={recursos.carregando}
                vazio={
                  recursos.erro ? (
                    <EstadoVazio
                      icone={<DisconnectOutlined />}
                      titulo="Não foi possível carregar as áreas"
                      descricao={recursos.erro.mensagem}
                      acao={<Button onClick={recursos.recarregar}>Tentar de novo</Button>}
                    />
                  ) : (
                    'Nenhuma área com nível de acesso'
                  )
                }
              />
            </div>
          ),
        },
        verHorarios && {
          key: 'jornada',
          label: 'Jornada semanal',
          children: (
            <JornadaPerfil
              key={perfil.id}
              perfil={perfil}
              somenteLeitura={horariosSomenteLeitura}
              aoAlterar={() => perfis.atualizarPerfil(perfil.id).catch(() => perfis.recarregar())}
            />
          ),
        },
        verHorarios && {
          key: 'bloqueios',
          label: 'Bloqueios, folgas e feriados',
          children: <BloqueiosPerfil key={perfil.id} perfil={perfil} somenteLeitura={horariosSomenteLeitura} />,
        },
      ].filter(Boolean)
    : []
  const abaAtiva = abas.find((a) => a.key === aba) ?? abas[0]
  const abaSomenteLeitura = { acessos: somenteLeitura, jornada: horariosSomenteLeitura, bloqueios: horariosSomenteLeitura }
  // Quem só consulta tudo vê a etiqueta no cabeçalho; nos outros casos ela fica na aba que não pode alterar
  const etiquetaAba = !tudoSomenteLeitura && abaAtiva && abaSomenteLeitura[abaAtiva.key] && (
    <Etiqueta icone={<EyeOutlined />} title="Seu perfil permite consultar esta parte, mas não alterar">
      Somente leitura
    </Etiqueta>
  )

  const botaoExcluir =
    !somenteLeitura &&
    perfil &&
    !perfil.padrao &&
    (perfil.funcionarios.length > 0 ? (
      <Tooltip title="Há funcionários com este perfil. Troque o perfil deles antes de excluir.">
        <Button danger icon={<DeleteOutlined />} disabled>
          Excluir perfil
        </Button>
      </Tooltip>
    ) : (
      <Popconfirm
        title="Excluir este perfil?"
        description="A jornada e os bloqueios do perfil também saem."
        okText="Excluir"
        okButtonProps={{ danger: true }}
        cancelText="Cancelar"
        onConfirm={excluir}
      >
        <Button danger icon={<DeleteOutlined />} loading={excluindo}>
          Excluir perfil
        </Button>
      </Popconfirm>
    ))

  const funcionariosDoPerfil = perfil?.funcionarios ?? []

  let listaPerfis
  if (perfis.carregando) {
    listaPerfis = (
      <div className="pilha" aria-busy="true">
        <Skeleton active title={false} paragraph={{ rows: 6 }} />
      </div>
    )
  } else if (perfis.erro && !perfis.itens.length) {
    listaPerfis = (
      <EstadoVazio
        icone={<DisconnectOutlined />}
        titulo="Não foi possível carregar os perfis"
        descricao={perfis.erro.mensagem}
        acao={<Button onClick={perfis.recarregar}>Tentar de novo</Button>}
      />
    )
  } else if (!perfis.itens.length) {
    listaPerfis = <EstadoVazio compacto titulo="Nenhum perfil cadastrado" />
  } else {
    listaPerfis = (
      <ul className="lista-opcoes">
        {perfis.itens.map((p) => (
          <li key={p.id}>
            <button type="button" className="opcao-lista" aria-pressed={p.id === perfil?.id} onClick={() => setSelecionadoId(p.id)}>
              <span className="opcao-lista-titulo">
                {p.acessoTotal && <LockOutlined aria-label="Acesso total" />}
                {p.nome}
              </span>
              {p.descricao && <span className="texto-apoio">{p.descricao}</span>}
              <span className="opcao-lista-meta">
                <span className="texto-apoio">{plural(p.funcionarios.length, 'funcionário', 'funcionários')}</span>
                {p.padrao && <Etiqueta tom="contorno">Padrão</Etiqueta>}
                {verHorarios && p.semJornada && <Etiqueta tom="atencao">Sem jornada</Etiqueta>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <Pagina
      titulo="Perfis e horários"
      descricao="Cada perfil reúne o que o funcionário pode acessar, a jornada semanal e as folgas. O funcionário herda tudo do perfil dele."
      acoes={
        somenteLeitura ? (
          tudoSomenteLeitura && (
            <Etiqueta icone={<EyeOutlined />} title="Seu perfil permite consultar, mas não alterar">
              Somente leitura
            </Etiqueta>
          )
        ) : (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setNovo(true)}>
            Novo perfil
          </Button>
        )
      }
    >
      <div className="grade-lista-detalhe">
        <Secao rente titulo="Perfis">
          {listaPerfis}
        </Secao>

        {perfil && (
          <Secao
            titulo={
              <Typography.Text
                className="titulo-editavel"
                editable={
                  editavel && !perfil.padrao
                    ? {
                        tooltip: 'Renomear',
                        maxLength: 60,
                        onChange: (nome) => nome.trim() && nome.trim() !== perfil.nome && editar({ nome: nome.trim() }, 'Perfil renomeado.'),
                      }
                    : false
                }
              >
                {perfil.nome}
              </Typography.Text>
            }
            descricao={
              funcionariosDoPerfil.length
                ? `Funcionários: ${funcionariosDoPerfil.map((f) => (f.ativo ? f.nome : `${f.nome} (inativo)`)).join(', ')}.`
                : 'Nenhum funcionário neste perfil.'
            }
            acoes={botaoExcluir}
          >
            <Typography.Paragraph
              type="secondary"
              editable={
                editavel
                  ? {
                      tooltip: 'Editar descrição',
                      text: perfil.descricao ?? '',
                      maxLength: 2000,
                      onChange: (descricao) =>
                        descricao.trim() !== (perfil.descricao ?? '') && editar({ descricao: descricao.trim() }, 'Descrição salva.'),
                    }
                  : false
              }
            >
              {perfil.descricao || 'Sem descrição.'}
            </Typography.Paragraph>
            <Tabs
              items={abas}
              activeKey={abaAtiva?.key}
              onChange={setAba}
              tabBarExtraContent={etiquetaAba ? { right: etiquetaAba } : undefined}
            />
          </Secao>
        )}
      </div>

      <PainelFormulario
        titulo="Novo perfil"
        open={novo}
        form={form}
        textoSalvar="Criar perfil"
        salvando={criando}
        onCancelar={() => setNovo(false)}
        onSalvar={criar}
      >
        <Form.Item
          name="nome"
          label="Nome"
          rules={[
            { required: true, whitespace: true, message: 'Informe o nome' },
            {
              validator: (_, v) =>
                perfis.itens.some((p) => p.nome.toLowerCase() === v?.trim().toLowerCase())
                  ? Promise.reject(new Error('Já existe um perfil com esse nome'))
                  : Promise.resolve(),
            },
          ]}
        >
          <Input maxLength={60} placeholder="Ex.: Profissional manhã" />
        </Form.Item>
        <Form.Item name="descricao" label="Descrição">
          <Input.TextArea rows={2} maxLength={2000} placeholder="Para que serve este perfil" />
        </Form.Item>
        <Form.Item
          name="copiarDe"
          label="Copiar níveis e jornada de"
          extra="Em branco, o perfil começa sem acesso a nada e sem jornada. Ajuste depois de criar."
        >
          <Select allowClear placeholder="Começar do zero" options={perfis.itens.map((p) => ({ value: p.id, label: p.nome }))} />
        </Form.Item>
      </PainelFormulario>
    </Pagina>
  )
}
