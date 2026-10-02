import { useState } from 'react'
import { Alert, App, Button, Form, Input, Popconfirm, Segmented, Select, Tabs, Tooltip, Typography } from 'antd'
import { DeleteOutlined, EyeOutlined, LockOutlined, PlusOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { modulos, niveis, recursos } from '../data/acesso.js'
import JornadaPerfil from '../components/perfis/JornadaPerfil.jsx'
import BloqueiosPerfil from '../components/perfis/BloqueiosPerfil.jsx'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import PainelFormulario from '../components/base/PainelFormulario.jsx'
import { plural } from '../utils/formatos.js'

const opcoesNivel = Object.entries(niveis).map(([value, n]) => ({ value, label: n.label }))
const nomeModulo = (codigo) => modulos.find((m) => m.codigo === codigo)?.nome

// Configurações > Perfis e horários: o perfil reúne os níveis de acesso (2.1 e 2.2), a jornada semanal (2.5)
// e os bloqueios (2.6). O funcionário é vinculado ao perfil uma vez só e herda tudo isso.
export default function PerfisAcesso() {
  const { perfis, funcionarios, jornadas, bloqueios } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const { message } = App.useApp()
  const verAcessos = pode('perfis_acesso')
  const somenteLeitura = !pode('perfis_acesso', 'escrita')
  const verHorarios = pode('config_agendamentos')
  const horariosSomenteLeitura = !pode('config_agendamentos', 'escrita')
  const [selecionadoId, setSelecionadoId] = useState(perfis.itens[0]?.id)
  const [novo, setNovo] = useState(false)
  const [form] = Form.useForm()

  const perfil = perfis.itens.find((p) => p.id === selecionadoId) ?? perfis.itens[0]
  const doPerfil = (id) => funcionarios.itens.filter((f) => f.perfilId === id)
  const bloqueado = somenteLeitura || perfil?.acessoTotal
  const semJornada = (id) => !jornadas.itens.some((j) => j.perfilId === id)

  const definirNivel = (codigo, nivel) => perfis.atualizar(perfil.id, { acessos: { ...perfil.acessos, [codigo]: nivel } })

  // Novo perfil pode partir de outro: copia os níveis e a jornada (útil para o mesmo cargo em outro horário)
  const criar = ({ copiarDe, ...v }) => {
    const base = perfis.itens.find((p) => p.id === copiarDe)
    const id = perfis.adicionar({ ...v, padrao: false, acessos: base && !base.acessoTotal ? { ...base.acessos } : {} })
    jornadas.itens
      .filter((j) => j.perfilId === copiarDe)
      .forEach(({ diaSemana, inicio, fim }) => jornadas.adicionar({ perfilId: id, diaSemana, inicio, fim }))
    setSelecionadoId(id)
    setNovo(false)
    message.success('Perfil criado.')
  }

  // Jornada e bloqueios do perfil saem junto com ele
  const excluir = () => {
    jornadas.itens.filter((j) => j.perfilId === perfil.id).forEach((j) => jornadas.remover(j.id))
    bloqueios.itens.filter((b) => b.perfilId === perfil.id).forEach((b) => bloqueios.remover(b.id))
    perfis.remover(perfil.id)
    setSelecionadoId(perfis.itens.find((p) => p.id !== perfil.id)?.id)
    message.success('Perfil excluído.')
  }

  const colunas = [
    {
      title: 'Área',
      key: 'recurso',
      render: (_, r) => (
        <div className="recurso">
          <strong>{r.nome}</strong>
          <span className="texto-apoio">
            {nomeModulo(r.modulo)}
            {!moduloAtivo(r.modulo) && ' (módulo desligado nesta loja)'}
          </span>
        </div>
      ),
    },
    {
      title: 'O que cada nível permite',
      key: 'descricao',
      render: (_, r) => (
        <div className="recurso texto-ajuda">
          <span>
            <strong>Leitura:</strong> {r.leitura}
          </span>
          <span>
            <strong>Escrita:</strong> {r.escrita}
          </span>
        </div>
      ),
    },
    {
      title: 'Nível',
      key: 'nivel',
      width: 250,
      render: (_, r) => (
        <Segmented
          size="small"
          options={opcoesNivel}
          value={perfil.acessoTotal ? 'escrita' : (perfil.acessos[r.codigo] ?? 'nenhum')}
          disabled={bloqueado}
          aria-label={`Nível de acesso: ${r.nome}`}
          onChange={(nivel) => definirNivel(r.codigo, nivel)}
        />
      ),
    },
  ]

  const abas = [
    verAcessos && {
      key: 'acessos',
      label: 'Níveis de acesso',
      children: (
        <div className="pilha">
          {perfil?.acessoTotal && (
            <Alert type="info" showIcon icon={<LockOutlined />} title="O Administrador tem escrita em tudo o que estiver ativo na loja. Esses níveis não mudam." />
          )}
          <Tabela rowKey="codigo" size="small" pagination={false} scroll={{ x: 760 }} columns={colunas} dataSource={recursos} />
        </div>
      ),
    },
    verHorarios && {
      key: 'jornada',
      label: 'Jornada semanal',
      children: perfil && <JornadaPerfil perfil={perfil} somenteLeitura={horariosSomenteLeitura} />,
    },
    verHorarios && {
      key: 'bloqueios',
      label: 'Bloqueios, folgas e feriados',
      children: perfil && <BloqueiosPerfil perfil={perfil} somenteLeitura={horariosSomenteLeitura} />,
    },
  ].filter(Boolean)

  const botaoExcluir =
    !somenteLeitura &&
    perfil &&
    !perfil.padrao &&
    (doPerfil(perfil.id).length > 0 ? (
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
        <Button danger icon={<DeleteOutlined />}>
          Excluir perfil
        </Button>
      </Popconfirm>
    ))

  const funcionariosDoPerfil = perfil ? doPerfil(perfil.id) : []

  return (
    <Pagina
      titulo="Perfis e horários"
      descricao="Cada perfil reúne o que o funcionário pode acessar, a jornada semanal e as folgas. O funcionário herda tudo do perfil dele."
      acoes={
        somenteLeitura ? (
          <Etiqueta icone={<EyeOutlined />}>Somente leitura</Etiqueta>
        ) : (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setNovo(true)}>
            Novo perfil
          </Button>
        )
      }
    >
      <div className="grade-lista-detalhe">
        <Secao rente titulo="Perfis">
          <ul className="lista-opcoes">
            {perfis.itens.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="opcao-lista"
                  aria-pressed={p.id === perfil?.id}
                  onClick={() => setSelecionadoId(p.id)}
                >
                  <span className="opcao-lista-titulo">
                    {p.acessoTotal && <LockOutlined aria-label="Acesso total" />}
                    {p.nome}
                  </span>
                  {p.descricao && <span className="texto-apoio">{p.descricao}</span>}
                  <span className="opcao-lista-meta">
                    <span className="texto-apoio">{plural(doPerfil(p.id).length, 'funcionário', 'funcionários')}</span>
                    {p.padrao && <Etiqueta tom="contorno">Padrão</Etiqueta>}
                    {verHorarios && semJornada(p.id) && <Etiqueta tom="atencao">Sem jornada</Etiqueta>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Secao>

        {perfil && (
          <Secao
            titulo={
              <Typography.Text
                className="titulo-editavel"
                editable={!somenteLeitura && !perfil.padrao ? { onChange: (nome) => nome.trim() && perfis.atualizar(perfil.id, { nome: nome.trim() }), tooltip: 'Renomear' } : false}
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
            <Tabs items={abas} />
          </Secao>
        )}
      </div>

      <PainelFormulario titulo="Novo perfil" open={novo} form={form} textoSalvar="Criar perfil" onCancelar={() => setNovo(false)} onSalvar={criar}>
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
          <Input.TextArea rows={2} placeholder="Para que serve este perfil" />
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
