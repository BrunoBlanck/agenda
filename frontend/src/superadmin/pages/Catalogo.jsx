import { Alert, Card, Col, Row, Table, Tag, Typography } from 'antd'
import { modulos, recursos } from '../../data/acesso.js'

const nomeModulo = (codigo) => modulos.find((m) => m.codigo === codigo)?.nome

// Catálogos globais: funcionalidades (1.4) e recursos com nível de acesso (1.8)
export default function Catalogo() {
  return (
    <Row gutter={[16, 16]}>
      <Col span={24}>
        <Alert
          type="info"
          showIcon
          title="Estes catálogos mudam junto com o sistema (um módulo ou tela nova entra aqui). Nesta prévia ficam só para consulta."
        />
      </Col>
      <Col xs={24} xl={8}>
        <Card title="Módulos (funcionalidades)">
          <Table
            rowKey="codigo"
            size="small"
            pagination={false}
            dataSource={modulos}
            columns={[
              { title: 'Módulo', dataIndex: 'nome' },
              { title: 'Código', dataIndex: 'codigo', render: (c) => <code>{c}</code> },
              {
                title: 'Tipo',
                dataIndex: 'opcional',
                render: (o) => (o ? <Tag color="cyan">Opcional por loja</Tag> : <Tag>Base</Tag>),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} xl={16}>
        <Card title="Recursos (níveis de acesso dos perfis)">
          <Table
            rowKey="codigo"
            size="small"
            pagination={false}
            dataSource={recursos}
            scroll={{ x: true }}
            columns={[
              {
                title: 'Recurso',
                key: 'recurso',
                render: (_, r) => (
                  <>
                    <Typography.Text strong>{r.nome}</Typography.Text>
                    <br />
                    <code>{r.codigo}</code>
                  </>
                ),
              },
              { title: 'Módulo', dataIndex: 'modulo', render: (m) => <Tag>{nomeModulo(m)}</Tag> },
              { title: 'Leitura permite', dataIndex: 'leitura' },
              { title: 'Escrita permite', dataIndex: 'escrita' },
            ]}
          />
        </Card>
      </Col>
    </Row>
  )
}
