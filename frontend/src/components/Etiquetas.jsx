import {
  CalendarOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  MinusCircleOutlined,
  PauseCircleOutlined,
  PlusCircleOutlined,
  RollbackOutlined,
  StopOutlined,
  UserDeleteOutlined,
} from '@ant-design/icons'
import Etiqueta from './base/Etiqueta.jsx'
import { niveis } from '../data/acesso.js'
import { operacoesHistorico, statusAgendamento, statusLoja, tiposLocal } from '../data/dominio.js'

// Etiquetas do domínio: o mesmo status tem sempre o mesmo texto, tom e ícone em todo o sistema

const iconesStatus = {
  pendente: <ClockCircleOutlined />,
  agendado: <CalendarOutlined />,
  confirmado: <CheckCircleOutlined />,
  concluido: <CheckOutlined />,
  cancelado: <CloseCircleOutlined />,
  nao_compareceu: <UserDeleteOutlined />,
}

// Valor que a tela não conhece (enum novo na API): rótulo neutro com o próprio código, sem quebrar
const desconhecido = (valor) => ({ label: String(valor ?? '—').replace(/_/g, ' '), tom: 'neutro' })

export function EtiquetaStatus({ status }) {
  if (!status) return null
  const s = statusAgendamento[status] ?? desconhecido(status)
  return (
    <Etiqueta tom={s.tom} icone={iconesStatus[status]}>
      {s.label}
    </Etiqueta>
  )
}

export function EtiquetaSituacao({ ativo, ativoTexto = 'Ativo', inativoTexto = 'Inativo' }) {
  return ativo ? (
    <Etiqueta tom="sucesso" icone={<CheckCircleOutlined />}>
      {ativoTexto}
    </Etiqueta>
  ) : (
    <Etiqueta icone={<MinusCircleOutlined />}>{inativoTexto}</Etiqueta>
  )
}

const iconesLoja = { ativa: <CheckCircleOutlined />, suspensa: <PauseCircleOutlined />, cancelada: <StopOutlined /> }

export function EtiquetaLoja({ status }) {
  if (!status) return null
  const s = statusLoja[status] ?? desconhecido(status)
  return (
    <Etiqueta tom={s.tom} icone={iconesLoja[status]}>
      {s.label}
    </Etiqueta>
  )
}

const iconesOperacao = {
  inserir: <PlusCircleOutlined />,
  alterar: <EditOutlined />,
  excluir: <CloseCircleOutlined />,
  restaurar: <RollbackOutlined />,
}

export function EtiquetaOperacao({ operacao }) {
  if (!operacao) return null
  const o = operacoesHistorico[operacao] ?? desconhecido(operacao)
  return (
    <Etiqueta tom={o.tom} icone={iconesOperacao[operacao]}>
      {o.label}
    </Etiqueta>
  )
}

export function EtiquetaTipoLocal({ tipo }) {
  const t = tiposLocal[tipo] ?? tiposLocal.presencial
  return <Etiqueta tom={t.tom}>{t.label}</Etiqueta>
}

export function EtiquetaNivel({ nivel }) {
  const n = niveis[nivel] ?? niveis.nenhum
  return <Etiqueta tom={n.tom}>{n.label}</Etiqueta>
}
