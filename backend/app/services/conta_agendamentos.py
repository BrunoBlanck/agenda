"""Cancelar e remarcar pelo site, na conta do cliente (SIT-23, SIT-24, AGE-25).

- **Quem:** só agendamentos da conta (mesma loja, cliente com o telefone da conta, não excluídos). Os
  outros respondem como inexistentes (a página dá 404).
- **Quando** (``exigir_alteravel``): situação ``pendente``/``agendado``/``confirmado`` e pelo menos a
  antecedência da loja (CFG-05, ``loja_configuracoes.antecedencia_cliente_minutos``) antes do início. O
  ``POST`` trava a linha (``FOR UPDATE``) e confere de novo.
- **Avisos** (NOT-03): cancelar avisa o profissional; remarcar avisa o cliente (pedido recebido), o
  profissional novo e, se mudou, o antigo. Na mesma transação (e no mesmo savepoint) da alteração.
- **Cancelar** (SIT-23): vira ``cancelado`` na hora, sem aceite da loja, com o motivo fixo.
- **Remarcar** (SIT-24): mesmo serviço, preço congelado e a duração atual (``fim - inicio``); o novo
  horário precisa ser um dos que o site oferece (``horario_oferecido``), sem contar o próprio agendamento
  como ocupado. Muda profissional, local, início e fim e volta a ``pendente`` (a loja aceita ou recusa
  como um pedido novo). O banco recusa a corrida com outro pedido (EXCLUDE, 23P01).
- **AGE-25:** as transições de ``TRANSICOES_DO_CLIENTE`` existem só aqui; o painel continua com as de
  ``app/services/agendamentos.py::TRANSICOES`` (nenhum caminho dele volta um agendamento a ``pendente``).

Contexto da transação: o das páginas do site (``app.origem = 'site'``, a loja, sem funcionário), então a
auditoria registra a alteração com origem ``site`` e ``atualizado_por`` NULL.
"""

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agendamento, Cliente, Servico
from app.models.enums import StatusAgendamento
from app.services.agendamento_site import (
    ContextoSite,
    HorarioEscolhido,
    filtro_telefone,
    horario_oferecido,
    servico_escolhido,
)
from app.services.conta_cliente import SITUACOES_ATIVAS, pode_alterar
from app.services.horarios_livres import locais_permitidos, profissionais
from app.services.notificacoes import HorarioAnterior, avisar_cancelamento_do_site, avisar_remarcacao_do_site

S = StatusAgendamento
MOTIVO_CANCELAMENTO = 'Cancelado pelo cliente pelo site.'

# AGE-25: o que o cliente pode fazer pelo site com um agendamento ativo. Remarcar volta a ``pendente``
# (inclusive de ``pendente`` para ``pendente`` com outro horário); cancelar vai a ``cancelado``.
TRANSICOES_DO_CLIENTE: dict[StatusAgendamento, frozenset[StatusAgendamento]] = {
    situacao: frozenset({S.pendente, S.cancelado}) for situacao in SITUACOES_ATIVAS
}


class NaoAlteravel(Exception):
    """Situação final ou fora do prazo: só a loja altera (a página responde 409)."""


class RemarcacaoImpossivel(Exception):
    """Serviço inativo/removido, ninguém habilitado ou sem local possível: remarcar só com a loja."""


def agendamento_da_conta(
    db: Session, loja_id: UUID, digitos: str, agendamento_id: UUID, *, travar: bool = False
) -> Agendamento | None:
    """O agendamento, se for de um cliente (não excluído) da loja com o telefone da conta (SIT-16).

    travar: ``FOR UPDATE`` só da linha do agendamento, a mesma trava das rotas do painel que o alteram
    (as duas mudanças ficam em fila e a segunda vê a situação que a primeira gravou).
    """
    consulta = (
        select(Agendamento)
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .where(
            Agendamento.id == agendamento_id,
            Agendamento.loja_id == loja_id,
            filtro_telefone(loja_id, digitos),
        )
    )
    if travar:
        consulta = consulta.with_for_update(of=Agendamento).execution_options(populate_existing=True)
    return db.scalar(consulta)


def exigir_alteravel(
    situacao: StatusAgendamento, inicio: datetime, novo: StatusAgendamento, antecedencia: timedelta
) -> None:
    """SIT-23/24 e AGE-25: situação ativa, dentro do prazo da loja e transição do cliente permitida."""
    permitidas = TRANSICOES_DO_CLIENTE.get(situacao, frozenset())
    if not pode_alterar(situacao, inicio, antecedencia) or novo not in permitidas:
        raise NaoAlteravel


