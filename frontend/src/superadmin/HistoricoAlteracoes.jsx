import { useState } from 'react'
import { Button, DatePicker, Select } from 'antd'
import { ArrowRightOutlined, DisconnectOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { PLATAFORMA } from '../data/dominio.js'
import { enviarData, lerDataHora } from '../data/api/conversao.js'
import { dataBR, dataHoraBR } from '../utils/formatos.js'
import { useAuditoria, usePessoasAuditoria, useTabelasAuditoria } from './usePlataforma.js'
import BarraFiltros from '../components/base/BarraFiltros.jsx'
import Tabela from '../components/base/Tabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import { EtiquetaOperacao } from '../components/Etiquetas.jsx'

// Colunas de controle e de vínculo interno: não aparecem no retrato do registro (inclusão/exclusão)
const CONTROLE = new Set([
  'id',
  'loja_id',
  'criado_em',
  'atualizado_em',
  'atualizado_por',
  'atualizado_por_funcionario',
  'atualizado_por_superadmin',
  'excluido_em',
  'excluido_por',
  'criado_por_funcionario',
  'criado_por_superadmin',
])

// Nomes das colunas do banco (snake_case, como vêm em `mudancas` e em antes/depois)
const nomesCampos = {
  nome: 'Nome',
  sobrenome: 'Sobrenome',
  nome_fantasia: 'Nome da loja',
  email: 'E-mail',
  telefone: 'Telefone',
  cpf: 'CPF',
  cnpj: 'CNPJ',
  status: 'Situação',
  ativo: 'Ativo',
  descricao: 'Descrição',
  observacao: 'Observação',
  observacoes: 'Observações',
  preco_mensal: 'Preço mensal',
  preco: 'Preço',
  duracao_minutos: 'Duração (min)',
  quantidade: 'Quantidade',
  quantidade_atual: 'Quantidade atual',
  inicio: 'Início',
  fim: 'Fim',
  entrada: 'Entrada',
  saida: 'Saída',
  data_nascimento: 'Nascimento',
  canais: 'Canais',
  perfil_id: 'Perfil',
  cargo_id: 'Cargo',
  cliente_id: 'Cliente',
  funcionario_id: 'Profissional',
  servico_id: 'Serviço',
  local_id: 'Local',
  plano_id: 'Plano',
  categoria_id: 'Categoria',
  material_id: 'Material',
  funcionalidade_id: 'Módulo',
  recurso_id: 'Recurso',
  senha: 'Senha',
  expira_em: 'Expira em',
  habilitado: 'Ligado',
  motivo: 'Motivo',
  tipo: 'Tipo',
  slug: 'Endereço do site',
  fuso_horario: 'Fuso horário',
  cor_agenda: 'Cor na agenda',
  ultimo_login_em: 'Último acesso',
  dia_semana: 'Dia da semana',
  hora_inicio: 'Hora de início',
  hora_fim: 'Hora de fim',
  acesso_total: 'Acesso total',
  nivel: 'Nível',
  estoque_minimo: 'Estoque mínimo',
  unidade: 'Unidade',
  cep: 'CEP',
  logradouro: 'Logradouro',
  numero: 'Número',
  complemento: 'Complemento',
  bairro: 'Bairro',
  cidade: 'Cidade',
  uf: 'UF',
  rotulo_local: 'Rótulo do local',
  rotulo_local_plural: 'Rótulo do local (plural)',
  origem: 'Origem',
}
const nomeCampo = (campo) => nomesCampos[campo] ?? campo.replace(/_/g, ' ')

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const codigoCurto = (id) => (UUID.test(id) ? id.slice(0, 8) : id || '—')

// Valor como veio da linha do banco: datas no fuso da loja (a API já converte), ids encurtados
const formatar = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'Sim' : 'Não'
  if (typeof v === 'number') return v.toLocaleString('pt-BR')
  if (typeof v === 'string') {
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) return dataHoraBR(v)
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return dataBR(v)
    if (/^\d{2}:\d{2}:\d{2}$/.test(v)) return v.slice(0, 5)
    if (UUID.test(v)) return `código ${codigoCurto(v)}`
    return v
  }
  if (Array.isArray(v) && v.every((x) => x === null || typeof x !== 'object')) return v.map(formatar).join(', ') || '—'
  return JSON.stringify(v)
}

