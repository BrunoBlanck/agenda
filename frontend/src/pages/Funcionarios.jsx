import { useState } from 'react'
import { App, Button, ColorPicker, Col, Flex, Form, Input, Popconfirm, Row, Select, Switch, Tooltip, Typography } from 'antd'
import { DeleteOutlined, DisconnectOutlined, LockOutlined, PlusOutlined, TagsOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import PainelLateral from '../components/base/PainelLateral.jsx'
import { EtiquetaSituacao } from '../components/Etiquetas.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { useCargos, useFuncionarios } from '../data/useFuncionarios.js'
import { usePerfis } from '../data/usePerfis.js'
import { MAPA_ERROS_FUNCIONARIO } from '../data/api/funcionarios.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { COR_PADRAO } from '../components/agenda/util.js'
import { mascaraCpf, mascaraTelefone, soDigitos } from '../utils/formatos.js'
import { coresAgenda } from '../tema.js'

// Id do registro aberto no formulário (vazio = cadastro novo), do campo oculto "id" no fim do formulário.
// Precisa ser um campo registrado: assim ele sai do formulário ao fechar o painel e um cadastro novo
// não herda o id da última edição.
const useIdEmEdicao = () => Form.useWatch('id', Form.useFormInstance())

const pesoNivel = { nenhum: 0, leitura: 1, escrita: 2 }

// Por que este perfil não pode ser atribuído por quem está editando (null = pode). Espelha a API (ACE-19):
// só o Administrador atribui o Administrador e ninguém atribui perfil com nível acima do próprio.
// teto(codigo): o nível de quem edita. Sem os níveis do perfil (acessos = null) não dá para comparar e a API decide.
function motivoBloqueio(perfil, { souAdmin, teto }) {
  if (souAdmin) return null
  if (perfil.acessoTotal) return 'só um Administrador atribui'
  if (!perfil.acessos) return null
  const acima = Object.entries(perfil.acessos).some(([codigo, nivel]) => (pesoNivel[nivel] ?? 0) > pesoNivel[teto(codigo)])
  return acima ? 'acesso maior que o seu' : null
}

// Perfil: ninguém troca o próprio (a API recusa com 403) nem atribui perfil acima do seu.
// O perfil que o funcionário já tem continua selecionável (manter não é atribuir).
function CampoPerfil({ perfis, funcionarios, souAdmin, teto, meuId }) {
  const id = useIdEmEdicao()
  const proprio = !!id && id === meuId
  const perfilAtual = id ? funcionarios.itens.find((f) => f.id === id)?.perfilId : null
  const opcoes = perfis.itens.map((p) => {
    const motivo = p.id === perfilAtual ? null : motivoBloqueio(p, { souAdmin, teto })
    return { value: p.id, label: p.nome, disabled: !!motivo, motivo }
  })
  const algumBloqueado = opcoes.some((o) => o.disabled)
  let ajuda = 'Acessos e jornada vêm do perfil (Configurações, Perfis e horários).'
  if (proprio) ajuda = 'Você não pode trocar o seu próprio perfil de acesso.'
  else if (algumBloqueado) ajuda = `${ajuda} Perfis com acesso maior que o seu ficam indisponíveis.`
  return (
    <Form.Item name="perfilId" label="Perfil" rules={[{ required: true, message: 'Escolha o perfil' }]} extra={ajuda}>
      <Select
        options={opcoes}
        disabled={proprio}
        loading={perfis.carregando}
        placeholder={perfis.erro ? 'Não foi possível carregar os perfis' : undefined}
        optionRender={(opcao) =>
          opcao.data.motivo ? (
            <span className="opcao-indisponivel">
              {opcao.data.label}
              <span className="texto-apoio">{opcao.data.motivo}</span>
            </span>
          ) : (
            opcao.data.label
          )
        }
      />
    </Form.Item>
  )
}

// Senha: obrigatória no cadastro (a pessoa entra com ela); na edição, só para trocar
function CampoSenha() {
  const novo = !useIdEmEdicao()
  return (
    <Form.Item
      name="senha"
      label={novo ? 'Senha inicial' : 'Nova senha'}
      rules={[{ required: novo, message: 'Informe a senha inicial' }, { min: 8, message: 'A senha precisa ter pelo menos 8 caracteres' }]}
      extra={novo ? 'Passe a senha para a pessoa; ela entra com o e-mail e esta senha.' : 'Deixe em branco para manter a senha atual.'}
    >
      <Input.Password autoComplete="new-password" maxLength={200} />
    </Form.Item>
  )
}

// Cargo: os ativos; um cargo inativo continua aparecendo para quem já o tem
function CampoCargo({ cargos }) {
  const form = Form.useFormInstance()
  const atual = Form.useWatch('cargoId', form)
  const opcoes = cargos.itens
    .filter((c) => c.ativo || c.id === atual)
    .map((c) => ({ value: c.id, label: c.ativo ? c.nome : `${c.nome} (inativo)` }))
  return (
    <Form.Item name="cargoId" label="Cargo" extra="Informativo. Quem define o acesso é o perfil.">
      <Select
        allowClear
        options={opcoes}
        loading={cargos.carregando}
        placeholder={cargos.erro ? 'Não foi possível carregar os cargos' : 'Sem cargo'}
      />
    </Form.Item>
  )
}

// Cargos da loja num painel lateral: adicionar, renomear, inativar e excluir (sem empilhar painéis:
// tudo acontece na própria lista)
function PainelCargos({ open, onClose, cargos, somenteLeitura }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const [adicionando, setAdicionando] = useState(false)
  const [ocupadoId, setOcupadoId] = useState(null)

  const adicionar = async ({ nome }) => {
    setAdicionando(true)
    try {
      await cargos.salvar({ nome })
      form.resetFields()
      message.success('Cargo adicionado.')
    } catch (e) {
      tratarErro(e, { form })
    } finally {
      setAdicionando(false)
    }
  }

  const alterar = async (cargo, valores, sucesso) => {
    setOcupadoId(cargo.id)
    try {
      await cargos.salvar(valores, cargo)
      message.success(sucesso)
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: cargos.recarregar })
    } finally {
      setOcupadoId(null)
    }
  }

  const excluir = async (cargo) => {
    setOcupadoId(cargo.id)
    try {
      await cargos.excluir(cargo)
      message.success('Cargo excluído.')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: cargos.recarregar })
    } finally {
      setOcupadoId(null)
    }
  }

  const colunas = [
    {
      title: 'Cargo',
      dataIndex: 'nome',
      render: (nome, c) => (
        <Typography.Text
          editable={
            !somenteLeitura && ocupadoId !== c.id
              ? {
                  tooltip: 'Renomear',
                  maxLength: 80,
                  onChange: (novo) => novo.trim() && novo.trim() !== nome && alterar(c, { nome: novo.trim() }, 'Cargo renomeado.'),
                }
              : false
          }
        >
          {nome}
        </Typography.Text>
      ),
    },
    {
      title: 'Ativo',
      dataIndex: 'ativo',
      width: 72,
      render: (ativo, c) =>
        somenteLeitura ? (
          <EtiquetaSituacao ativo={ativo} />
        ) : (
          <Switch
            size="small"
            checked={ativo}
            loading={ocupadoId === c.id}
            aria-label={`Cargo ${c.nome} ativo`}
            onChange={(v) => alterar(c, { ativo: v }, v ? 'Cargo reativado.' : 'Cargo inativado.')}
          />
        ),
    },
    !somenteLeitura && {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      width: 48,
      align: 'right',
      render: (_, c) => (
        <Popconfirm
          title="Excluir este cargo?"
          description="Só dá para excluir cargo sem funcionários. Com funcionários, inative-o."
          okText="Excluir"
          okButtonProps={{ danger: true }}
          cancelText="Cancelar"
          onConfirm={() => excluir(c)}
        >
          <Tooltip title="Excluir">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} disabled={ocupadoId === c.id} aria-label={`Excluir o cargo ${c.nome}`} />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ].filter(Boolean)

  return (
    <PainelLateral titulo="Cargos" nome="Cargos da loja" icone={<TagsOutlined />} open={open} onClose={onClose}>
      <div className="pilha">
        {!somenteLeitura && (
          <Form form={form} layout="inline" onFinish={adicionar} disabled={adicionando} className="form-em-linha" colon={false}>
            <Form.Item name="nome" label="Novo cargo" rules={[{ required: true, whitespace: true, message: 'Informe o nome do cargo' }]}>
              <Input maxLength={80} placeholder="Ex.: Dentista" />
            </Form.Item>
            <Button htmlType="submit" icon={<PlusOutlined />} loading={adicionando}>
              Adicionar
            </Button>
          </Form>
        )}
        <Tabela
          size="small"
          pagination={false}
          columns={colunas}
          dataSource={cargos.itens}
          loading={cargos.carregando || cargos.atualizando}
          vazio={
            cargos.erro ? (
              <EstadoVazio
                icone={<DisconnectOutlined />}
                titulo="Não foi possível carregar os cargos"
                descricao={cargos.erro.mensagem}
                acao={<Button onClick={cargos.recarregar}>Tentar de novo</Button>}
              />
            ) : (
              'Nenhum cargo cadastrado'
            )
          }
        />
      </div>
    </PainelLateral>
  )
}

