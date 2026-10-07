"""Ciclo da tarefa de fundo das notificações (NOT-05, NOT-07): lembretes e envio dos e-mails pendentes.

``processar`` é uma função comum (sem asyncio), testável com um ``agora``, um relógio e um provedor de
e-mail quaisquer. Roda com origem ``sistema`` (GER-08/12). As lojas com trabalho
(``notificacoes_lojas_com_trabalho``, migração 0008) são atendidas em paralelo (``LOJAS_EM_PARALELO``):
uma loja com SMTP lento não segura as outras. Para cada loja:

1. **Reserva** (uma transação, com o contexto e o RLS da loja): cria os lembretes da janela, encerra os
   avisos vencidos (A5: lembrete de agendamento que mudou, aviso com mais de 24 h ou de agendamento que já
   começou) e reserva até ``LOTE`` e-mails pendentes com ``FOR UPDATE SKIP LOCKED``. Reservar = somar a
   tentativa e empurrar ``email_proxima_tentativa_em`` para ``momento + RESERVA``, com ``momento`` = o
   relógio **na hora da reserva** (nunca o começo do ciclo). Outro processo não pega a linha nem durante a
   reserva (SKIP LOCKED) nem depois (a data está no futuro). ``RESERVA`` é maior que o pior caso de uma
   loja (``ORCAMENTO_LOJA`` + um envio de ``PRAZO_ENVIO``).
2. **Envio**, fora de qualquer transação (PER-05), pelo SMTP da loja, cada um com prazo total de 15 s. Para
   na primeira falha de conexão (o servidor não responde: os outros nem são tentados) ou quando o orçamento
   de tempo da loja acaba; o que sobrou volta à fila **sem gastar tentativa**.
3. **Resultado** (outra transação), só se a linha ainda tiver a **mesma reserva** (tentativa e data):
   2 enviado; falha temporária volta a 1 com espera crescente (``ESPERAS``); depois da 3ª tentativa, ou
   falha definitiva, 3 com a mensagem tratada.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import definir_contexto, get_sessionmaker
from app.models import Agendamento, Loja, LojaConfiguracao, Notificacao
from app.models.enums import StatusAgendamento
from app.services.acesso import modulos_da_loja
from app.services.cifra import SenhaIlegivel, decifrar
from app.services.envio_email import (
    MSG_SENHA_ILEGIVEL,
    PRAZO_ENVIO,
    ConfigSmtp,
    Email,
    EnvioEmail,
    FalhaEnvio,
    provedor_de_email,
)
from app.services.notificacoes import (
    ENVIADO,
    ERRO,
    ERRO_MAX,
    MSG_SEM_SMTP,
    PENDENTE,
    TIPO_CLIENTE,
    LojaAviso,
    criar_lembretes,
)

log = logging.getLogger('app.notificacoes')

LOTE = 50
TENTATIVAS = 3  # igual ao CHECK de notificacoes.email_tentativas
LOJAS_EM_PARALELO = 4
ESPERA_DO_CICLO = 20.0  # segundos que o ciclo espera as lojas antes de seguir (as atrasadas continuam)
ORCAMENTO_LOJA = 60.0  # segundos de envio por loja em cada ciclo
RESERVA = timedelta(minutes=5)  # tempo da reserva: maior que o pior caso de uma loja
ESPERAS = (timedelta(minutes=1), timedelta(minutes=5))  # depois da 1ª e da 2ª falha
VALIDADE = timedelta(hours=24)  # aviso pendente mais velho que isto não sai mais
MSG_SEM_CONFIRMACAO = 'Não foi possível confirmar o envio.'
MSG_VENCIDO = 'Aviso vencido.'
MSG_LEMBRETE_VENCIDO = 'Aviso vencido: o agendamento mudou.'

if timedelta(seconds=ORCAMENTO_LOJA + 2 * PRAZO_ENVIO) >= RESERVA:
    raise RuntimeError('A reserva precisa cobrir o pior caso de uma loja.')

Relogio = Callable[[], datetime]


def relogio_real() -> datetime:
    return datetime.now(UTC)


@dataclass
class Ciclo:
    lojas: int = 0
    lembretes: int = 0
    enviados: int = 0
    falhas: int = 0

    def somar(self, outro: 'Ciclo') -> None:
        self.lembretes += outro.lembretes
        self.enviados += outro.enviados
        self.falhas += outro.falhas


@dataclass(frozen=True)
class Reservado:
    """Um e-mail reservado; ``tentativa`` e ``reserva`` são o token conferido ao gravar o resultado."""

    id: UUID
    email: Email
    tentativa: int
    reserva: datetime


def config_smtp(configuracao: LojaConfiguracao | None) -> ConfigSmtp | str:
    """O SMTP ativo da loja, com a senha decifrada; ou a mensagem de por que não dá para enviar."""
    if configuracao is None or not configuracao.smtp_ativo:
        return MSG_SEM_SMTP
    senha = None
    if configuracao.smtp_senha_cifrada:
        try:
            senha = decifrar(configuracao.smtp_senha_cifrada)
        except SenhaIlegivel:
            return MSG_SENHA_ILEGIVEL
    return ConfigSmtp(
        servidor=configuracao.smtp_servidor or '',
        porta=configuracao.smtp_porta or 0,
        seguranca='ssl' if configuracao.smtp_seguranca == 'ssl' else 'starttls',
        usuario=configuracao.smtp_usuario,
        senha=senha,
        remetente_email=configuracao.smtp_remetente_email or '',
        remetente_nome=configuracao.smtp_remetente_nome,
    )


def corpo_do_email(n: Notificacao, loja: LojaAviso) -> str:
    """Texto simples (NOT-08). Ao cliente, só o link do próprio site (DIR-003), se houver URL pública."""
    partes = [n.mensagem]
    url = get_settings().url_publica
    if n.tipo == TIPO_CLIENTE and url:
        partes.append(f'Veja os seus horários: {url}/{loja.slug}/conta')
    rodape = loja.nome + (f' · {loja.telefone}' if loja.telefone else '')
    partes.append(f'{rodape}\nMensagem automática: não é preciso responder.')
    return '\n\n'.join(partes) + '\n'


def _encerrar(n: Notificacao, mensagem: str) -> None:
    n.status_email = ERRO
    n.email_erro = mensagem[:ERRO_MAX]
    n.email_proxima_tentativa_em = None


def _vencido(
    n: Notificacao,
    ag: tuple[StatusAgendamento, datetime, datetime | None] | None,
    momento: datetime,
    real: datetime,
) -> str | None:
    """Por que o aviso não deve mais sair (A5), ou None. ``momento`` = a hora do ciclo (compara com a
    agenda); ``real`` = o relógio (compara com ``criado_em``, que é a hora do banco)."""
    if n.evento == 'lembrete':
        if ag is None:
            return MSG_LEMBRETE_VENCIDO
        situacao, inicio, excluido_em = ag
        if (
            excluido_em is not None
            or situacao not in (StatusAgendamento.agendado, StatusAgendamento.confirmado)
            or inicio != n.lembrete_inicio
            or inicio <= momento
        ):
            return MSG_LEMBRETE_VENCIDO
    if n.criado_em < real - VALIDADE:
        return MSG_VENCIDO
    if ag is not None and ag[1] <= momento:
        return MSG_VENCIDO
    return None


def _agendamentos(db: Session, loja_id: UUID, ids: set[UUID]) -> dict[UUID, tuple]:
    if not ids:
        return {}
    linhas = db.execute(
        select(Agendamento.id, Agendamento.status, Agendamento.inicio, Agendamento.excluido_em)
        .where(Agendamento.loja_id == loja_id, Agendamento.id.in_(ids))
        .execution_options(incluir_excluidos=True)
    ).all()
    return {id_: (situacao, inicio, excluido) for id_, situacao, inicio, excluido in linhas}


def _reservar(
    db: Session, loja: LojaAviso, agora: datetime, relogio: Relogio, lote: int
) -> tuple[list[Reservado], ConfigSmtp | None]:
    linhas = db.scalars(
        select(Notificacao)
        .where(
            Notificacao.loja_id == loja.id,
            Notificacao.status_email == PENDENTE,
            Notificacao.email_proxima_tentativa_em <= agora,
            Notificacao.excluido_em.is_(None),
        )
        .order_by(Notificacao.email_proxima_tentativa_em, Notificacao.id)
        .limit(lote)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()
    if not linhas:
        return [], None
    config = config_smtp(db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == loja.id)))
    agendamentos = _agendamentos(db, loja.id, {n.agendamento_id for n in linhas if n.agendamento_id})
    real = relogio()
    momento = max(agora, real)  # o relógio da reserva, não o do começo do ciclo
    reservados = []
    for n in linhas:
        vencido = _vencido(n, agendamentos.get(n.agendamento_id) if n.agendamento_id else None, momento, real)
        if vencido:
            _encerrar(n, vencido)
        elif isinstance(config, str):  # a loja desligou o SMTP ou a senha não abre: não adianta tentar
            _encerrar(n, config)
        elif n.email_tentativas >= TENTATIVAS:  # o processo morreu depois da última tentativa
            _encerrar(n, n.email_erro or MSG_SEM_CONFIRMACAO)
        else:
            n.email_tentativas += 1
            n.email_proxima_tentativa_em = momento + RESERVA
            assunto = f'{n.titulo} · {loja.nome}'
            email = Email(n.email_destino or '', assunto, corpo_do_email(n, loja))
            reservados.append(Reservado(n.id, email, n.email_tentativas, n.email_proxima_tentativa_em))
    db.flush()
    return reservados, config if isinstance(config, ConfigSmtp) and reservados else None


def _da_reserva(db: Session, loja_id: UUID, item: Reservado) -> Notificacao | None:
    """A linha, travada, se ainda for a mesma reserva (senão outro processo já a pegou: não mexe)."""
    return db.scalar(
        select(Notificacao)
        .where(
            Notificacao.id == item.id,
            Notificacao.loja_id == loja_id,
            Notificacao.status_email == PENDENTE,
            Notificacao.email_tentativas == item.tentativa,
            Notificacao.email_proxima_tentativa_em == item.reserva,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _registrar(
    db: Session, loja_id: UUID, item: Reservado, falha: FalhaEnvio | None, momento: datetime
) -> None:
    n = _da_reserva(db, loja_id, item)
    if n is None:
        return
    if falha is None:
        n.status_email = ENVIADO
        n.email_enviado_em = momento
        n.email_erro = None
        n.email_proxima_tentativa_em = None
    elif falha.definitiva or n.email_tentativas >= TENTATIVAS:
        _encerrar(n, falha.mensagem)
    else:
        n.email_erro = falha.mensagem[:ERRO_MAX]
        n.email_proxima_tentativa_em = momento + ESPERAS[min(n.email_tentativas, len(ESPERAS)) - 1]


def _devolver(db: Session, loja_id: UUID, item: Reservado, quando: datetime) -> None:
    """Não foi tentado: volta à fila sem gastar a tentativa."""
    db.execute(
        update(Notificacao)
        .where(
            Notificacao.id == item.id,
            Notificacao.loja_id == loja_id,
            Notificacao.status_email == PENDENTE,
            Notificacao.email_tentativas == item.tentativa,
            Notificacao.email_proxima_tentativa_em == item.reserva,
        )
        .values(email_tentativas=Notificacao.email_tentativas - 1, email_proxima_tentativa_em=quando)
        .execution_options(synchronize_session=False)
    )


def _abrir_loja(db: Session, loja_id: UUID) -> LojaAviso | None:
    definir_contexto(db, origem='sistema', loja_id=loja_id)
    loja = db.scalar(select(Loja).where(Loja.id == loja_id))
    return LojaAviso.de(loja, modulos_da_loja(db, loja_id)) if loja is not None else None


def processar_loja(
    fabrica: sessionmaker[Session],
    loja_id: UUID,
    agora: datetime,
    envio: EnvioEmail,
    lote: int,
    relogio: Relogio = relogio_real,
) -> Ciclo:
    ciclo = Ciclo()
    with fabrica() as db, db.begin():
        loja = _abrir_loja(db, loja_id)
        if loja is None:
            return ciclo
        ciclo.lembretes = criar_lembretes(db, loja, agora)
        reservados, config = _reservar(db, loja, agora, relogio, lote)
    if config is None:
        return ciclo
    resultados: list[tuple[Reservado, FalhaEnvio | None]] = []
    sobra: list[Reservado] = []
    inicio = time.monotonic()
    for posicao, item in enumerate(reservados):
        if time.monotonic() - inicio >= ORCAMENTO_LOJA:  # o resto fica para o próximo ciclo
            sobra = reservados[posicao:]
            break
        try:
            envio.enviar(config, item.email)
        except FalhaEnvio as falha:
            resultados.append((item, falha))
            ciclo.falhas += 1
            if falha.conexao:  # o servidor não responde: nem tenta os outros agora
                sobra = reservados[posicao + 1 :]
                break
        else:
            resultados.append((item, None))
            ciclo.enviados += 1
    with fabrica() as db, db.begin():
        definir_contexto(db, origem='sistema', loja_id=loja_id)
        momento = max(agora, relogio())
        for item, falha in resultados:
            _registrar(db, loja_id, item, falha, momento)
        quando = momento + ESPERAS[0] if resultados and resultados[-1][1] is not None else momento
        for item in sobra:
            _devolver(db, loja_id, item, quando)
    return ciclo


def lojas_com_trabalho(fabrica: sessionmaker[Session], agora: datetime) -> list[UUID]:
    with fabrica() as db, db.begin():
        definir_contexto(db, origem='sistema')
        return list(db.scalars(text('SELECT notificacoes_lojas_com_trabalho(:agora)'), {'agora': agora}))


class Despachante:
    """Lojas em atendimento neste processo, num pool fixo de threads (``LOJAS_EM_PARALELO``).

    O ciclo espera as lojas no máximo ``ESPERA_DO_CICLO`` segundos: uma loja atrasada continua no pool (o
    envio dela tem prazo, então termina sozinha) e **fica fora dos ciclos seguintes até terminar**; as outras
    seguem. O pool é fixo (nenhuma thread nova por ciclo) e cada loja fecha as próprias sessões. Outro
    processo é outro despachante: a reserva no banco impede o envio em dobro entre eles.
    """

    def __init__(self, threads: int = LOJAS_EM_PARALELO) -> None:
        self._threads = threads
        self._pool: ThreadPoolExecutor | None = None
        self._em_andamento: set[UUID] = set()
        self._trava = threading.Lock()

    def em_andamento(self) -> set[UUID]:
        with self._trava:
            return set(self._em_andamento)

    def iniciar(self, loja_id: UUID, tarefa: Callable[[], Ciclo]) -> Future[Ciclo] | None:
        with self._trava:
            if loja_id in self._em_andamento:
                return None
            if self._pool is None:
                self._pool = ThreadPoolExecutor(self._threads, thread_name_prefix='notificacoes')
            self._em_andamento.add(loja_id)

        def rodar() -> Ciclo:
            try:
                return tarefa()
            finally:
                with self._trava:
                    self._em_andamento.discard(loja_id)

        return self._pool.submit(rodar)

    def encerrar(self) -> None:
        """Fim do processo: não começa nada novo (o que está enviando termina dentro do prazo)."""
        with self._trava:
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


DESPACHANTE = Despachante()


def processar(
    fabrica: sessionmaker[Session] | None = None,
    agora: datetime | None = None,
    envio: EnvioEmail | None = None,
    lote: int = LOTE,
    relogio: Relogio | None = None,
    despachante: Despachante | None = None,
    espera: float | None = None,
) -> Ciclo:
    """Um ciclo: lembretes e e-mails das lojas com trabalho, até ``LOJAS_EM_PARALELO`` ao mesmo tempo.

    Espera as lojas no máximo ``espera`` segundos (padrão ``ESPERA_DO_CICLO``); a que passar disso segue em
    segundo plano e não entra nos ciclos seguintes enquanto não terminar (``Ciclo`` conta só as que
    terminaram). Falha de uma loja não para as outras (vai para o log; o próximo ciclo tenta de novo).
    """
    fabrica = fabrica or get_sessionmaker()
    relogio = relogio or relogio_real
    agora = agora or relogio()
    envio = envio or provedor_de_email()
    despachante = despachante or DESPACHANTE
    ciclo = Ciclo()
    lojas = lojas_com_trabalho(fabrica, agora)
    ciclo.lojas = len(lojas)

    def tarefa(loja_id: UUID) -> Callable[[], Ciclo]:
        def uma() -> Ciclo:
            try:
                return processar_loja(fabrica, loja_id, agora, envio, lote, relogio)
            except Exception:
                log.exception('Falha ao processar as notificações da loja %s', loja_id)
                return Ciclo()

        return uma

    futuros = [f for loja_id in lojas if (f := despachante.iniciar(loja_id, tarefa(loja_id))) is not None]
    prontos, _ = wait(futuros, timeout=ESPERA_DO_CICLO if espera is None else espera)
    for futuro in prontos:
        ciclo.somar(futuro.result())
    return ciclo
