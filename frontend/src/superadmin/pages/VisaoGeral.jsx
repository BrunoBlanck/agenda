import { Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { useData } from '../../data/DataContext.jsx'
import { modulos } from '../../data/acesso.js'
import { tabelasLoja, tabelasPlataforma, tiposLoja } from '../../data/plataforma.js'
import { moeda, plural } from '../../utils/formatos.js'
import { usePlataforma } from '../usePlataforma.js'
import Pagina from '../../components/base/Pagina.jsx'
import Secao from '../../components/base/Secao.jsx'
import Tabela from '../../components/base/Tabela.jsx'
import EstadoVazio from '../../components/base/EstadoVazio.jsx'
import { EtiquetaLoja, EtiquetaOperacao } from '../../components/Etiquetas.jsx'

const opcionais = modulos.filter((m) => m.opcional)
const nomeTabela = (t) => tabelasLoja[t] ?? tabelasPlataforma[t] ?? t

export default function VisaoGeral() {
  const { lojas, historico, superadmins } = useData()
  const { funcionariosDe, plano } = usePlataforma()
  const navigate = useNavigate()

  const ativas = lojas.itens.filter((l) => l.status === 'ativa')
  const suspensas = lojas.itens.filter((l) => l.status === 'suspensa')
  const funcionariosAtivos = ativas.reduce((t, l) => t + funcionariosDe(l).filter((f) => f.ativo).length, 0)
  const receita = ativas.reduce((t, l) => t + (plano(l.planoId)?.precoMensal ?? 0), 0)

  // Módulos liberados com prazo que vence nos próximos 30 dias
  const expirando = lojas.itens.flatMap((l) =>
    Object.entries(l.modulosInfo ?? {})
      .filter(([codigo, info]) => l.modulos?.[codigo] && info.expiraEm && dayjs(info.expiraEm).diff(dayjs(), 'day') <= 30)
      .map(([codigo, info]) => ({ loja: l, codigo, expiraEm: info.expiraEm })),
  )

  const nomeLoja = (id) => lojas.todos.find((l) => l.id === id)?.nomeFantasia
  const nomeSuperadmin = (id) => superadmins.todos.find((s) => s.id === id)?.nome ?? '—'
  // Últimas alterações feitas pelos usuários admin, em qualquer loja
  const ultimas = historico
    .filter((h) => h.superadminId)
    .sort((a, b) => b.criadoEm.localeCompare(a.criadoEm))
    .slice(0, 6)

  const porTipo = Object.entries(tiposLoja).map(([codigo, t]) => {
    const doTipo = lojas.itens.filter((l) => l.tipo === codigo)
    const contar = (status) => doTipo.filter((l) => l.status === status).length
    return { id: codigo, nome: t.nome, ativa: contar('ativa'), suspensa: contar('suspensa'), cancelada: contar('cancelada') }
  })

  const numero = (n) => (n ? n : <span className="texto-apoio">0</span>)

  return (
    <Pagina titulo="Visão geral" descricao="Situação das lojas da plataforma e da receita dos planos.">
      <div className="numeros-resumo">
        <div>
          <span>Lojas ativas</span>
          <strong>{ativas.length}</strong>
        </div>
        <div>
          <span>Lojas suspensas</span>
          <strong>{suspensas.length}</strong>
        </div>
        <div>
          <span>Funcionários nas lojas ativas</span>
          <strong>{funcionariosAtivos}</strong>
        </div>
        <div>
          <span>Receita mensal dos planos</span>
          <strong>{moeda(receita)}</strong>
        </div>
      </div>

      <div className="grade-principal">
        <div className="pilha">
          <Secao titulo="Precisa de atenção">
            {suspensas.length + expirando.length === 0 ? (
              <EstadoVazio compacto titulo="Nada pendente" descricao="Nenhuma loja suspensa nem módulo perto de vencer." />
            ) : (
              <ul className="lista-linhas lista-compacta">
                {suspensas.map((l) => (
                  <li key={l.id}>
                    <button type="button" className="link-tabela" onClick={() => navigate(`/superadmin/lojas/${l.id}`)}>
                      {l.nomeFantasia}
                    </button>
                    <EtiquetaLoja status={l.status} />
                  </li>
                ))}
                {expirando.map((e) => (
                  <li key={`${e.loja.id}-${e.codigo}`}>
                    <button type="button" className="link-tabela" onClick={() => navigate(`/superadmin/lojas/${e.loja.id}`)}>
                      {e.loja.nomeFantasia}
                    </button>
                    <span className="texto-apoio">
                      {modulos.find((m) => m.codigo === e.codigo)?.nome} vence em {dayjs(e.expiraEm).format('DD/MM/YYYY')}
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

          <Secao titulo="Módulos opcionais em uso" descricao={`Entre as ${plural(ativas.length, 'loja ativa', 'lojas ativas')}.`}>
            <ul className="lista-linhas lista-compacta">
              {opcionais.map((m) => {
                const n = ativas.filter((l) => l.modulos?.[m.codigo]).length
                return (
                  <li key={m.codigo} className="uso-modulo">
                    <span>{m.nome}</span>
                    <span className="uso-modulo-barra" aria-hidden="true">
                      <span style={{ width: `${ativas.length ? (n / ativas.length) * 100 : 0}%` }} />
                    </span>
                    <span className="numeros">
                      {n} de {ativas.length}
                    </span>
                  </li>
                )
              })}
            </ul>
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
          {ultimas.length ? (
            <ul className="lista-linhas acoes-admin">
              {ultimas.map((a) => (
                <li key={a.id}>
                  <div className="acoes-admin-topo">
                    <EtiquetaOperacao operacao={a.operacao} />
                    <span>{nomeTabela(a.tabela)}</span>
                    <span className="texto-apoio numeros">{dayjs(a.criadoEm).format('DD/MM HH:mm')}</span>
                  </div>
                  <span className="texto-apoio">
                    {nomeSuperadmin(a.superadminId)}
                    {a.lojaId ? ` em ${nomeLoja(a.lojaId)}` : ', na plataforma'}
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
