import { useState } from 'react'
import { Card, Flex, Select, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { acoesAuditoria } from '../../data/plataforma.js'

// superadmin_auditoria: tudo o que os superadmins fizeram
export default function Auditoria() {
  const { auditoria, lojas, superadmins } = useData()
  const [lojaId, setLojaId] = useState(null)
  const [superadminId, setSuperadminId] = useState(null)
  const [acao, setAcao] = useState(null)

  const dados = auditoria.itens
    .filter((a) => !lojaId || a.lojaId === lojaId)
    .filter((a) => !superadminId || a.superadminId === superadminId)
    .filter((a) => !acao || a.acao === acao)
    .sort((a, b) => b.criadoEm.localeCompare(a.criadoEm))

  return (
    <Card>
      <Flex gap={8} wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Todas as lojas"
          style={{ width: 240 }}
          onChange={setLojaId}
          options={lojas.itens.map((l) => ({ value: l.id, label: l.nomeFantasia }))}
        />
        <Select
          allowClear
          placeholder="Todos os superadmins"
          style={{ width: 200 }}
          onChange={setSuperadminId}
          options={superadmins.itens.map((s) => ({ value: s.id, label: s.nome }))}
        />
        <Select
          allowClear
          placeholder="Todas as ações"
          style={{ width: 240 }}
          onChange={setAcao}
          options={Object.entries(acoesAuditoria).map(([value, a]) => ({ value, label: a.label }))}
        />
      </Flex>
      <Table
        rowKey="id"
        dataSource={dados}
        scroll={{ x: true }}
        columns={[
          { title: 'Quando', dataIndex: 'criadoEm', width: 150, render: (d) => dayjs(d).format('DD/MM/YYYY HH:mm') },
          { title: 'Superadmin', dataIndex: 'superadminId', render: (id) => superadmins.itens.find((s) => s.id === id)?.nome },
          { title: 'Loja', dataIndex: 'lojaId', render: (id) => lojas.itens.find((l) => l.id === id)?.nomeFantasia ?? '—' },
          { title: 'Ação', dataIndex: 'acao', render: (a) => <Tag color={acoesAuditoria[a]?.color}>{acoesAuditoria[a]?.label ?? a}</Tag> },
          { title: 'Detalhes', dataIndex: 'dados', render: (d) => Object.values(d ?? {}).join(' · ') || '—' },
        ]}
      />
    </Card>
  )
}
