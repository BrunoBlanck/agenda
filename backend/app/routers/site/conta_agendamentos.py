"""Cancelar e remarcar pela conta do cliente (SIT-23, SIT-24, AGE-25): páginas HTML.

- ``GET/POST /<slug>/conta/agendamentos/<id>/cancelar``: resumo e "Cancelar este agendamento?"; o ``POST``
  cancela na hora e volta a Minha conta com ``aviso=cancelado``;
- ``GET /<slug>/conta/agendamentos/<id>/remarcar?profissional=&dia=``: a escolha de horário do passo 2
  (faixa de 31 dias), com a duração atual e sem contar o próprio agendamento como ocupado;
- ``GET/POST /<slug>/conta/agendamentos/<id>/remarcar/confirmar?profissional=&inicio=&local=``: "De … Para …"
  e o envio; o ``POST`` troca o horário, volta a ``pendente`` e vai a Minha conta com ``aviso=remarcado``.

Regras em ``app/services/conta_agendamentos.py``. Todas exigem a sessão (sem ela, 303 para entrar voltando à
mesma página). Agendamento de outro telefone, de outra loja, inexistente ou excluído: 404. Situação final ou
menos de 2 h antes: 409 com o telefone da loja. Serviço que não dá mais para remarcar pelo site: 409 "Para
remarcar este horário, fale com a loja." (cancelar continua possível). Horário que não é mais oferecido
(inclusive a corrida recusada pelo banco, 23P01): 303 de volta à escolha com ``aviso=ocupado``.
Todo ``POST`` confere a origem e trava a linha do agendamento antes de conferir tudo de novo.
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.exc import DBAPIError

from app.auth.dependencias import DbDep
from app.erros import MSG_TENTE_DE_NOVO
from app.models import Agendamento, Servico
from app.models.enums import StatusAgendamento
from app.routers.html import RespostaPronta, nao_encontrada, redirecionar
from app.routers.site.conta import AVISOS, exigir_sessao, item_da_conta, origem_recusada
from app.routers.site.paginas import (
    METODOS,
    Pagina,
    abrir,
    dia_por_extenso,
    escolha_de_horario,
    ler_formulario,
    ler_momento,
    ler_uuid,
    montar_url,
)
from app.services.agendamento_site import HorarioEscolhido, HorarioIndisponivel
from app.services.comum import no_fuso
from app.services.conta_agendamentos import (
    HorarioAtual,
    MesmoHorario,
    NaoAlteravel,
    RemarcacaoImpossivel,
    agendamento_da_conta,
    cancelado_pelo_cliente,
    cancelar,
    duracao_minutos,
    novo_horario,
    remarcar,
    servico_da_remarcacao,
)
from app.services.conta_cliente import MeuAgendamento, meu_agendamento, pode_alterar

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)
Formulario = Annotated[dict[str, str], Depends(ler_formulario)]

CAMINHO = '/{slug:segmento}/conta/agendamentos/{agendamento_id}'
MSG_NAO_ALTERAVEL = 'Este agendamento não pode mais ser alterado pelo site. Fale com a loja'
MSG_REMARCAR_COM_A_LOJA = 'Para remarcar este horário, fale com a loja'


# --- Ajudantes -----------------------------------------------------------------------------------


def _base(site: Pagina, agendamento_id: UUID) -> str:
    return f'/{site.slug}/conta/agendamentos/{agendamento_id}'


def _conta(site: Pagina, aviso: str | None = None) -> str:
    return montar_url(f'/{site.slug}/conta', aviso=aviso)


def _nao_encontrado() -> RespostaPronta:
    return RespostaPronta(nao_encontrada())


def _da_conta(site: Pagina, texto_id: str) -> MeuAgendamento:
    """O agendamento da URL, se for da conta na sessão (sem sessão: 303 para entrar; senão 404)."""
    sessao = exigir_sessao(site)
    agendamento_id = ler_uuid(texto_id)
    item = (
        meu_agendamento(site.ctx.db, site.ctx.loja.id, sessao.conta.telefone_digitos, agendamento_id)
        if agendamento_id is not None
        else None
    )
    if item is None:
        raise _nao_encontrado()
    return item


def _travado(site: Pagina, texto_id: str) -> Agendamento:
    """O agendamento da URL com a linha travada (``POST``), se for da conta na sessão; senão 404."""
    sessao = exigir_sessao(site)
    agendamento_id = ler_uuid(texto_id)
    ag = (
        agendamento_da_conta(
            site.ctx.db, site.ctx.loja.id, sessao.conta.telefone_digitos, agendamento_id, travar=True
        )
        if agendamento_id is not None
        else None
    )
    if ag is None:
        raise _nao_encontrado()
    return ag


def _pagina_aviso(
    site: Pagina,
    titulo: str,
    mensagem: str,
    item: MeuAgendamento | None = None,
    *,
    cancelar: str | None = None,
    com_telefone: bool = True,
) -> HTMLResponse:
    """409: o que o site não pode fazer com o agendamento (com o telefone da loja no fim da mensagem)."""
    return site.renderizar(
        'site/conta_aviso.html',
        None,
        status.HTTP_409_CONFLICT,
        titulo_pagina=titulo,
        mensagem=mensagem,
        com_telefone=com_telefone,
        agendamento=item_da_conta(site, item) if item is not None else None,
        rotulo_local=site.loja.rotulo_local,
        cancelar=cancelar,
        conta=_conta(site),
    )


def _nao_alteravel(site: Pagina, item: MeuAgendamento | None = None) -> RespostaPronta:
    return RespostaPronta(_pagina_aviso(site, 'Alterar agendamento', MSG_NAO_ALTERAVEL, item))


def _servico(
    site: Pagina,
    agendamento_id: UUID,
    servico_id: UUID | None,
    item: MeuAgendamento | None = None,
    *,
    travar: bool = False,
) -> Servico | None:
    """O serviço para remarcar; se não der pelo site, 409 com o convite a cancelar (SIT-24)."""
    try:
        return servico_da_remarcacao(site.ctx, servico_id, travar=travar)
    except RemarcacaoImpossivel:
        raise RespostaPronta(
            _pagina_aviso(
                site,
                'Remarcar agendamento',
                MSG_REMARCAR_COM_A_LOJA,
                item,
                cancelar=f'{_base(site, agendamento_id)}/cancelar',
            )
        ) from None


def _escolher(site: Pagina, agendamento_id: UUID, dia: date | None, aviso: str) -> RespostaPronta:
    """De volta à escolha de horário da remarcação (qualquer profissional) no dia, com o aviso."""
    url = montar_url(
        f'{_base(site, agendamento_id)}/remarcar', dia=dia.isoformat() if dia else None, aviso=aviso
    )
    return RespostaPronta(redirecionar(url + '#horarios'))


def _ler_escolha(
    site: Pagina, agendamento_id: UUID, valores: dict[str, str]
) -> tuple[UUID, datetime, UUID | None]:
    """Profissional, início (fuso da loja) e local escolhidos; ilegíveis voltam à escolha (``horario``)."""
    profissional_id = ler_uuid(valores.get('profissional'))
    momento = ler_momento(valores.get('inicio'))
    inicio = no_fuso(momento, site.ctx.zona) if momento else None
    texto_local = valores.get('local') or ''
    local_id = ler_uuid(texto_local)
    if profissional_id is None or inicio is None or (texto_local and local_id is None):
        dia = inicio.astimezone(site.ctx.zona).date() if inicio else None
        raise _escolher(site, agendamento_id, dia, 'horario')
    return profissional_id, inicio, local_id


def _horario_escolhido(
    site: Pagina,
    servico: Servico | None,
    atual: HorarioAtual,
    escolha: tuple[UUID, datetime, UUID | None],
) -> HorarioEscolhido:
    """O novo horário, se o site o oferece; senão de volta à escolha com o aviso certo."""
    profissional_id, inicio, local_id = escolha
    dia = inicio.astimezone(site.ctx.zona).date()
    try:
        return novo_horario(site.ctx, servico, atual, profissional_id, inicio, local_id)
    except HorarioIndisponivel:
        raise _escolher(site, atual.id, dia, 'ocupado') from None
    except MesmoHorario:
        raise _escolher(site, atual.id, dia, 'mesmo') from None
    except HTTPException:  # profissional que não faz o serviço, local que não é do serviço
        raise _escolher(site, atual.id, dia, 'horario') from None


# --- Cancelar (SIT-23) -----------------------------------------------------------------------------


@router.api_route(f'{CAMINHO}/cancelar', methods=METODOS)
def pagina_cancelar(slug: str, agendamento_id: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    item = _da_conta(site, agendamento_id)
    if not item.alteravel:
        raise _nao_alteravel(site, item)
    return site.renderizar(
        'site/conta_cancelar.html',
        None,
        agendamento=item_da_conta(site, item),
        rotulo_local=site.loja.rotulo_local,
        acao=f'{_base(site, item.id)}/cancelar',
        conta=_conta(site),
    )


@router.post(f'{CAMINHO}/cancelar', response_model=None)
def enviar_cancelar(slug: str, agendamento_id: str, request: Request, db: DbDep) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    ag = _travado(site, agendamento_id)
    if cancelado_pelo_cliente(ag):  # o mesmo envio de novo (LOG-07)
        return redirecionar(_conta(site, 'cancelado'))
    try:
        cancelar(db, ag)
    except NaoAlteravel:
        raise _nao_alteravel(site) from None
    return redirecionar(_conta(site, 'cancelado'))


# --- Remarcar (SIT-24, AGE-25) ---------------------------------------------------------------------


def _horario_atual(site: Pagina, item: MeuAgendamento) -> str:
    inicio = item.inicio.astimezone(site.ctx.zona)
    return f'{dia_por_extenso(inicio.date())}, {inicio:%H:%M} · {item.funcionario_nome}'


@router.api_route(f'{CAMINHO}/remarcar', methods=METODOS)
def pagina_remarcar(slug: str, agendamento_id: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    item = _da_conta(site, agendamento_id)
    if not item.alteravel:
        raise _nao_alteravel(site, item)
    servico = _servico(site, item.id, item.servico_id, item)
    base, duracao = _base(site, item.id), duracao_minutos(item.inicio, item.fim)
    return site.renderizar(
        'site/horarios.html',
        None,
        titulo=f'Remarcar: {item.servico_nome}',
        servico_nome=item.servico_nome,
        duracao=duracao,
        horario_atual=_horario_atual(site, item),
        voltar=_conta(site),
        **escolha_de_horario(
            site,
            request.query_params,
            servico,
            aviso=AVISOS.get(request.query_params.get('aviso', '')),
            url_dia=lambda profissional_id, dia: montar_url(
                f'{base}/remarcar', profissional=profissional_id, dia=dia.isoformat() if dia else None
            ),
            url_horario=lambda livre, inicio: montar_url(
                f'{base}/remarcar/confirmar',
                profissional=livre.funcionario.id,
                inicio=inicio,
                local=livre.local_id,
            ),
            duracao=duracao,
            ignorar=item.id,
        ),
    )


@router.api_route(f'{CAMINHO}/remarcar/confirmar', methods=METODOS)
def pagina_confirmar(slug: str, agendamento_id: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    item = _da_conta(site, agendamento_id)
    if not item.alteravel:
        raise _nao_alteravel(site, item)
    servico = _servico(site, item.id, item.servico_id, item)
    escolha = _horario_escolhido(site, servico, item, _ler_escolha(site, item.id, dict(request.query_params)))
    inicio = escolha.livre.inicio.astimezone(site.ctx.zona)
    local = escolha.local
    base = _base(site, item.id)
    return site.renderizar(
        'site/conta_remarcar.html',
        None,
        servico=item.servico_nome,
        atual=item_da_conta(site, item),
        novo={
            'dia': dia_por_extenso(inicio.date()),
            'hora': f'{inicio:%H:%M}',
            'profissional': escolha.livre.funcionario.nome,
            'local': local.nome if local else None,
        },
        rotulo_local=site.loja.rotulo_local,
        acao=f'{base}/remarcar/confirmar',
        ocultos={
            'profissional': escolha.livre.funcionario.id,
            'inicio': inicio.isoformat(timespec='minutes'),
            'local': escolha.local_id or '',
        },
        escolher=montar_url(f'{base}/remarcar', dia=inicio.date().isoformat()) + '#horarios',
    )


@router.post(f'{CAMINHO}/remarcar/confirmar', response_model=None)
def enviar_remarcacao(
    slug: str, agendamento_id: str, request: Request, db: DbDep, formulario: Formulario
) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    ag = _travado(site, agendamento_id)
    if not pode_alterar(ag.status, ag.inicio):
        raise _nao_alteravel(site)
    servico = _servico(site, ag.id, ag.servico_id, travar=True)
    profissional_id, inicio, local_id = _ler_escolha(site, ag.id, formulario)
    dia = inicio.astimezone(site.ctx.zona).date()
    try:
        with db.begin_nested():  # a recusa do banco desfaz só a remarcação; a página ainda responde
            remarcar(site.ctx, ag, servico, profissional_id, inicio, local_id)
    except NaoAlteravel:
        raise _nao_alteravel(site) from None
    except HorarioIndisponivel:
        raise _escolher(site, ag.id, dia, 'ocupado') from None
    except MesmoHorario:
        if ag.status == StatusAgendamento.pendente:  # já remarcado para este horário (envio repetido, LOG-07)
            return redirecionar(_conta(site, 'remarcado'))
        raise _escolher(site, ag.id, dia, 'mesmo') from None
    except HTTPException:
        raise _escolher(site, ag.id, dia, 'horario') from None
    except DBAPIError as exc:
        sqlstate = getattr(exc.orig, 'sqlstate', None)
        if sqlstate == '23P01':  # o banco recusou: outro pedido levou o horário agora (SIT-05)
            raise _escolher(site, ag.id, dia, 'ocupado') from None
        if sqlstate not in ('40P01', '40001'):
            raise
        return _pagina_aviso(site, 'Remarcar agendamento', MSG_TENTE_DE_NOVO, com_telefone=False)
    return redirecionar(_conta(site, 'remarcado'))
