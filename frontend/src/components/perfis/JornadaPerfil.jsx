import { App, Tag, TimePicker } from 'antd'
import { useData } from '../../data/DataContext.jsx'
import Tabela from '../base/Tabela.jsx'

// Segunda a domingo
const dias = [
  [1, 'Segunda'],
  [2, 'Terça'],
  [3, 'Quarta'],
  [4, 'Quinta'],
  [5, 'Sexta'],
  [6, 'Sábado'],
  [0, 'Domingo'],
].map(([dia, nome]) => ({ dia, nome }))

// Jornada semanal do perfil (2.5): vale para todos os funcionários vinculados a ele
export default function JornadaPerfil({ perfil, somenteLeitura }) {
  const { jornadas } = useData()
  const { message } = App.useApp()

  const faixasDoDia = (dia) =>
    jornadas.itens
      .filter((j) => j.perfilId === perfil.id && j.diaSemana === dia)
      .sort((a, b) => a.inicio.localeCompare(b.inicio))

  const adicionarFaixa = (dia, intervalo) => {
    if (!intervalo) return
    const [inicio, fim] = intervalo.map((h) => h.format('HH:mm'))
    if (fim <= inicio) {
      message.error('O fim precisa ser depois do início.')
      return
    }
    if (faixasDoDia(dia).some((f) => inicio < f.fim && fim > f.inicio)) {
      message.error('Essa faixa se sobrepõe a outra do mesmo dia. Ajuste o horário.')
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
        if (!faixas.length) return <span className="texto-apoio">Folga</span>
        return faixas.map((f) => (
          <Tag
            key={f.id}
            closable={!somenteLeitura}
            onClose={(e) => {
              e.preventDefault()
              jornadas.remover(f.id)
            }}
          >
            {f.inicio} às {f.fim}
          </Tag>
        ))
      },
    },
    !somenteLeitura && {
      title: 'Adicionar faixa',
      key: 'adicionar',
      width: 240,
      render: (_, { dia, nome }) => (
        <TimePicker.RangePicker
          format="HH:mm"
          minuteStep={15}
          value={null}
          placeholder={['Início', 'Fim']}
          aria-label={`Adicionar faixa de horário: ${nome}`}
          onChange={(intervalo) => adicionarFaixa(dia, intervalo)}
        />
      ),
    },
  ].filter(Boolean)

  return (
    <div className="pilha">
      <p className="texto-ajuda">
        Todo funcionário com o perfil <strong>{perfil.nome}</strong> pode ser agendado nestes horários. Quem tem
        horário diferente fica num perfil próprio (ex.: "Profissional manhã").
      </p>
      <Tabela rowKey="dia" size="small" pagination={false} columns={colunas} dataSource={dias} />
    </div>
  )
}
