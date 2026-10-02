import { Table, Tag, TimePicker, Typography, message } from 'antd'
import { useData } from '../../data/DataContext.jsx'

// Segunda a domingo
const dias = [
  [1, 'Segunda'],
  [2, 'Terça'],
  [3, 'Quarta'],
  [4, 'Quinta'],
  [5, 'Sexta'],
  [6, 'Sábado'],
  [0, 'Domingo'],
]

// Jornada semanal do perfil (2.5): vale para todos os funcionários vinculados a ele
export default function JornadaPerfil({ perfil, somenteLeitura }) {
  const { jornadas } = useData()
  const [msg, contextHolder] = message.useMessage()

  const faixasDoDia = (dia) =>
    jornadas.itens
      .filter((j) => j.perfilId === perfil.id && j.diaSemana === dia)
      .sort((a, b) => a.inicio.localeCompare(b.inicio))

  const adicionarFaixa = (dia, intervalo) => {
    if (!intervalo) return
    const [inicio, fim] = intervalo.map((h) => h.format('HH:mm'))
    if (fim <= inicio) {
      msg.error('O fim deve ser depois do início.')
      return
    }
    if (faixasDoDia(dia).some((f) => inicio < f.fim && fim > f.inicio)) {
      msg.error('Essa faixa se sobrepõe a outra do mesmo dia.')
      return
    }
    jornadas.adicionar({ perfilId: perfil.id, diaSemana: dia, inicio, fim })
  }

  const colunas = [
    { title: 'Dia', dataIndex: 'nome', width: 110 },
    {
      title: 'Horários',
      key: 'faixas',
      render: (_, { dia }) => {
        const faixas = faixasDoDia(dia)
        if (!faixas.length) return <Tag>Não trabalha</Tag>
        return faixas.map((f) => (
          <Tag
            key={f.id}
            color="blue"
            closable={!somenteLeitura}
            onClose={(e) => {
              e.preventDefault()
              jornadas.remover(f.id)
            }}
          >
            {f.inicio} – {f.fim}
          </Tag>
        ))
      },
    },
    !somenteLeitura && {
      title: 'Adicionar faixa',
      key: 'adicionar',
      width: 230,
      render: (_, { dia }) => (
        <TimePicker.RangePicker
          format="HH:mm"
          minuteStep={15}
          value={null}
          placeholder={['Início', 'Fim']}
          onChange={(intervalo) => adicionarFaixa(dia, intervalo)}
        />
      ),
    },
  ].filter(Boolean)

  return (
    <>
      {contextHolder}
      <Typography.Paragraph type="secondary">
        Todo funcionário com o perfil <b>{perfil.nome}</b> pode ser agendado nestes horários. Quem tem horário diferente
        fica num perfil próprio (ex.: "Profissional · manhã").
      </Typography.Paragraph>
      <Table
        rowKey="dia"
        size="small"
        pagination={false}
        columns={colunas}
        dataSource={dias.map(([dia, nome]) => ({ dia, nome }))}
        scroll={{ x: true }}
      />
    </>
  )
}
