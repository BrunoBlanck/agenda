import { useState } from 'react'
import { Card, Empty, Flex, Select, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { useData } from '../../data/DataContext.jsx'
import { PLATAFORMA } from '../../data/plataforma.js'
import HistoricoAlteracoes from '../HistoricoAlteracoes.jsx'

// Auditoria: sempre uma loja por vez. Escolhe a loja, a tabela e o período e vê o que mudou e quem fez.
export default function Auditoria() {
  const { lojas } = useData()
  const [params] = useSearchParams()
  const [lojaId, setLojaId] = useState(() => {
    const inicial = params.get('loja')
    return inicial === PLATAFORMA ? PLATAFORMA : inicial ? Number(inicial) : null
  })

  return (
    <Card>
      <Flex vertical gap={16}>
        <Flex align="center" gap={12} wrap>
          <Typography.Text strong>Loja</Typography.Text>
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Escolha a loja"
            style={{ width: 300 }}
            value={lojaId}
            onChange={setLojaId}
            options={[
              ...lojas.todos.map((l) => ({ value: l.id, label: l.nomeFantasia })),
              { value: PLATAFORMA, label: 'Plataforma (planos e usuários admin)' },
            ]}
          />
        </Flex>
        {lojaId ? (
          <HistoricoAlteracoes key={lojaId} lojaId={lojaId} />
        ) : (
          <Empty description="Escolha uma loja para ver as alterações" />
        )}
      </Flex>
    </Card>
  )
}