def duracao_minutos(inicio: datetime, fim: datetime) -> int:
    return int((fim - inicio) // timedelta(minutes=1))


# --- Cancelar (SIT-23) -----------------------------------------------------------------------------


def cancelado_pelo_cliente(ag: Agendamento) -> bool:
    """Já cancelado pelo próprio cliente no site (o mesmo envio repetido, LOG-07)."""
    return ag.status == S.cancelado and ag.motivo_cancelamento == MOTIVO_CANCELAMENTO


def cancelar(ctx: ContextoSite, ag: Agendamento) -> None:
    """Cancela na hora, com o motivo fixo (o chamador já travou a linha), e avisa o profissional."""
    exigir_alteravel(ag.status, ag.inicio, S.cancelado, ctx.antecedencia)
    ag.status = S.cancelado
    ag.motivo_cancelamento = MOTIVO_CANCELAMENTO
    ctx.db.flush()
    avisar_cancelamento_do_site(ctx.db, ctx.aviso, ag)


# --- Remarcar (SIT-24) -----------------------------------------------------------------------------


def servico_da_remarcacao(
    ctx: ContextoSite, servico_id: UUID | None, *, travar: bool = False
) -> Servico | None:
    """O serviço do agendamento, se ainda dá para remarcar pelo site; senão ``RemarcacaoImpossivel``.

    Sem o módulo Serviços: None (os profissionais do SIT-08). Com ele: o serviço precisa estar ativo e
    não excluído (LOG-08), com alguém ativo habilitado; com o módulo Locais, com algum local possível.
    travar: ``FOR KEY SHARE`` no serviço, como o pedido do site (não passa junto com a exclusão dele).
    """
    servico: Servico | None = None
    if ctx.usa_servicos:
        if servico_id is None:
            raise RemarcacaoImpossivel
        try:
            servico = servico_escolhido(ctx, servico_id, travar=travar)
        except HTTPException:
            raise RemarcacaoImpossivel from None
    if not profissionais(ctx.db, ctx.loja.id, servico):
        raise RemarcacaoImpossivel
    if ctx.usa_locais and not locais_permitidos(ctx.db, ctx.loja.id, servico):
        raise RemarcacaoImpossivel
    return servico


class HorarioAtual(Protocol):
    """O que a remarcação precisa saber do horário atual (o agendamento travado ou o da página)."""

    @property
    def id(self) -> UUID: ...
    @property
    def inicio(self) -> datetime: ...
    @property
    def fim(self) -> datetime: ...
    @property
    def funcionario_id(self) -> UUID: ...


class MesmoHorario(Exception):
    """O horário escolhido é o atual (mesmo profissional e início): nada a remarcar."""


def novo_horario(
    ctx: ContextoSite,
    servico: Servico | None,
    atual: HorarioAtual,
    funcionario_id: UUID,
    inicio: datetime,
    local_id: UUID | None,
) -> HorarioEscolhido:
    """O horário escolhido para a remarcação, se o site o oferece com a duração atual e sem contar o
    próprio agendamento como ocupado.

    Erros: ``HorarioIndisponivel`` (não oferecido ou local ocupado), ``HTTPException`` 422 (profissional
    ou local que não servem para o serviço) e ``MesmoHorario``.
    """
    escolha = horario_oferecido(
        ctx,
        servico,
        funcionario_id,
        inicio,
        local_id,
        duracao=duracao_minutos(atual.inicio, atual.fim),
        ignorar=atual.id,
    )
    if escolha.livre.funcionario.id == atual.funcionario_id and escolha.livre.inicio == atual.inicio:
        raise MesmoHorario
    return escolha


def remarcar(
    ctx: ContextoSite,
    ag: Agendamento,
    servico: Servico | None,
    funcionario_id: UUID,
    inicio: datetime,
    local_id: UUID | None,
) -> HorarioEscolhido:
    """Troca o horário (o chamador já travou a linha) e volta a ``pendente`` (AGE-25).

    Erros: ``NaoAlteravel``, os de ``novo_horario`` e, no ``flush``, a recusa do banco (23P01) se outro
    pedido levou o horário agora.
    """
    exigir_alteravel(ag.status, ag.inicio, S.pendente, ctx.antecedencia)
    escolha = novo_horario(ctx, servico, ag, funcionario_id, inicio, local_id)
    livre = escolha.livre
    antes = HorarioAnterior(funcionario_id=ag.funcionario_id, inicio=ag.inicio)
    if escolha.local_id != ag.local_id:
        ag.local_id = escolha.local_id  # sem o módulo Locais, None (como o pedido do site)
        ag.link_reuniao = None  # o link era do local antigo; o painel mostra o link padrão do novo
    ag.funcionario_id = livre.funcionario.id
    ag.inicio, ag.fim = livre.inicio, livre.fim
    ag.status = S.pendente
    ctx.db.flush()  # o banco recusa conflito de horário que tenha surgido agora (EXCLUDE)
    avisar_remarcacao_do_site(ctx.db, ctx.aviso, ag, antes)
    return escolha
