import { useState } from 'react'
import { Form, Select } from 'antd'
import { AuditOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { useData } from '../../data/DataContext.jsx'
import { PLATAFORMA } from '../../data/plataforma.js'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
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
    <Pagina titulo="Auditoria" descricao="O que mudou em cada loja, quando e quem fez. Nada é apagado de verdade: exclusões também ficam aqui.">
      <Secao>
        <Form layout="vertical" className="auditoria-loja">
          <Form.Item label="Loja">
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="Escolha a loja"
              value={lojaId}
              onChange={setLojaId}
              options={[
                ...lojas.todos.map((l) => ({ value: l.id, label: l.nomeFantasia })),
                { value: PLATAFORMA, label: 'Plataforma (planos e usuários admin)' },
              ]}
            />
          </Form.Item>
        </Form>
      </Secao>
      {lojaId ? (
        <Secao rente>
          <HistoricoAlteracoes key={lojaId} lojaId={lojaId} />
        </Secao>
      ) : (
        <Secao>
          <EstadoVazio icone={<AuditOutlined />} titulo="Escolha uma loja" descricao="A auditoria mostra uma loja por vez, para a lista não misturar dados de clientes diferentes." />
        </Secao>
      )}
    </Pagina>
  )
}
