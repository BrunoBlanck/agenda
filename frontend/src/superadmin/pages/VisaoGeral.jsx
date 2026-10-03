import { Button, Skeleton } from 'antd'
import { DisconnectOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { tiposLoja } from '../../data/dominio.js'
import { dataBR, moeda, plural } from '../../utils/formatos.js'
import { lerDataHora } from '../../data/api/conversao.js'
import { useVisaoGeral } from '../usePlataforma.js'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import Tabela from '../../components/base/Tabela.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import { EtiquetaLoja, EtiquetaOperacao } from '../../components/Etiquetas.jsx'

const DESCRICAO = 'Situação das lojas da plataforma e da receita dos planos.'

export default function VisaoGeral() {
  const { visao, carregando, erro, recarregar } = useVisaoGeral()
  const navigate = useNavigate()

  if (carregando) {
    return (
      <Pagina titulo="Visão geral" descricao={DESCRICAO}>
        <Secao>
          <Skeleton active paragraph={{ rows: 6 }} />
        </Secao>
      </Pagina>
    )
  }

  if (!visao) {
    return (
      <Pagina titulo="Visão geral" descricao={DESCRICAO}>
        <Secao>
          <EstadoVazio
            icone={<DisconnectOutlined />}
            titulo="Não foi possível carregar a visão geral"
            descricao={erro?.mensagem}
            acao={<Button onClick={recarregar}>Tentar de novo</Button>}
          />
        </Secao>
      </Pagina>
    )
  }

  const { suspensas = [], totalSuspensas = 0, modulosExpirando, modulosEmUso, ultimasAcoes } = visao
  const abrirLoja = (id) => navigate(`/superadmin/lojas/${id}`)

  // Tipos conhecidos primeiro (na ordem do domínio); um tipo novo da API aparece com o próprio código
  const codigosTipo = [...new Set([...Object.keys(tiposLoja), ...Object.keys(visao.lojasPorTipo)])]
  const porTipo = codigosTipo.map((codigo) => {
    const contagem = visao.lojasPorTipo[codigo] ?? {}
    return {
      id: codigo,
      nome: tiposLoja[codigo]?.nome ?? codigo,
      ativa: contagem.ativa ?? 0,
      suspensa: contagem.suspensa ?? 0,
      cancelada: contagem.cancelada ?? 0,
    }
  })

  const numero = (n) => (n ? n : <span className="texto-apoio">0</span>)
  const ativas = visao.lojasAtivas

  return (
    <Pagina titulo="Visão geral" descricao={DESCRICAO}>
      <div className="numeros-resumo">
        <div>
          <span>Lojas ativas</span>
          <strong>{ativas}</strong>
        </div>
        <div>
          <span>Lojas suspensas</span>
          <strong>{visao.lojasSuspensas}</strong>
        </div>
        <div>
          <span>Funcionários nas lojas ativas</span>
          <strong>{visao.funcionariosAtivos}</strong>
        </div>
        <div>
          <span>Receita mensal dos planos</span>
          <strong>{moeda(visao.receitaMensal)}</strong>
        </div>
      </div>

      <div className="grade-principal">
        <div className="pilha">
          <Secao titulo="Precisa de atenção">
            {suspensas.length + modulosExpirando.length === 0 ? (
              <EstadoVazio compacto titulo="Nada pendente" descricao="Nenhuma loja suspensa nem módulo perto de vencer." />
            ) : (
              <ul className="lista-linhas lista-compacta">
                {suspensas.map((l) => (
                  <li key={l.id}>
                    <button type="button" className="link-tabela" onClick={() => abrirLoja(l.id)}>
                      {l.nomeFantasia}
                    </button>
                    <EtiquetaLoja status={l.status} />
                  </li>
                ))}
                {totalSuspensas > suspensas.length && (
                  <li>
                    <button type="button" className="link-tabela" onClick={() => navigate('/superadmin/lojas?status=suspensa')}>
                      Ver as {totalSuspensas} lojas suspensas
                    </button>
                  </li>
                )}
                {modulosExpirando.map((m) => (
                  <li key={`${m.lojaId}-${m.codigo}`}>
                    <button type="button" className="link-tabela" onClick={() => abrirLoja(m.lojaId)}>
                      {m.lojaNome}
                    </button>
                    <span className="texto-apoio">
                      {m.nome} {m.vencido ? 'venceu em' : 'vence em'} {dataBR(m.expiraEm)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Secao>

          <Secao rente titulo="Lojas por tipo">
            <Tabela
              size="small"
              pagination={false}
              dataSource={porTipo}
              columns={[
                { title: 'Tipo', dataIndex: 'nome', render: (n) => <strong>{n}</strong> },
                { title: 'Ativas', dataIndex: 'ativa', align: 'right', render: numero },
                { title: 'Suspensas', dataIndex: 'suspensa', align: 'right', render: numero },
                { title: 'Canceladas', dataIndex: 'cancelada', align: 'right', render: numero },
              ]}
            />
          </Secao>

          <Secao titulo="Módulos opcionais em uso" descricao={`Entre as ${plural(ativas, 'loja ativa', 'lojas ativas')}.`}>
            {modulosEmUso.length ? (
              <ul className="lista-linhas lista-compacta">
                {modulosEmUso.map((m) => (
                  <li key={m.codigo} className="uso-modulo">
                    <span>{m.nome}</span>
                    <span className="uso-modulo-barra" aria-hidden="true">
                      <span style={{ width: `${ativas ? Math.min(100, (m.lojas / ativas) * 100) : 0}%` }} />
                    </span>
                    <span className="numeros">
                      {m.lojas} de {ativas}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EstadoVazio compacto titulo="Nenhum módulo opcional cadastrado" />
            )}
          </Secao>
        </div>

        <Secao
          titulo="Últimas ações dos admins"
          acoes={
            <Button type="link" size="small" onClick={() => navigate('/superadmin/auditoria')}>
              Abrir auditoria
            </Button>
          }
        >
          {ultimasAcoes.length ? (
            <ul className="lista-linhas acoes-admin">
              {ultimasAcoes.map((a) => (
                <li key={a.id}>
                  <div className="acoes-admin-topo">
                    <EtiquetaOperacao operacao={a.operacao} />
                    <span>{a.tabelaNome}</span>
                    <span className="texto-apoio numeros">{lerDataHora(a.criadoEm)?.format('DD/MM HH:mm') ?? '—'}</span>
                  </div>
                  <span className="texto-apoio">
                    {a.superadminNome ?? 'Superadmin'}
                    {a.lojaId ? ` em ${a.lojaNome ?? 'loja excluída'}` : ', na plataforma'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EstadoVazio compacto titulo="Nenhuma ação registrada" />
          )}
        </Secao>
      </div>
    </Pagina>
  )
}
