"""Notificações (NOT-01 a NOT-08): criação nos fatos da agenda, sino do painel e lembretes.

- **Criação** (NOT-01): uma linha em ``notificacoes`` na **mesma transação** do fato (se a mudança de status
  não grava, o aviso também não), com título e mensagem congelados. As funções ``avisar_*`` são chamadas
  pelos serviços da agenda (painel e site) depois do ``flush`` do agendamento.
- **Quem recebe:** cliente do agendamento (NOT-02) ou **só o profissional** do agendamento, se ativo
  (NOT-03). Ações do próprio cliente no site não geram aviso de cancelamento para ele.
- **Canais** (NOT-04): site 1 (não visualizada); e-mail 1 (pendente, a tarefa de fundo envia), 3 (loja sem
  SMTP ativo) ou 4 (destinatário sem e-mail); WhatsApp sempre 4 por enquanto.
- **Textos** (NOT-08): datas no fuso da loja; sem o módulo Serviços, "Atendimento"; sem Locais, sem local;
  nunca o motivo do cancelamento (SIT-21) nem link do local.
- **Lembrete** (NOT-05): ``criar_lembretes`` (tarefa de fundo), um por (agendamento, início lembrado).
- **Sino do painel** (NOT-06): cada funcionário lê e marca só as suas (``tipo = loja``).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, and_, exists, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Agendamento, Cliente, Funcionario, Local, Loja, LojaConfiguracao, Notificacao, Servico
from app.models.enums import StatusAgendamento
from app.schemas.comum import Paginacao
from app.services.comum import fuso

S = StatusAgendamento

# Status por canal (NOT-04)
NAO_VISUALIZADA, VISUALIZADA = 1, 2
PENDENTE, ENVIADO, ERRO, DADO_FALTANDO = 1, 2, 3, 4

TIPO_CLIENTE, TIPO_LOJA = 'cliente', 'loja'
NOME_SEM_SERVICO = 'Atendimento'
ANTECEDENCIA_PADRAO = 120  # minutos (CFG-05), igual ao DEFAULT da coluna

MSG_SEM_EMAIL = 'Cadastro sem e-mail.'
MSG_SEM_SMTP = 'O envio de e-mail da loja não está configurado.'
MSG_WHATSAPP = 'Envio por WhatsApp ainda não disponível.'

TITULO_MAX, MENSAGEM_MAX, ERRO_MAX = 120, 1000, 300
SEMANA_CURTA = ('seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom')


# --- Loja e textos ---------------------------------------------------------------------------------


@dataclass
class LojaAviso:
    """O que os textos e os canais precisam saber da loja (lido uma vez por transação)."""

    id: UUID
    slug: str
    nome: str
    telefone: str | None
    zona: ZoneInfo
    usa_servicos: bool
    usa_locais: bool
    _smtp_ativo: bool | None = field(default=None, repr=False)

    @classmethod
    def de(cls, loja: Loja, modulos: dict[str, bool]) -> 'LojaAviso':
        return cls(
            id=loja.id,
            slug=loja.slug,
            nome=_uma_linha(loja.nome_fantasia or loja.nome),
            telefone=loja.telefone,
            zona=fuso(loja.fuso_horario),
            usa_servicos=modulos.get('servicos', False),
            usa_locais=modulos.get('locais', False),
        )

    def smtp_ativo(self, db: Session) -> bool:
        if self._smtp_ativo is None:
            ativo = db.scalar(select(LojaConfiguracao.smtp_ativo).where(LojaConfiguracao.loja_id == self.id))
            self._smtp_ativo = bool(ativo)
        return self._smtp_ativo


def _uma_linha(texto: str) -> str:
    return ' '.join(texto.split())


def _cortar(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + '…'


def hora(momento: datetime) -> str:
    """Hora no padrão do painel (UI-18): "9h30", "9h", "14h05"."""
    return f'{momento.hour}h{momento.minute:02d}' if momento.minute else f'{momento.hour}h'


def quando(momento: datetime, zona: ZoneInfo) -> str:
    """Ex.: "ter 14/10 às 9h30" (fuso da loja, GER-15)."""
    local = momento.astimezone(zona)
    return f'{SEMANA_CURTA[local.weekday()]} {local:%d/%m} às {hora(local)}'


@dataclass(frozen=True)
class Detalhes:
    """Nomes do agendamento (inclusive de cadastros excluídos depois, para o histórico)."""

    id: UUID
    inicio: datetime
    cliente_id: UUID
    cliente_nome: str
    cliente_email: str | None
    funcionario_id: UUID
    funcionario_nome: str
    servico_nome: str | None
    local_nome: str | None


def _consulta_detalhes(loja_id: UUID) -> Select:
    return (
        select(
            Agendamento.id,
            Agendamento.inicio,
            Cliente.id,
            Cliente.nome,
            Cliente.sobrenome,
            Cliente.email,
            Funcionario.id,
            Funcionario.nome,
            Servico.nome,
            Local.nome,
        )
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .join(
            Funcionario,
            (Funcionario.id == Agendamento.funcionario_id) & (Funcionario.loja_id == Agendamento.loja_id),
        )
        .outerjoin(Servico, (Servico.id == Agendamento.servico_id) & (Servico.loja_id == Agendamento.loja_id))
        .outerjoin(Local, (Local.id == Agendamento.local_id) & (Local.loja_id == Agendamento.loja_id))
        .where(Agendamento.loja_id == loja_id)
        .execution_options(incluir_excluidos=True)
    )


def _detalhes(linha: Any) -> Detalhes:
    ag_id, inicio, cliente_id, nome, sobrenome, email, funcionario_id, prof, servico, local = linha
    return Detalhes(
        id=ag_id,
        inicio=inicio,
        cliente_id=cliente_id,
        cliente_nome=_uma_linha(f'{nome} {sobrenome}'),
        cliente_email=email,
        funcionario_id=funcionario_id,
        funcionario_nome=_uma_linha(prof),
        servico_nome=_uma_linha(servico) if servico else None,
        local_nome=_uma_linha(local) if local else None,
    )


def detalhes_do_agendamento(db: Session, loja_id: UUID, agendamento_id: UUID) -> Detalhes:
    return _detalhes(db.execute(_consulta_detalhes(loja_id).where(Agendamento.id == agendamento_id)).one())


@dataclass(frozen=True)
class Textos:
    loja: LojaAviso
    d: Detalhes

    @property
    def servico(self) -> str:
        return self.d.servico_nome if self.loja.usa_servicos and self.d.servico_nome else NOME_SEM_SERVICO

    @property
    def local(self) -> str:
        return f' ({self.d.local_nome})' if self.loja.usa_locais and self.d.local_nome else ''

    @property
    def quando(self) -> str:
        return quando(self.d.inicio, self.loja.zona)

    @property
    def com(self) -> str:
        """Profissional e local, ex.: " com Ana (Sala 1)"."""
        return f' com {self.d.funcionario_nome}{self.local}'

    @property
    def fale_com_a_loja(self) -> str:
        return f'fale com a loja: {self.loja.telefone}' if self.loja.telefone else 'fale com a loja'


# --- Criação -----------------------------------------------------------------------------------------


def _canal_email(db: Session, loja: LojaAviso, destino: str | None) -> dict[str, Any]:
    if not destino:
        return {'status_email': DADO_FALTANDO, 'email_destino': None, 'email_erro': MSG_SEM_EMAIL}
    if not loja.smtp_ativo(db):
        return {'status_email': ERRO, 'email_destino': destino, 'email_erro': MSG_SEM_SMTP}
    return {'status_email': PENDENTE, 'email_destino': destino}


def _valores(
    db: Session,
    loja: LojaAviso,
    *,
    tipo: str,
    evento: str,
    titulo: str,
    mensagem: str,
    agendamento_id: UUID | None,
    cliente_id: UUID | None = None,
    funcionario_id: UUID | None = None,
    email: str | None,
    agora: datetime | None = None,
) -> dict[str, Any]:
    canal = _canal_email(db, loja, email)
    if canal['status_email'] == PENDENTE:
        canal['email_proxima_tentativa_em'] = agora if agora is not None else func.now()
    return {
        'loja_id': loja.id,
        'tipo': tipo,
        'cliente_id': cliente_id,
        'funcionario_id': funcionario_id,
        'agendamento_id': agendamento_id,
        'evento': evento,
        'titulo': _cortar(titulo, TITULO_MAX),
        'mensagem': _cortar(mensagem, MENSAGEM_MAX),
        'status_whatsapp': DADO_FALTANDO,
        'whatsapp_erro': MSG_WHATSAPP,
        **canal,
    }


def _para_cliente(db: Session, loja: LojaAviso, d: Detalhes, evento: str, titulo: str, mensagem: str) -> None:
    valores = _valores(
        db,
        loja,
        tipo=TIPO_CLIENTE,
        evento=evento,
        titulo=titulo,
        mensagem=mensagem,
        agendamento_id=d.id,
        cliente_id=d.cliente_id,
        email=d.cliente_email,
    )
    db.execute(insert(Notificacao).values(**valores))


def _para_profissional(
    db: Session, loja: LojaAviso, funcionario_id: UUID, d: Detalhes, evento: str, titulo: str, mensagem: str
) -> None:
    """Só o profissional do agendamento, ativo e não excluído (NOT-03)."""
    email = db.scalar(
        select(Funcionario.email).where(
            Funcionario.id == funcionario_id, Funcionario.loja_id == loja.id, Funcionario.ativo
        )
    )
    if email is None:
        return
    valores = _valores(
        db,
        loja,
        tipo=TIPO_LOJA,
        evento=evento,
        titulo=titulo,
        mensagem=mensagem,
        agendamento_id=d.id,
        funcionario_id=funcionario_id,
        email=email,
    )
    db.execute(insert(Notificacao).values(**valores))


# --- Eventos do painel (NOT-02) --------------------------------------------------------------------


def avisar_criado_no_painel(db: Session, loja: LojaAviso, ag: Agendamento) -> None:
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    _para_cliente(
        db,
        loja,
        t.d,
        'agendamento_criado',
        'Horário agendado',
        f'{loja.nome} agendou {t.servico} para {t.quando}{t.com}.',
    )


def avisar_mudanca_de_status(
    db: Session, loja: LojaAviso, ag: Agendamento, anterior: StatusAgendamento
) -> None:
    """A loja confirmou, recusou ou cancelou (reabertura, concluir e não compareceu não avisam)."""
    if ag.status not in (S.confirmado, S.cancelado):
        return
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    if ag.status == S.confirmado:
        _para_cliente(
            db,
            loja,
            t.d,
            'confirmado',
            'Horário confirmado',
            f'{loja.nome} confirmou {t.servico} em {t.quando}{t.com}.',
        )
    elif anterior == S.pendente:
        _para_cliente(
            db,
            loja,
            t.d,
            'cancelado',
            'Pedido não confirmado',
            f'{loja.nome} não pôde confirmar o seu pedido de {t.servico} para {t.quando}. '
            f'Escolha outro horário ou {t.fale_com_a_loja}.',
        )
    else:
        _para_cliente(
            db,
            loja,
            t.d,
            'cancelado',
            'Horário cancelado',
            f'{loja.nome} cancelou {t.servico} de {t.quando}. Para remarcar, {t.fale_com_a_loja}.',
        )


def avisar_horario_alterado(db: Session, loja: LojaAviso, ag: Agendamento) -> None:
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    _para_cliente(
        db,
        loja,
        t.d,
        'horario_alterado',
        'Horário alterado',
        f'{loja.nome} alterou o seu horário de {t.servico}: agora é {t.quando}{t.com}.',
    )


# --- Eventos do site (NOT-02, NOT-03) ----------------------------------------------------------------


def avisar_pedido_do_site(db: Session, loja: LojaAviso, ag: Agendamento) -> None:
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    _para_cliente(
        db,
        loja,
        t.d,
        'pedido_recebido',
        'Pedido recebido',
        f'Recebemos o seu pedido de {t.servico} para {t.quando}{t.com}. {loja.nome} vai confirmar o horário.',
    )
    _para_profissional(
        db,
        loja,
        t.d.funcionario_id,
        t.d,
        'novo_pedido',
        'Novo pedido pelo site',
        f'{t.d.cliente_nome} pediu {t.servico} para {t.quando}.',
    )


@dataclass(frozen=True)
class HorarioAnterior:
    funcionario_id: UUID
    inicio: datetime


def avisar_remarcacao_do_site(db: Session, loja: LojaAviso, ag: Agendamento, antes: HorarioAnterior) -> None:
    """Cliente: pedido de remarcação recebido. Profissional novo: remarcação pedida; se o profissional
    mudou, o antigo recebe "remarcou para outro profissional" (NOT-03)."""
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    antigo = quando(antes.inicio, loja.zona)
    _para_cliente(
        db,
        loja,
        t.d,
        'pedido_recebido',
        'Pedido de remarcação recebido',
        f'Recebemos o seu pedido para remarcar {t.servico} para {t.quando}{t.com}. '
        f'{loja.nome} vai confirmar o novo horário.',
    )
    _para_profissional(
        db,
        loja,
        t.d.funcionario_id,
        t.d,
        'remarcacao_pedida',
        'Remarcação pedida pelo site',
        f'{t.d.cliente_nome} pediu para remarcar {t.servico} de {antigo} para {t.quando}.',
    )
    if antes.funcionario_id != t.d.funcionario_id:
        _para_profissional(
            db,
            loja,
            antes.funcionario_id,
            t.d,
            'cancelado_pelo_cliente',
            'Cancelado pelo cliente',
            f'{t.d.cliente_nome} remarcou {t.servico} de {antigo} para outro profissional.',
        )


def avisar_cancelamento_do_site(db: Session, loja: LojaAviso, ag: Agendamento) -> None:
    t = Textos(loja, detalhes_do_agendamento(db, loja.id, ag.id))
    _para_profissional(
        db,
        loja,
        t.d.funcionario_id,
        t.d,
        'cancelado_pelo_cliente',
        'Cancelado pelo cliente',
        f'{t.d.cliente_nome} cancelou {t.servico} de {t.quando} pelo site.',
    )


# --- Lembrete (NOT-05) -------------------------------------------------------------------------------


def antecedencia_da_loja(db: Session, loja_id: UUID) -> int:
    """Minutos de antecedência do cliente (CFG-05); sem a linha de configurações, o padrão."""
    minutos = db.scalar(
        select(LojaConfiguracao.antecedencia_cliente_minutos).where(LojaConfiguracao.loja_id == loja_id)
    )
    return ANTECEDENCIA_PADRAO if minutos is None else minutos


def _sem_lembrete() -> ColumnElement[bool]:
    return ~exists().where(
        Notificacao.loja_id == Agendamento.loja_id,
        Notificacao.agendamento_id == Agendamento.id,
        Notificacao.evento == 'lembrete',
        Notificacao.lembrete_inicio == Agendamento.inicio,
        Notificacao.excluido_em.is_(None),
    )


def criar_lembretes(db: Session, loja: LojaAviso, agora: datetime) -> int:
    """Um lembrete para cada agendamento ``agendado``/``confirmado`` com ``inicio − antecedência ≤ agora <
    inicio`` que ainda não foi lembrado naquele início. O índice único garante um só, mesmo com vários
    processos (``ON CONFLICT DO NOTHING``). Devolve quantos foram criados."""
    minutos = antecedencia_da_loja(db, loja.id)
    if minutos <= 0:
        return 0
    linhas = db.execute(
        _consulta_detalhes(loja.id).where(
            Agendamento.status.in_((S.agendado, S.confirmado)),
            Agendamento.excluido_em.is_(None),
            Cliente.excluido_em.is_(None),
            Agendamento.inicio > agora,
            Agendamento.inicio <= agora + timedelta(minutes=minutos),
            _sem_lembrete(),
        )
    ).all()
    criados = 0
    for linha in linhas:
        t = Textos(loja, _detalhes(linha))
        valores = _valores(
            db,
            loja,
            tipo=TIPO_CLIENTE,
            evento='lembrete',
            titulo='Lembrete do seu horário',
            mensagem=f'Seu horário de {t.servico} é {t.quando}{t.com}. {loja.nome} espera por você.',
            agendamento_id=t.d.id,
            cliente_id=t.d.cliente_id,
            email=t.d.cliente_email,
            agora=agora,
        )
        resultado = db.execute(
            insert(Notificacao)
            .values(**valores, lembrete_inicio=t.d.inicio)
            .on_conflict_do_nothing(
                index_elements=['loja_id', 'agendamento_id', 'lembrete_inicio'],
                index_where=text("evento = 'lembrete' AND excluido_em IS NULL"),
            )
            .returning(Notificacao.id)
        )
        criados += len(resultado.all())
    return criados


# --- Sino do painel (NOT-06) -------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemDoSino:
    notificacao: Notificacao
    agendamento_id: UUID | None  # None se o agendamento foi excluído
    inicio_agendamento: datetime | None


def _do_funcionario(loja_id: UUID, funcionario_id: UUID) -> list[ColumnElement[bool]]:
    return [
        Notificacao.loja_id == loja_id,
        Notificacao.tipo == TIPO_LOJA,
        Notificacao.funcionario_id == funcionario_id,
        Notificacao.excluido_em.is_(None),
    ]


def nao_visualizadas_do_funcionario(db: Session, loja_id: UUID, funcionario_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notificacao)
            .where(*_do_funcionario(loja_id, funcionario_id), Notificacao.status_site == NAO_VISUALIZADA)
        )
        or 0
    )


def listar_do_funcionario(
    db: Session, loja_id: UUID, funcionario_id: UUID, pag: Paginacao
) -> tuple[list[ItemDoSino], int]:
    """Mais novas primeiro; o agendamento excluído sai como None (sem link na tela)."""
    filtro = _do_funcionario(loja_id, funcionario_id)
    total = db.scalar(select(func.count()).select_from(Notificacao).where(*filtro)) or 0
    linhas = db.execute(
        select(Notificacao, Agendamento.id, Agendamento.inicio)
        .outerjoin(
            Agendamento,
            and_(
                Agendamento.loja_id == Notificacao.loja_id,
                Agendamento.id == Notificacao.agendamento_id,
                Agendamento.excluido_em.is_(None),
            ),
        )
        .where(*filtro)
        .order_by(Notificacao.criado_em.desc(), Notificacao.id.desc())
        .limit(pag.por_pagina)
        .offset(pag.offset)
        .execution_options(incluir_excluidos=True)
    ).all()
    return [ItemDoSino(n, ag_id, inicio) for n, ag_id, inicio in linhas], total


def marcar_do_funcionario(db: Session, loja_id: UUID, funcionario_id: UUID, ids: list[UUID]) -> int:
    """Marca como visualizadas as do funcionário entre ``ids``; as de outro, de outra loja ou inexistentes
    são ignoradas em silêncio. Já visualizada não muda (idempotente). Devolve quantas mudaram."""
    resultado = db.execute(
        update(Notificacao)
        .where(
            *_do_funcionario(loja_id, funcionario_id),
            Notificacao.id.in_(set(ids)),
            Notificacao.status_site == NAO_VISUALIZADA,
        )
        .values(status_site=VISUALIZADA, visualizada_em=func.now())
        .returning(Notificacao.id)
        .execution_options(synchronize_session=False)
    )
    return len(resultado.all())
