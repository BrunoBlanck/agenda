import { useState } from 'react'
import { App, Button, DatePicker, Form, Input, Popconfirm, Select, Tooltip } from 'antd'
import { DeleteOutlined, DisconnectOutlined, PlusOutlined } from '@ant-design/icons'
import { useBloqueios } from '../../data/usePerfis.js'
import { useTratarErro } from '../../data/api/useTratarErro.js'
import Tabela from '../base/Tabela.jsx'
import Etiqueta from '../base/Etiqueta.jsx'
import BarraFiltros from '../base/BarraFiltros.jsx'
import EstadoVazio from '../base/EstadoVazio.jsx'
import PainelFormulario from '../base/PainelFormulario.jsx'

// inicio/fim já vêm como dayjs na hora da loja (data/api/perfis.js)
const periodo = (b) =>
  b.inicio && b.fim ? `${b.inicio.format('DD/MM/YYYY HH:mm')} até ${b.fim.format('DD/MM/YYYY HH:mm')}` : '—'

// "Aplica a": loja, perfil ou f:<id> (um funcionário do perfil; id é uuid)
const PREFIXO_FUNCIONARIO = 'f:'

// O período é um campo só na tela; a API valida início e fim separados
const MAPA_ERROS = { inicio: 'periodo', fim: 'periodo', perfil_id: 'alvo', funcionario_id: 'alvo' }

// Bloqueios, folgas e feriados (2.6) que atingem o perfil: os da loja inteira, os do perfil
// e os de cada funcionário dele (férias, consulta médica...)
export default function BloqueiosPerfil({ perfil, somenteLeitura }) {
  const bloqueios = useBloqueios(perfil.id)
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [aberto, setAberto] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [removendoId, setRemovendoId] = useState(null)
  const [form] = Form.useForm()

  const funcionariosAtivos = perfil.funcionarios.filter((f) => f.ativo)
  const opcoesAlvo = [
    { value: 'perfil', label: `Todo o perfil ${perfil.nome}` },
    ...funcionariosAtivos.map((f) => ({ value: `${PREFIXO_FUNCIONARIO}${f.id}`, label: f.nome })),
    { value: 'loja', label: 'Loja inteira (ex.: feriado)' },
  ]

  const salvar = async (v) => {
    const funcionarioId = v.alvo.startsWith(PREFIXO_FUNCIONARIO) ? v.alvo.slice(PREFIXO_FUNCIONARIO.length) : null
    setSalvando(true)
    try {
      await bloqueios.criar({
        perfilId: v.alvo === 'perfil' ? perfil.id : null,
        funcionarioId,
        inicio: v.periodo[0],
        fim: v.periodo[1],
        motivo: v.motivo,
      })
      message.success('Bloqueio salvo.')
      setAberto(false)
    } catch (e) {
      tratarErro(e, { form, mapa: MAPA_ERROS, aoNaoEncontrado: bloqueios.recarregar })
    } finally {
      setSalvando(false)
    }
  }

  const remover = async (b) => {
    setRemovendoId(b.id)
    try {
      await bloqueios.remover(b.id)
      message.success('Bloqueio removido.')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: bloqueios.recarregar })
    } finally {
      setRemovendoId(null)
    }
  }

  const colunas = [
    {
      title: 'Quem',
      key: 'quem',
      render: (_, b) =>
        b.alvo === 'loja' ? (
          <Etiqueta tom="atencao">Loja inteira</Etiqueta>
        ) : b.alvo === 'perfil' ? (
          <Etiqueta tom="tinta">Todo o perfil</Etiqueta>
        ) : (
          (b.quem ?? '—')
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
          description={b.alvo === 'loja' ? 'Ele vale para a loja inteira, não só para este perfil.' : 'O horário volta a ficar livre na agenda.'}
          okText="Remover"
          okButtonProps={{ danger: true }}
          cancelText="Cancelar"
          onConfirm={() => remover(b)}
        >
          <Tooltip title="Remover">
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={removendoId === b.id}
              aria-label="Remover bloqueio"
            />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ].filter(Boolean)

  const vazio = bloqueios.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar os bloqueios"
      descricao={bloqueios.erro.mensagem}
      acao={<Button onClick={bloqueios.recarregar}>Tentar de novo</Button>}
    />
  ) : (
    'Nenhum bloqueio, folga ou feriado cadastrado'
  )

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
      <Tabela
        size="small"
        pagination={false}
        columns={colunas}
        dataSource={bloqueios.itens}
        loading={bloqueios.carregando || bloqueios.atualizando}
        vazio={vazio}
      />
      <PainelFormulario
        titulo="Novo bloqueio"
        open={aberto}
        form={form}
        valoresIniciais={{ alvo: 'perfil' }}
        salvando={salvando}
        onCancelar={() => setAberto(false)}
        onSalvar={salvar}
      >
        <Form.Item name="alvo" label="Aplica a" rules={[{ required: true, message: 'Escolha a quem o bloqueio se aplica' }]}>
          <Select options={opcoesAlvo} />
        </Form.Item>
        <Form.Item
          name="periodo"
          label="Período"
          rules={[
            { required: true, message: 'Informe o início e o fim' },
            {
              validator: (_, v) =>
                !v?.[0] || !v?.[1] || v[1].isAfter(v[0]) ? Promise.resolve() : Promise.reject(new Error('O fim precisa ser depois do início')),
            },
          ]}
        >
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
