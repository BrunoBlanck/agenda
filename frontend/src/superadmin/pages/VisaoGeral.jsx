import { Row, Col, Card, Statistic, Flex, Tag, Typography, Button, Divider } from 'antd'
import { ShopOutlined, TeamOutlined, DollarOutlined, WarningOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { acoesAuditoria, statusLoja } from '../../data/plataforma.js'
import { moeda } from '../../utils/formatos.js'
import { usePlataforma } from '../usePlataforma.js'

export default function VisaoGeral() {
  const { lojas, tipos, auditoria, superadmins } = useData()
  const { funcionariosDe, plano } = usePlataforma()
  const navigate = useNavigate()

  const ativas = lojas.itens.filter((l) => l.status === 'ativa')
  const suspensas = lojas.itens.filter((l) => l.status === 'suspensa')
  const funcionariosAtivos = ativas.reduce((t, l) => t + funcionariosDe(l).filter((f) => f.ativo).length, 0)
  const receita = ativas.reduce((t, l) => t + (plano(l.planoId)?.precoMensal ?? 0), 0)

  const nomeLoja = (id) => lojas.itens.find((l) => l.id === id)?.nomeFantasia
  const nomeSuperadmin = (id) => superadmins.itens.find((s) => s.id === id)?.nome ?? '—'
  const ultimas = [...auditoria.itens].sort((a, b) => b.criadoEm.localeCompare(a.criadoEm)).slice(0, 6)

  const cards = [
    { titulo: 'Lojas ativas', valor: ativas.length, icone: <ShopOutlined /> },
    { titulo: 'Lojas suspensas', valor: suspensas.length, icone: <WarningOutlined /> },
    { titulo: 'Funcionários ativos', valor: funcionariosAtivos, icone: <TeamOutlined /> },
    { titulo: 'Receita mensal (planos)', valor: moeda(receita), icone: <DollarOutlined /> },
  ]

  return (
    <Row gutter={[16, 16]}>
      {cards.map((c) => (
        <Col key={c.titulo} xs={24} sm={12} xl={6}>
          <Card>
            <Statistic title={c.titulo} value={c.valor} prefix={c.icone} />
          </Card>
        </Col>
      ))}

      <Col xs={24} xl={8}>
        <Card title="Lojas por tipo" style={{ height: '100%' }}>
          <Flex vertical gap={12}>
            {tipos.itens.map((t) => {
              const doTipo = lojas.itens.filter((l) => l.tipo === t.codigo)
              return (
                <Flex key={t.id} justify="space-between" align="center">
                  <Typography.Text strong>{t.nome}</Typography.Text>
                  <Flex gap={4}>
                    {Object.entries(statusLoja).map(([codigo, s]) => {
                      const n = doTipo.filter((l) => l.status === codigo).length
                      return n > 0 && <Tag key={codigo} color={s.color}>{n} {s.label.toLowerCase()}{n > 1 ? 's' : ''}</Tag>
                    })}
                    {doTipo.length === 0 && <Typography.Text type="secondary">nenhuma</Typography.Text>}
                  </Flex>
                </Flex>
              )
            })}
          </Flex>
        </Card>
      </Col>

      <Col xs={24} xl={8}>
        <Card title="Módulos opcionais nas lojas ativas" style={{ height: '100%' }}>
          <Flex vertical gap={12}>
            {modulos
              .filter((m) => m.opcional)
              .map((m) => {
                const n = ativas.filter((l) => l.modulos?.[m.codigo]).length
                return (
                  <Flex key={m.codigo} justify="space-between">
                    <Typography.Text strong>{m.nome}</Typography.Text>
                    <Typography.Text type="secondary">
                      {n} de {ativas.length} lojas
                    </Typography.Text>
                  </Flex>
                )
              })}
          </Flex>
        </Card>
      </Col>

      <Col xs={24} xl={8}>
        <Card
          title="Últimas ações"
          style={{ height: '100%' }}
          extra={<Button type="link" onClick={() => navigate('/superadmin/auditoria')}>Ver tudo</Button>}
        >
          <Flex vertical>
            {ultimas.map((a, i) => (
              <div key={a.id}>
                {i > 0 && <Divider style={{ margin: '10px 0' }} />}
                <Flex justify="space-between" gap={8}>
                  <Tag color={acoesAuditoria[a.acao]?.color}>{acoesAuditoria[a.acao]?.label ?? a.acao}</Tag>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {dayjs(a.criadoEm).format('DD/MM HH:mm')}
                  </Typography.Text>
                </Flex>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {nomeSuperadmin(a.superadminId)}
                  {a.lojaId && ` · ${nomeLoja(a.lojaId)}`}
                </Typography.Text>
              </div>
            ))}
          </Flex>
        </Card>
      </Col>
    </Row>
  )
}