// Cargos em uso na loja, com o atalho para gerenciar
function ResumoCargos({ cargos, somenteLeitura, onGerenciar }) {
  const ativos = cargos.itens.filter((c) => c.ativo)
  return (
    <Secao
      titulo="Cargos"
      descricao="Aparecem no cadastro de cada funcionário. Quem define o acesso é o perfil."
      acoes={
        <Button icon={<TagsOutlined />} onClick={onGerenciar}>
          {somenteLeitura ? 'Ver cargos' : 'Gerenciar cargos'}
        </Button>
      }
    >
      {cargos.erro ? (
        <span className="texto-apoio">Não foi possível carregar os cargos. {cargos.erro.mensagem}</span>
      ) : ativos.length ? (
        <Flex wrap gap={8}>
          {ativos.map((c) => (
            <Etiqueta key={c.id} tom="contorno">
              {c.nome}
            </Etiqueta>
          ))}
        </Flex>
      ) : (
        !cargos.carregando && <span className="texto-apoio">Nenhum cargo ativo.</span>
      )}
    </Secao>
  )
}

export default function Funcionarios() {
  const { pode, nivel, perfil: meuPerfil, usuario } = useAcesso()
  const podeVer = pode('funcionarios')
  const somenteLeitura = !pode('funcionarios', 'escrita')
  const funcionarios = useFuncionarios({ ativo: podeVer })
  const perfis = usePerfis({ ativo: podeVer })
  const cargos = useCargos({ ativo: podeVer })
  const [painelCargos, setPainelCargos] = useState(false)
  const souAdmin = !!meuPerfil?.acessoTotal
  // Teto para atribuir perfis: os níveis gravados no meu perfil (a API compara esses, sem o efeito dos
  // módulos desligados); se a lista não trouxer, o nível efetivo da sessão
  const meusNiveis = perfis.itens.find((p) => p.id === meuPerfil?.id)?.acessos
  const teto = (codigo) => (meusNiveis ? (meusNiveis[codigo] ?? 'nenhum') : nivel(codigo))

  const colunas = [
    {
      title: 'Nome',
      dataIndex: 'nome',
      sorter: (a, b) => a.nome.localeCompare(b.nome),
      render: (nome, f) => (
        <span className="com-ponto">
          <PontoCor cor={f.cor ?? COR_PADRAO} />
          <strong>{nome}</strong>
        </span>
      ),
    },
    {
      title: 'Cargo',
      dataIndex: 'cargoNome',
      filters: cargos.itens.map((c) => ({ text: c.nome, value: c.id })),
      onFilter: (id, f) => f.cargoId === id,
      render: (nome) => nome ?? '—',
    },
    {
      title: 'Perfil',
      dataIndex: 'perfilNome',
      render: (nome, f) =>
        f.perfilAcessoTotal ? (
          <Etiqueta tom="tinta" icone={<LockOutlined />}>
            {nome ?? '—'}
          </Etiqueta>
        ) : (
          <Etiqueta tom="contorno">{nome ?? '—'}</Etiqueta>
        ),
    },
    { title: 'E-mail (login)', dataIndex: 'email' },
    { title: 'Telefone', dataIndex: 'telefone', render: (t) => t ?? '—' },
    { title: 'Situação', dataIndex: 'ativo', render: (ativo) => <EtiquetaSituacao ativo={ativo} /> },
  ]

  return (
    <>
      <CadastroTabela
        titulo="Funcionários"
        descricao="Quem trabalha na loja. O perfil de cada um define o que ele acessa e a jornada de trabalho."
        item="funcionário"
        lista={funcionarios}
        colunas={colunas}
        somenteLeitura={somenteLeitura}
        permitirExcluir={false}
        valoresNovo={{ cor: coresAgenda[0], ativo: true }}
        corRegistro={(f) => f.cor ?? COR_PADRAO}
        mapaErros={MAPA_ERROS_FUNCIONARIO}
        antes={<ResumoCargos cargos={cargos} somenteLeitura={somenteLeitura} onGerenciar={() => setPainelCargos(true)} />}
        campos={
          <>
            <h3 className="grupo-formulario">Dados do funcionário</h3>
            <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
              <Input maxLength={150} />
            </Form.Item>
            <Row gutter={12}>
              <Col xs={24} sm={12}>
                <CampoCargo cargos={cargos} />
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="telefone" label="Telefone" normalize={mascaraTelefone}>
                  <Input inputMode="tel" placeholder="Opcional" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="cpf"
              label="CPF"
              normalize={mascaraCpf}
              validateTrigger="onBlur"
              rules={[
                {
                  validator: (_, v) =>
                    !v || soDigitos(v).length === 11 ? Promise.resolve() : Promise.reject(new Error('CPF incompleto: são 11 dígitos')),
                },
              ]}
            >
              <Input inputMode="numeric" placeholder="Opcional" />
            </Form.Item>

            <h3 className="grupo-formulario">Acesso ao sistema</h3>
            <Form.Item
              name="email"
              label="E-mail (login)"
              validateTrigger="onBlur"
              rules={[
                { required: true, message: 'Informe o e-mail de login' },
                { type: 'email', message: 'E-mail inválido. Confira o @ e o domínio' },
              ]}
            >
              <Input type="email" autoComplete="off" />
            </Form.Item>
            <CampoSenha />
            <CampoPerfil perfis={perfis} funcionarios={funcionarios} souAdmin={souAdmin} teto={teto} meuId={usuario?.id} />
            <Form.Item name="ativo" label="Ativo" valuePropName="checked" extra="Inativo não entra no sistema.">
              <Switch />
            </Form.Item>

            <h3 className="grupo-formulario">Agenda</h3>
            {/* Sem cor (null) o seletor mostra a cor de quem não tem cor na agenda; o valor continua null até escolher */}
            <Form.Item
              name="cor"
              label="Cor na agenda"
              getValueFromEvent={(cor) => cor.toHexString()}
              getValueProps={(cor) => ({ value: cor ?? COR_PADRAO })}
            >
              <ColorPicker disabledAlpha presets={[{ label: 'Sugestões', colors: coresAgenda }]} />
            </Form.Item>
            {/* Só para saber se é edição (ver useIdEmEdicao); fica no fim para não roubar o foco do primeiro campo */}
            <Form.Item name="id" hidden>
              <Input />
            </Form.Item>
          </>
        }
      />
      <PainelCargos open={painelCargos} onClose={() => setPainelCargos(false)} cargos={cargos} somenteLeitura={somenteLeitura} />
    </>
  )
}