// Retrato do registro (inclusão, exclusão, restauração): os campos da linha, sem comparar nada
const retrato = (h) => {
  const linha = (h.operacao === 'excluir' ? (h.antes ?? h.depois) : (h.depois ?? h.antes)) ?? {}
  return Object.entries(linha)
    .filter(([campo]) => !CONTROLE.has(campo))
    .map(([campo, valor]) => ({ campo, valor }))
}

const textoOperacao = {
  inserir: 'Registro criado',
  excluir: 'Registro excluído',
  restaurar: 'Registro restaurado',
}

// Um campo alterado: valor antigo riscado, seta, valor novo
function Mudanca({ antes, depois }) {
  return (
    <span className="mudanca">
      <del>{formatar(antes)}</del>
      <ArrowRightOutlined aria-label="mudou para" />
      <strong>{formatar(depois)}</strong>
    </span>
  )
}

// Atalhos de período: o código vai para a API (os dias são contados no fuso da loja);
// datas escolhidas à mão vão como intervalo.
function atalhosPeriodo() {
  const hoje = dayjs()
  return [
    { chave: 'hoje', label: 'Hoje', value: [hoje, hoje] },
    { chave: '7d', label: 'Últimos 7 dias', value: [hoje.subtract(6, 'day'), hoje] },
    { chave: '30d', label: 'Últimos 30 dias', value: [hoje.subtract(29, 'day'), hoje] },
    { chave: '90d', label: 'Últimos 90 dias', value: [hoje.subtract(89, 'day'), hoje] },
    { chave: 'ano', label: 'Último ano', value: [hoje.subtract(1, 'year'), hoje] },
  ]
}

