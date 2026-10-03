import { Button, Form, Select } from 'antd'
import { AuditOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { PLATAFORMA } from '../../data/dominio.js'
import { useOpcoesLojas } from '../usePlataforma.js'
import { EtiquetaLoja } from '../../components/Etiquetas.jsx'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import HistoricoAlteracoes from '../HistoricoAlteracoes.jsx'

// Auditoria: sempre uma loja por vez. Escolhe a loja, a tabela e o período e vê o que mudou e quem fez.
export default function Auditoria() {
  const [params, setParams] = useSearchParams()
  const { opcoes, carregando, erro, recarregar } = useOpcoesLojas()
  // ?loja=<uuid> ou ?loja=plataforma (o id é texto: uuid, nunca número)
  const lojaId = params.get('loja') || null

  const escolher = (valor) => setParams(valor ? { loja: valor } : {}, { replace: true })

  return (
    <Pagina titulo="Auditoria" descricao="O que mudou em cada loja, quando e quem fez. Nada é apagado de verdade: exclusões também ficam aqui.">
      <Secao>
        <Form layout="vertical" className="auditoria-loja">
          <Form.Item
            label="Loja"
            validateStatus={erro ? 'error' : undefined}
            help={
              erro && (
                <span>
                  {erro.mensagem}{' '}
                  <Button type="link" size="small" onClick={recarregar}>
                    Tentar de novo
                  </Button>
                </span>
              )
            }
          >
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="Escolha a loja"
              loading={carregando}
              value={lojaId}
              onChange={escolher}
              options={[
                ...opcoes.map((l) => ({
                  value: l.id,
                  label: l.nome,
                  title: l.slug,
                })),
                { value: PLATAFORMA, label: 'Plataforma (planos e usuários admin)' },
                // Loja da URL que não está na lista (excluída): não mostra o uuid cru
                ...(lojaId && lojaId !== PLATAFORMA && !carregando && !opcoes.some((l) => l.id === lojaId)
                  ? [{ value: lojaId, label: 'Loja fora da lista (excluída)' }]
                  : []),
              ]}
              optionRender={(opcao) =>
                opcao.value === PLATAFORMA ? (
                  opcao.label
                ) : (
                  <span className="com-ponto">
                    {opcao.label}
                    {opcoes.find((l) => l.id === opcao.value)?.status !== 'ativa' && (
                      <EtiquetaLoja status={opcoes.find((l) => l.id === opcao.value)?.status} />
                    )}
                  </span>
                )
              }
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
