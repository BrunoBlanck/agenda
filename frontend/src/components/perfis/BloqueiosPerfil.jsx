import { useState } from 'react'
import { App, Button, DatePicker, Form, Input, Popconfirm, Select, Tooltip } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { bloqueioDaLoja } from '../../data/horarios.js'
import Tabela from '../base/Tabela.jsx'
import Etiqueta from '../base/Etiqueta.jsx'
import BarraFiltros from '../base/BarraFiltros.jsx'
import PainelFormulario from '../base/PainelFormulario.jsx'

const FORMATO = 'YYYY-MM-DD HH:mm'
const periodo = (b) => `${dayjs(b.inicio).format('DD/MM/YYYY HH:mm')} até ${dayjs(b.fim).format('DD/MM/YYYY HH:mm')}`

// Bloqueios, folgas e feriados (2.6) que atingem o perfil: os da loja inteira, os do perfil
// e os de cada funcionário dele (férias, consulta médica...)
export default function BloqueiosPerfil({ perfil, somenteLeitura }) {
  const { funcionarios, bloqueios } = useData()
  const { message } = App.useApp()
  const [aberto, setAberto] = useState(false)
  const [form] = Form.useForm()

  const doPerfil = funcionarios.itens.filter((f) => f.perfilId === perfil.id)
  const idsDoPerfil = doPerfil.map((f) => f.id)
  const nomeFunc = (id) => funcionarios.todos.find((f) => f.id === id)?.nome ?? '—'

  const lista = bloqueios.itens
    .filter((b) => bloqueioDaLoja(b) || b.perfilId === perfil.id || idsDoPerfil.includes(b.funcionarioId))
    .sort((a, b) => a.inicio.localeCompare(b.inicio))

  // "Aplica a": loja, perfil ou f<id> (um funcionário do perfil)
  const opcoesAlvo = [
    { value: 'perfil', label: `Todo o perfil ${perfil.nome}` },
    ...doPerfil.filter((f) => f.ativo).map((f) => ({ value: `f${f.id}`, label: f.nome })),
    { value: 'loja', label: 'Loja inteira (ex.: feriado)' },
  ]

  const salvar = (v) => {
    bloqueios.adicionar({
      perfilId: v.alvo === 'perfil' ? perfil.id : null,
      funcionarioId: v.alvo.startsWith('f') ? Number(v.alvo.slice(1)) : null,
      inicio: v.periodo[0].format(FORMATO),
      fim: v.periodo[1].format(FORMATO),
      motivo: v.motivo,
    })
    message.success('Bloqueio salvo.')
    setAberto(false)
  }

  const colunas = [
    {
      title: 'Quem',
      key: 'quem',
      render: (_, b) =>
        bloqueioDaLoja(b) ? (
          <Etiqueta tom="atencao">Loja inteira</Etiqueta>
        ) : b.perfilId != null ? (
          <Etiqueta tom="tinta">Todo o perfil</Etiqueta>
        ) : (
          nomeFunc(b.funcionarioId)
        ),
    },
    { title: 'Período', key: 'periodo', render: (_, b) => periodo(b) },
    { title: 'Motivo', dataIndex: 'motivo', render: (m) => m || <span className="texto-apoio">Sem motivo</span> },
    !somenteLeitura && {
      title: <span className="sr-only">Ações</span>,
      key: 'acoes',
      width: 56,
      align: 'right',
      render: (_, b) => (
        <Popconfirm
          title="Remover este bloqueio?"
          description={bloqueioDaLoja(b) ? 'Ele vale para a loja inteira, não só para este perfil.' : 'O horário volta a ficar livre na agenda.'}
          okText="Remover"
          okButtonProps={{ danger: true }}
          cancelText="Cancelar"
          onConfirm={() => bloqueios.remover(b.id)}
        >
          <Tooltip title="Remover">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label="Remover bloqueio" />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ].filter(Boolean)

  return (
    <div className="pilha">
      <BarraFiltros
        acoes={
          !somenteLeitura && (
            <Button icon={<PlusOutlined />} onClick={() => setAberto(true)}>
              Novo bloqueio
            </Button>
          )
        }
      >
        <p className="texto-ajuda">Bloqueios da loja inteira, do perfil e de cada funcionário dele.</p>
      </BarraFiltros>
      <Tabela size="small" pagination={false} columns={colunas} dataSource={lista} vazio="Nenhum bloqueio, folga ou feriado cadastrado" />
      <PainelFormulario
        titulo="Novo bloqueio"
        open={aberto}
        form={form}
        valoresIniciais={{ alvo: 'perfil' }}
        onCancelar={() => setAberto(false)}
        onSalvar={salvar}
      >
        <Form.Item name="alvo" label="Aplica a" rules={[{ required: true }]}>
          <Select options={opcoesAlvo} />
        </Form.Item>
        <Form.Item name="periodo" label="Período" rules={[{ required: true, message: 'Informe o início e o fim' }]}>
          <DatePicker.RangePicker
            showTime={{ format: 'HH:mm', minuteStep: 15 }}
            format="DD/MM/YYYY HH:mm"
            placeholder={['Início', 'Fim']}
          />
        </Form.Item>
        <Form.Item name="motivo" label="Motivo">
          <Input maxLength={150} placeholder="Férias, folga, feriado" />
        </Form.Item>
      </PainelFormulario>
    </div>
  )
}
