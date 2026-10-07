"""Agendamento pelo site do consumidor (SIT-02 a SIT-08): serviços, horários livres e o pedido.

Uma regra só para os dois caminhos do site: a API pública (``app/routers/site``) e as páginas HTML
(``app/routers/site/paginas.py``). O contexto da transação já fica como ``app.origem = 'site'``, com a
loja e sem funcionário (``carregar_loja_publica``).

Erros: ``invalido`` (422) para escolha que não existe (serviço, profissional, local), ``HorarioIndisponivel``
(409) para horário ou local que deixou de estar livre e ``conflito`` (409) para o limite de pedidos
pendentes por telefone. As páginas HTML tratam cada um de um jeito (voltar ao passo certo).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Agendamento, AgendamentoMaterial, Cliente, Funcionario, Local, Loja, Servico
from app.models.enums import CanalCliente, OrigemAgendamento, StatusAgendamento
from app.schemas.comum import so_digitos
from app.schemas.site import (
    LocalPublico,
    ProfissionalPublico,
    ServicoPublico,
    SolicitacaoEntrada,
    SolicitacaoSaida,
)
from app.services.acesso import modulos_da_loja
from app.services.agendamentos import materiais_do_servico
from app.services.assinatura import assinar_id, ler_id
from app.services.comum import conflito, fuso, invalido, no_fuso
from app.services.horarios_livres import (
    DURACAO_SEM_SERVICO,
    Agenda,
    Livre,
    locais_permitidos,
    profissionais,
    profissionais_por_servico,
)
from app.services.site import carregar_loja_publica

NOME_SEM_SERVICO = 'Atendimento'

MSG_ESCOLHA_SERVICO = 'Escolha o serviço.'
MSG_SERVICO_INVALIDO = 'Serviço não encontrado.'
MSG_PROFISSIONAL_INVALIDO = 'Profissional não encontrado para este serviço.'
MSG_LOCAL_INVALIDO = 'Local não encontrado para este serviço.'
MSG_HORARIO_OCUPADO = 'Este horário não está mais disponível. Escolha outro horário.'
MSG_LOCAL_OCUPADO = 'Este local já está ocupado nesse horário. Escolha outro horário.'
MSG_MUITOS_PENDENTES = (
    'Já há pedidos deste telefone aguardando a confirmação da loja. '
    'Aguarde a resposta antes de pedir outro horário.'
)


class HorarioIndisponivel(HTTPException):
    """O horário (ou o local) escolhido não está mais livre: 409, e o site volta à escolha de horário."""

    def __init__(self, mensagem: str = MSG_HORARIO_OCUPADO) -> None:
        super().__init__(status.HTTP_409_CONFLICT, mensagem)


@dataclass
class ContextoSite:
    db: Session
    loja: Loja
    modulos: dict[str, bool]
    zona: ZoneInfo

    @property
    def usa_servicos(self) -> bool:
        return self.modulos.get('servicos', False)

    @property
    def usa_locais(self) -> bool:
        return self.modulos.get('locais', False)

    @property
    def usa_materiais(self) -> bool:
        return self.modulos.get('materiais', False)

    @property
    def nome_da_loja(self) -> str:
        return self.loja.nome_fantasia or self.loja.nome


def abrir_site(db: Session, slug: str, ip: str | None) -> ContextoSite | None:
    """Contexto do site da loja (SIT-01: só loja ativa), ou None para responder 404."""
    loja = carregar_loja_publica(db, slug, ip)
    if loja is None:
        return None
    return ContextoSite(db=db, loja=loja, modulos=modulos_da_loja(db, loja.id), zona=fuso(loja.fuso_horario))


# --- Serviços e profissionais --------------------------------------------------------------------


def servico_escolhido(ctx: ContextoSite, servico_id: UUID | None, *, travar: bool = False) -> Servico | None:
    """Serviço escolhido (ativo). Sem o módulo Serviços, não há serviço (atendimento genérico, SIT-08).

    travar: FOR KEY SHARE, para o pedido não passar junto com a exclusão do serviço (que usa FOR UPDATE).
    """
    if not ctx.usa_servicos:
        return None
    if servico_id is None:
        raise invalido(MSG_ESCOLHA_SERVICO)
    consulta = select(Servico).where(Servico.id == servico_id, Servico.loja_id == ctx.loja.id, Servico.ativo)
    if travar:
        consulta = consulta.with_for_update(read=True, key_share=True).execution_options(
            populate_existing=True
        )
    servico = ctx.db.scalar(consulta)
    if servico is None:
        raise invalido(MSG_SERVICO_INVALIDO)
    return servico


def duracao_de(servico: Servico | None) -> int:
    return servico.duracao_minutos if servico else DURACAO_SEM_SERVICO


def nome_de(servico: Servico | None) -> str:
    return servico.nome if servico else NOME_SEM_SERVICO


def _publicos(equipe: list[Funcionario]) -> list[ProfissionalPublico]:
    return [ProfissionalPublico.model_validate(f) for f in equipe]


def servicos_publicos(ctx: ContextoSite) -> list[ServicoPublico]:
    """Serviços ativos com quem atende (serviço sem ninguém não aparece). Sem o módulo: "Atendimento"."""
    if not ctx.usa_servicos:
        equipe = profissionais(ctx.db, ctx.loja.id, None)
        return [
            ServicoPublico(
                id=None,
                nome=NOME_SEM_SERVICO,
                duracao_minutos=DURACAO_SEM_SERVICO,
                profissionais=_publicos(equipe),
            )
        ]
    servicos = list(
        ctx.db.scalars(
            select(Servico).where(Servico.loja_id == ctx.loja.id, Servico.ativo).order_by(Servico.nome)
        )
    )
    equipes = profissionais_por_servico(ctx.db, ctx.loja.id, [s.id for s in servicos])
    return [
        ServicoPublico(
            id=servico.id,
            nome=servico.nome,
            descricao=servico.descricao,
            duracao_minutos=servico.duracao_minutos,
            preco=servico.preco,
            profissionais=_publicos(equipes[servico.id]),
        )
        for servico in servicos
        if equipes.get(servico.id)
    ]


# --- Horários livres -----------------------------------------------------------------------------


def agenda_do_periodo(
    ctx: ContextoSite,
    servico: Servico | None,
    funcionario_id: UUID | None,
    primeiro: date,
    ultimo: date,
    local_id: UUID | None = None,
    *,
    ignorar: UUID | None = None,
) -> tuple[Agenda, dict[UUID, Local]]:
    """Agenda do período. ``local_id`` (módulo Locais) restringe os horários aos desse local.

    ``ignorar``: agendamento que não conta como ocupado (o próprio, na remarcação pelo site, SIT-24).
    """
    candidatos = profissionais(ctx.db, ctx.loja.id, servico)
    if funcionario_id is not None:
        candidatos = [f for f in candidatos if f.id == funcionario_id]
        if not candidatos:
            raise invalido(MSG_PROFISSIONAL_INVALIDO)
    locais = locais_permitidos(ctx.db, ctx.loja.id, servico) if ctx.usa_locais else None
    if locais is not None and local_id is not None:
        locais = [local for local in locais if local.id == local_id]
        if not locais:
            raise invalido(MSG_LOCAL_INVALIDO)
    agenda = Agenda(
        ctx.db,
        ctx.loja.id,
        ctx.zona,
        candidatos,
        [local.id for local in locais] if locais is not None else None,
        primeiro,
        ultimo,
        ignorar=ignorar,
    )
    return agenda, {local.id: local for local in locais or []}


def local_publico(locais: dict[UUID, Local], local_id: UUID | None) -> LocalPublico | None:
    return LocalPublico.model_validate(locais[local_id]) if local_id in locais else None


def dias_livres(
    ctx: ContextoSite,
    servico: Servico | None,
    funcionario_id: UUID | None,
    primeiro: date,
    ultimo: date,
    local_id: UUID | None = None,
    *,
    duracao: int | None = None,
    ignorar: UUID | None = None,
) -> tuple[list[tuple[date, list[Livre]]], dict[UUID, Local]]:
    """Horários livres de cada dia do período (o chamador limita o tamanho do período).

    ``duracao`` (minutos): a do serviço quando não informada; ``ignorar``: ver ``agenda_do_periodo``.
    """
    agenda, locais = agenda_do_periodo(
        ctx, servico, funcionario_id, primeiro, ultimo, local_id, ignorar=ignorar
    )
    agora, duracao = datetime.now(UTC), duracao or duracao_de(servico)
    dias = [primeiro + timedelta(days=i) for i in range((ultimo - primeiro).days + 1)]
    return [(dia, agenda.livres_no_dia(dia, duracao, agora)) for dia in dias], locais


@dataclass(frozen=True)
class HorarioEscolhido:
    servico: Servico | None
    livre: Livre
    local_id: UUID | None
    locais: dict[UUID, Local]

    @property
    def local(self) -> LocalPublico | None:
        return local_publico(self.locais, self.local_id)


def horario_oferecido(
    ctx: ContextoSite,
    servico: Servico | None,
    funcionario_id: UUID,
    inicio: datetime,
    local_id: UUID | None = None,
    *,
    duracao: int | None = None,
    ignorar: UUID | None = None,
) -> HorarioEscolhido:
    """O horário precisa ser um dos oferecidos (jornada, bloqueios, antecedência e ocupação, SIT-05).

    ``local_id`` vazio = o primeiro local permitido e livre (SIT-04). Sem o módulo Locais, é ignorado.
    ``duracao`` e ``ignorar``: ver ``dias_livres`` (remarcação pelo site, SIT-24).
    """
    inicio = no_fuso(inicio, ctx.zona)
    dia = inicio.astimezone(ctx.zona).date()
    agenda, locais = agenda_do_periodo(ctx, servico, funcionario_id, dia, dia, ignorar=ignorar)
    livres = agenda.livres_no_dia(dia, duracao or duracao_de(servico), datetime.now(UTC))
    livre = next((h for h in livres if h.inicio == inicio), None)
    if livre is None:
        raise HorarioIndisponivel(MSG_HORARIO_OCUPADO)
    escolhido = livre.local_id
    if local_id is not None and ctx.usa_locais:
        if local_id not in locais:
            raise invalido(MSG_LOCAL_INVALIDO)
        if local_id not in agenda.locais_livres(livre.inicio, livre.fim):
            raise HorarioIndisponivel(MSG_LOCAL_OCUPADO)
        escolhido = local_id
    return HorarioEscolhido(servico=servico, livre=livre, local_id=escolhido, locais=locais)


# --- Pedido de agendamento -----------------------------------------------------------------------


def filtro_telefone(loja_id: UUID, digitos: str) -> ColumnElement[bool]:
    """Clientes da loja com o telefone (só dígitos, SIT-07); índice ``clientes_telefone_digitos_idx``."""
    return (Cliente.loja_id == loja_id) & (func.regexp_replace(Cliente.telefone, r'\D', '', 'g') == digitos)


def _telefone_da_loja(ctx: ContextoSite, digitos: str) -> ColumnElement[bool]:
    return filtro_telefone(ctx.loja.id, digitos)


def cliente_do_telefone(db: Session, loja_id: UUID, digitos: str) -> Cliente | None:
    """O cliente mais antigo da loja com o telefone (o mesmo que o pedido do site usa)."""
    return db.scalar(
        select(Cliente)
        .where(filtro_telefone(loja_id, digitos))
        .order_by(Cliente.criado_em, Cliente.id)
        .limit(1)
    )


def _limitar_pendentes(ctx: ContextoSite, digitos: str) -> None:
    """No máximo N pedidos "Aguardando aceite" futuros por telefone na loja.

    Trava o telefone na transação (advisory lock): dois pedidos simultâneos do mesmo número são
    serializados, então a contagem não é burlada e o cliente novo não é cadastrado duas vezes.
    """
    ctx.db.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(f'site-telefone:{ctx.loja.id}:{digitos}', 0)))
    )
    pendentes = ctx.db.scalar(
        select(func.count())
        .select_from(Agendamento)
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .where(
            _telefone_da_loja(ctx, digitos),
            Agendamento.loja_id == ctx.loja.id,
            Agendamento.status == StatusAgendamento.pendente,
            Agendamento.fim > func.now(),
        )
    )
    if (pendentes or 0) >= get_settings().site_pendentes_por_telefone:
        raise conflito(MSG_MUITOS_PENDENTES)


def _cliente(ctx: ContextoSite, dados: SolicitacaoEntrada, digitos: str) -> Cliente:
    """Cliente pelo telefone (SIT-07): se já existe na loja, ganha o canal "site"; senão, é cadastrado.

    O cadastro existente não é alterado (nome e e-mail ficam como a loja registrou) e nada dele é
    devolvido, para o site não revelar dados de quem já é cliente.
    """
    existente = cliente_do_telefone(ctx.db, ctx.loja.id, digitos)
    if existente is not None:
        if CanalCliente.site not in existente.canais:
            existente.canais = [*existente.canais, CanalCliente.site]
        return existente
    cliente = Cliente(
        loja_id=ctx.loja.id,
        nome=dados.nome,
        sobrenome=dados.sobrenome,
        telefone=dados.telefone,
        email=dados.email,
        canais=[CanalCliente.site],
    )
    ctx.db.add(cliente)
    return cliente


def solicitar(ctx: ContextoSite, dados: SolicitacaoEntrada) -> SolicitacaoSaida:
    """Pedido do cliente (SIT-05 a SIT-07): agendamento ``pendente``, ``origem = site``, preço congelado,
    local reservado e materiais copiados. O banco recusa a corrida entre dois pedidos (EXCLUDE, 23P01).
    """
    db = ctx.db
    servico = servico_escolhido(ctx, dados.servico_id, travar=True)
    escolha = horario_oferecido(ctx, servico, dados.funcionario_id, dados.inicio, dados.local_id)
    livre = escolha.livre

    digitos = so_digitos(dados.telefone)
    _limitar_pendentes(ctx, digitos)
    cliente = _cliente(ctx, dados, digitos)
    db.flush()
    agendamento = Agendamento(
        loja_id=ctx.loja.id,
        cliente_id=cliente.id,
        servico_id=servico.id if servico else None,
        funcionario_id=livre.funcionario.id,
        local_id=escolha.local_id,
        inicio=livre.inicio,
        fim=livre.fim,
        preco=servico.preco if servico else None,
        status=StatusAgendamento.pendente,
        origem=OrigemAgendamento.site,
        observacoes=dados.observacoes,
    )
    db.add(agendamento)
    db.flush()  # o banco recusa conflito de horário que tenha surgido agora (EXCLUDE)
    if ctx.usa_materiais and servico is not None:
        for material_id, extra in materiais_do_servico(db, ctx.loja.id, servico.id).items():
            db.add(
                AgendamentoMaterial(
                    loja_id=ctx.loja.id, agendamento_id=agendamento.id, material_id=material_id, **extra
                )
            )
        db.flush()

    return SolicitacaoSaida(
        id=agendamento.id,
        status=agendamento.status,
        inicio=livre.inicio.astimezone(ctx.zona),
        fim=livre.fim.astimezone(ctx.zona),
        servico_nome=nome_de(servico),
        funcionario_nome=livre.funcionario.nome,
        local=escolha.local,
        preco=agendamento.preco,
        cliente_nome=dados.nome,
        mensagem=f'Pedido enviado. {ctx.nome_da_loja} vai confirmar o seu horário.',
    )


JANELA_DE_REPETICAO = timedelta(minutes=10)


def pedido_repetido(ctx: ContextoSite, dados: SolicitacaoEntrada) -> UUID | None:
    """O mesmo pedido, já gravado pelo site há pouco e ainda pendente (LOG-07).

    Envio repetido do mesmo formulário (duplo clique sem JS, recarregar a página, dois envios ao mesmo
    tempo) encontra o próprio pedido: o site mostra a confirmação dele em vez de dizer que o horário foi
    ocupado ou que o telefone já tem pedidos pendentes.

    Para não entregar o pedido de outra pessoa a quem só conhece telefone, profissional e horário
    (SIT-07), tudo o que foi digitado precisa bater: o cliente tem de ter sido cadastrado por esse
    pedido (mesma transação, ``criado_em`` igual), com o mesmo nome, sobrenome e e-mail (sem diferenciar
    maiúsculas), e as observações iguais. Telefone que já era de um cliente da loja nunca é tratado
    como repetição (o nome digitado não fica gravado): o envio repetido volta à escolha de horário.
    """
    email = dados.email.lower() if dados.email else None
    return ctx.db.scalar(
        select(Agendamento.id)
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .where(
            Agendamento.loja_id == ctx.loja.id,
            Agendamento.funcionario_id == dados.funcionario_id,
            Agendamento.inicio == no_fuso(dados.inicio, ctx.zona),
            Agendamento.origem == OrigemAgendamento.site,
            Agendamento.status == StatusAgendamento.pendente,
            Agendamento.criado_em > func.now() - JANELA_DE_REPETICAO,
            Agendamento.observacoes.is_not_distinct_from(dados.observacoes),
            _telefone_da_loja(ctx, so_digitos(dados.telefone)),
            Cliente.criado_em == Agendamento.criado_em,
            func.lower(Cliente.nome) == dados.nome.lower(),
            func.lower(Cliente.sobrenome) == dados.sobrenome.lower(),
            func.lower(Cliente.email).is_not_distinct_from(email),
        )
        .limit(1)
    )


def pedido_repetido_da_conta(ctx: ContextoSite, dados: SolicitacaoEntrada) -> UUID | None:
    """O mesmo pedido de quem está na conta (SIT-22), já gravado pelo site há pouco e ainda pendente.

    A sessão prova que o telefone é de quem envia, então basta o telefone da conta (em ``dados``), o
    profissional, o início e as observações iguais (LOG-07: duplo clique, recarregar, envio simultâneo).
    """
    return ctx.db.scalar(
        select(Agendamento.id)
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .where(
            Agendamento.loja_id == ctx.loja.id,
            Agendamento.funcionario_id == dados.funcionario_id,
            Agendamento.inicio == no_fuso(dados.inicio, ctx.zona),
            Agendamento.origem == OrigemAgendamento.site,
            Agendamento.status == StatusAgendamento.pendente,
            Agendamento.criado_em > func.now() - JANELA_DE_REPETICAO,
            Agendamento.observacoes.is_not_distinct_from(dados.observacoes),
            _telefone_da_loja(ctx, so_digitos(dados.telefone)),
        )
        .limit(1)
    )


# --- Confirmação (passo 4) -----------------------------------------------------------------------

VALIDADE_DO_CODIGO = timedelta(hours=24)
DOMINIO_PEDIDO, DOMINIO_FALSO = 'site-pedido', 'site-falso'


def codigo_do_pedido(loja_id: UUID, agendamento_id: UUID | None, *, agora: datetime | None = None) -> str:
    """Código da página de confirmação: id do pedido + validade (24 h), assinado (HMAC) e preso à loja.

    ``agendamento_id`` None = código de um pedido que não existe (resposta ao robô que caiu na
    armadilha do formulário): mesmo formato, assinado com outra chave, e a página mostra uma
    confirmação genérica sem gravar nada.
    """
    falso = agendamento_id is None
    return assinar_id(
        DOMINIO_FALSO if falso else DOMINIO_PEDIDO,
        loja_id,
        uuid.uuid4() if agendamento_id is None else agendamento_id,
        VALIDADE_DO_CODIGO,
        agora=agora,
    )


@dataclass(frozen=True)
class CodigoLido:
    agendamento_id: UUID
    falso: bool


def ler_codigo(codigo: str, loja_id: UUID, *, agora: datetime | None = None) -> CodigoLido | None:
    """Código válido, desta loja e dentro da validade; senão None (a página responde 404)."""
    lido = ler_id(codigo, loja_id, (DOMINIO_PEDIDO, DOMINIO_FALSO), agora=agora)
    if lido is None:
        return None
    return CodigoLido(agendamento_id=lido[0], falso=lido[1] == DOMINIO_FALSO)


@dataclass(frozen=True)
class ResumoDoPedido:
    inicio: datetime
    status: StatusAgendamento
    preco: Decimal | None
    servico_nome: str
    funcionario_nome: str
    local_nome: str | None


def resumo_do_pedido(ctx: ContextoSite, agendamento_id: UUID) -> ResumoDoPedido | None:
    """O pedido feito pelo site (desta loja, não excluído), só com o que a confirmação mostra.

    Nada do cliente: se o telefone já era de um cliente da loja, o nome cadastrado não aparece (SIT-07).
    Serviço, profissional ou local excluídos depois continuam com o nome (histórico).
    """
    linha = ctx.db.execute(
        select(
            Agendamento.inicio,
            Agendamento.status,
            Agendamento.preco,
            Servico.nome,
            Funcionario.nome,
            Local.nome,
        )
        .join(
            Funcionario,
            (Funcionario.id == Agendamento.funcionario_id) & (Funcionario.loja_id == Agendamento.loja_id),
        )
        .outerjoin(Servico, (Servico.id == Agendamento.servico_id) & (Servico.loja_id == Agendamento.loja_id))
        .outerjoin(Local, (Local.id == Agendamento.local_id) & (Local.loja_id == Agendamento.loja_id))
        .where(
            Agendamento.id == agendamento_id,
            Agendamento.loja_id == ctx.loja.id,
            Agendamento.origem == OrigemAgendamento.site,
            Agendamento.excluido_em.is_(None),
        )
        .execution_options(incluir_excluidos=True)
    ).one_or_none()
    if linha is None:
        return None
    inicio, situacao, preco, servico_nome, funcionario_nome, local_nome = linha
    return ResumoDoPedido(
        inicio=inicio.astimezone(ctx.zona),
        status=situacao,
        preco=preco,
        servico_nome=servico_nome or NOME_SEM_SERVICO,
        funcionario_nome=funcionario_nome,
        local_nome=local_nome,
    )
