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
  StopOutlined,
  UserDeleteOutlined,
} from '@ant-design/icons'
import Etiqueta from './base/Etiqueta.jsx'
import { statusAgendamento, tiposLocal } from '../data/mock.js'
import { niveis } from '../data/acesso.js'
import { operacoesHistorico, statusLoja } from '../data/plataforma.js'

// Etiquetas do domínio: o mesmo status tem sempre o mesmo texto, tom e ícone em todo o sistema

const iconesStatus = {
  pendente: <ClockCircleOutlined />,
  agendado: <CalendarOutlined />,
  confirmado: <CheckCircleOutlined />,
  concluido: <CheckOutlined />,
  cancelado: <CloseCircleOutlined />,
  nao_compareceu: <UserDeleteOutlined />,
}

export function EtiquetaStatus({ status }) {
  const s = statusAgendamento[status]
  if (!s) return null
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
  const s = statusLoja[status]
  if (!s) return null
  return (
    <Etiqueta tom={s.tom} icone={iconesLoja[status]}>
      {s.label}
    </Etiqueta>
  )
}

const iconesOperacao = { inserir: <PlusCircleOutlined />, alterar: <EditOutlined />, excluir: <CloseCircleOutlined /> }

export function EtiquetaOperacao({ operacao }) {
  const o = operacoesHistorico[operacao]
  if (!o) return null
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
