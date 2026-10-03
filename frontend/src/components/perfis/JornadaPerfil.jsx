import { useState } from 'react'
import { App, Button, Tag, TimePicker } from 'antd'
import { DisconnectOutlined } from '@ant-design/icons'
import { useJornada } from '../../data/usePerfis.js'
import { useTratarErro } from '../../data/api/useTratarErro.js'
import Tabela from '../base/Tabela.jsx'
import EstadoVazio from '../base/EstadoVazio.jsx'

// Segunda a domingo (dia_semana da API: 0 = domingo ... 6 = sábado)
const dias = [
  [1, 'Segunda'],
  [2, 'Terça'],
  [3, 'Quarta'],
  [4, 'Quinta'],
  [5, 'Sexta'],
  [6, 'Sábado'],
  [0, 'Domingo'],
].map(([dia, nome]) => ({ dia, nome }))

// Jornada semanal do perfil (2.5): vale para todos os funcionários vinculados a ele.
// aoAlterar: avisado depois de incluir ou remover uma faixa (ex.: o perfil deixa de estar "sem jornada").
export default function JornadaPerfil({ perfil, somenteLeitura, aoAlterar }) {
  const jornada = useJornada(perfil.id)
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  // Dia com faixa sendo incluída e faixa sendo removida: trava só o que está em andamento
  const [incluindoDia, setIncluindoDia] = useState(null)
  const [removendoId, setRemovendoId] = useState(null)

  const faixasDoDia = (dia) =>
    jornada.itens.filter((j) => j.diaSemana === dia).sort((a, b) => a.inicio.localeCompare(b.inicio))

  const adicionarFaixa = async (dia, intervalo) => {
    if (!intervalo?.[0] || !intervalo?.[1]) return
    const [inicio, fim] = intervalo.map((h) => h.format('HH:mm'))
    // Conferência rápida antes de enviar; quem decide é a API (422/409 com a mensagem dela)
    if (fim <= inicio) {
      message.error('O fim precisa ser depois do início.')
      return
    }
    if (faixasDoDia(dia).some((f) => inicio < f.fim && fim > f.inicio)) {
      message.error('Essa faixa se sobrepõe a outra do mesmo dia. Ajuste o horário.')
      return
    }
    if (incluindoDia !== null) return
    // Enquanto inclui, a tabela fica em carregamento (cobre os campos e evita envio duplo)
    setIncluindoDia(dia)
    try {
      await jornada.adicionar({ diaSemana: dia, inicio, fim })
      aoAlterar?.()
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: jornada.recarregar, aoConflito: jornada.recarregar })
    } finally {
      setIncluindoDia(null)
    }
  }

  const removerFaixa = async (faixa) => {
    setRemovendoId(faixa.id)
    try {
      await jornada.remover(faixa.id)
      aoAlterar?.()
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: jornada.recarregar })
    } finally {
      setRemovendoId(null)
    }
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
            closable={!somenteLeitura && removendoId !== f.id}
            aria-busy={removendoId === f.id}
            onClose={(e) => {
              e.preventDefault()
              removerFaixa(f)
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
      {jornada.erro && !jornada.itens.length ? (
        <EstadoVazio
          icone={<DisconnectOutlined />}
          titulo="Não foi possível carregar a jornada"
          descricao={jornada.erro.mensagem}
          acao={<Button onClick={jornada.recarregar}>Tentar de novo</Button>}
        />
      ) : (
        <Tabela
          rowKey="dia"
          size="small"
          pagination={false}
          columns={colunas}
          dataSource={dias}
          loading={jornada.carregando || jornada.atualizando || incluindoDia !== null}
        />
      )}
    </div>
  )
}