// Histórico de alterações de uma loja (ou da plataforma): filtros, paginação e "o que mudou" vêm da API.
export default function HistoricoAlteracoes({ lojaId }) {
  const plataforma = lojaId === PLATAFORMA
  const { tabelas: catalogo, carregando: carregandoTabelas } = useTabelasAuditoria()
  const tabelas = (plataforma ? catalogo.plataforma : catalogo.loja) ?? {}
  const [atalhos] = useState(atalhosPeriodo)
  const [tabela, setTabela] = useState(null)
  const [periodo, setPeriodo] = useState({ chave: '30d', datas: atalhos[2].value })
  const [quem, setQuem] = useState(null)
  const [pagina, setPagina] = useState(1)

  const intervalo = periodo.chave === 'intervalo'
  const filtrosBase = {
    loja: lojaId,
    tabela,
    periodo: periodo.chave,
    inicio: intervalo ? enviarData(periodo.datas[0]) : undefined,
    fim: intervalo ? enviarData(periodo.datas[1]) : undefined,
  }
  const auditoria = useAuditoria({ ...filtrosBase, quem, pagina })
  const { pessoas, carregando: carregandoPessoas } = usePessoasAuditoria(filtrosBase)

  const mudarTabela = (t) => {
    setTabela(t ?? null)
    setQuem(null)
    setPagina(1)
  }
  const mudarPeriodo = (datas) => {
    if (!datas?.[0] || !datas?.[1]) return
    const atalho = atalhos.find((a) => a.value[0].isSame(datas[0], 'day') && a.value[1].isSame(datas[1], 'day'))
    setPeriodo({ chave: atalho?.chave ?? 'intervalo', datas })
    setPagina(1)
  }
  const mudarQuem = (q) => {
    setQuem(q ?? null)
    setPagina(1)
  }

  // A pessoa escolhida continua na lista mesmo se não aparecer no período novo
  const opcoesQuem = pessoas.map((p) => ({ value: p.chave, label: p.tipo === 'superadmin' ? `${p.nome} (superadmin)` : p.nome }))

  const colunas = [
    {
      title: 'Quando',
      dataIndex: 'criadoEm',
      width: 150,
      render: (d) => lerDataHora(d)?.format('DD/MM/YYYY HH:mm') ?? '—',
    },
    {
      title: 'Quem',
      key: 'quem',
      render: (_, h) => (
        <span className="com-ponto">
          {h.quem.nome}
          {h.quem.tipo === 'superadmin' && <Etiqueta tom="contorno">Superadmin</Etiqueta>}
          {h.quem.tipo === 'site' && <Etiqueta tom="contorno">Site</Etiqueta>}
        </span>
      ),
    },
    { title: 'Operação', dataIndex: 'operacao', render: (o) => <EtiquetaOperacao operacao={o} /> },
    {
      title: 'Registro',
      key: 'registro',
      render: (_, h) => (
        <span className="recurso">
          <span>{h.rotulo ?? '—'}</span>
          <span className="texto-apoio">
            {tabela ? '' : `${h.tabelaNome}, `}código {codigoCurto(h.registroId)}
          </span>
        </span>
      ),
    },
    {
      title: 'O que mudou',
      key: 'mudancas',
      render: (_, h) => {
        if (h.operacao !== 'alterar') return <span className="texto-apoio">{textoOperacao[h.operacao] ?? '—'}</span>
        if (!h.mudancas.length) return <span className="texto-apoio">Só dados de controle</span>
        return (
          <span className="recurso">
            {h.mudancas.slice(0, 3).map((c) => (
              <span key={c.campo}>
                {nomeCampo(c.campo)}: <Mudanca antes={c.antes} depois={c.depois} />
              </span>
            ))}
            {h.mudancas.length > 3 && <span className="texto-apoio">e mais {h.mudancas.length - 3}</span>}
          </span>
        )
      },
    },
  ]

  const vazio = auditoria.erro ? (
    <EstadoVazio
      icone={<DisconnectOutlined />}
      titulo="Não foi possível carregar o histórico"
      descricao={auditoria.erro.mensagem}
      acao={<Button onClick={auditoria.recarregar}>Tentar de novo</Button>}
    />
  ) : (
    <EstadoVazio
      compacto
      titulo={tabela ? 'Nenhuma alteração nesta tabela no período' : 'Nenhuma alteração no período'}
      descricao="Tente um período maior ou outra tabela."
    />
  )

  return (
    <div className="historico-alteracoes">
      <BarraFiltros>
        <Select
          allowClear
          placeholder="Todas as tabelas"
          aria-label="Tabela"
          loading={carregandoTabelas}
          value={tabela}
          onChange={mudarTabela}
          options={Object.entries(tabelas).map(([value, label]) => ({ value, label }))}
        />
        <DatePicker.RangePicker
          className="busca"
          format="DD/MM/YYYY"
          value={periodo.datas}
          onChange={mudarPeriodo}
          presets={atalhos.map(({ label, value }) => ({ label, value }))}
          allowClear={false}
          aria-label="Período"
        />
        <Select
          allowClear
          placeholder="Todas as pessoas"
          aria-label="Quem fez"
          loading={carregandoPessoas}
          value={quem}
          onChange={mudarQuem}
          options={quem && !opcoesQuem.some((o) => o.value === quem) ? [...opcoesQuem, { value: quem, label: 'Pessoa escolhida' }] : opcoesQuem}
        />
      </BarraFiltros>
      <Tabela
        scroll={{ x: 960 }}
        dataSource={auditoria.erro ? [] : auditoria.itens}
        columns={colunas}
        loading={auditoria.carregando || auditoria.atualizando}
        pagination={{
          current: auditoria.pagina,
          pageSize: auditoria.porPagina,
          total: auditoria.total,
          onChange: setPagina,
          showSizeChanger: false,
          hideOnSinglePage: true,
        }}
        vazio={vazio}
        expandable={{
          rowExpandable: (h) => (h.operacao === 'alterar' ? h.mudancas.length > 0 : retrato(h).length > 0),
          expandedRowRender: (h) =>
            h.operacao === 'alterar' ? (
              <Tabela
                rowKey="campo"
                size="small"
                pagination={false}
                dataSource={h.mudancas}
                columns={[
                  { title: 'Campo', dataIndex: 'campo', width: 200, render: nomeCampo },
                  { title: 'Antes', dataIndex: 'antes', render: formatar },
                  { title: 'Depois', dataIndex: 'depois', render: (v) => <strong>{formatar(v)}</strong> },
                ]}
              />
            ) : (
              <Tabela
                rowKey="campo"
                size="small"
                pagination={false}
                dataSource={retrato(h)}
                columns={[
                  { title: 'Campo', dataIndex: 'campo', width: 200, render: nomeCampo },
                  { title: h.operacao === 'excluir' ? 'Valor ao excluir' : 'Valor', dataIndex: 'valor', render: formatar },
                ]}
              />
            ),
        }}
      />
    </div>
  )
}
