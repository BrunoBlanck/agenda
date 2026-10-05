"""Locais (/api/loja/locais) e como a loja os chama no menu (/api/loja/locais/rotulos). Recurso: locais.

Local não é excluído: é inativado (some dos novos agendamentos, o histórico continua).

Serviços vinculados (LOC-06): os mesmos vínculos de servico_locais editados na tela de Serviços. O
vínculo restringe o serviço, não o local: serviço sem nenhum local vinculado aceita qualquer local.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Agendamento, Local, Servico, ServicoLocal
from app.models.enums import StatusAgendamento
from app.schemas.comum import Erro
from app.schemas.locais import (
    LocalEntrada,
    LocalSaida,
    OpcoesLocal,
    RotulosEntrada,
    RotulosSaida,
    ServicoDoLocal,
    ServicoOpcaoLocal,
)
from app.services.comum import (
    buscar,
    com_autor,
    conferir_ids,
    fuso,
    hoje,
    inicio_do_dia,
    sincronizar_vinculos,
)
from app.services.configuracoes import configuracao_da_loja

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(prefix='/locais', tags=['Loja: locais'], responses=ERROS)

MSG_404 = 'Local não encontrado.'
MSG_SERVICO_404 = 'Serviço não encontrado.'
INATIVOS = (StatusAgendamento.cancelado, StatusAgendamento.nao_compareceu)

Leitura = Annotated[ContextoLoja, Depends(exigir('locais'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('locais', 'escrita'))]


def _saida(ctx: ContextoLoja, locais: list[Local]) -> list[LocalSaida]:
    db = ctx.db
    ids = [loc.id for loc in locais]
    servicos: dict[UUID, list[ServicoDoLocal]] = {i: [] for i in ids}
    if ctx.acesso.modulo_ativo('servicos'):
        # Vínculos e serviços excluídos ficam de fora (filtro global de excluido_em do ORM)
        for local_id, servico_id, nome, ativo in db.execute(
            select(ServicoLocal.local_id, Servico.id, Servico.nome, Servico.ativo)
            .join(
                Servico, (Servico.id == ServicoLocal.servico_id) & (Servico.loja_id == ServicoLocal.loja_id)
            )
            .where(ServicoLocal.loja_id == ctx.loja_id, ServicoLocal.local_id.in_(ids))
            .order_by(func.lower(Servico.nome), Servico.id)
        ):
            servicos[local_id].append(ServicoDoLocal(id=servico_id, nome=nome, ativo=ativo))
    zona = fuso(ctx.loja.fuso_horario)
    desde = inicio_do_dia(hoje(zona), zona)
    proximos = dict(
        db.execute(
            select(Agendamento.local_id, func.count())
            .where(
                Agendamento.loja_id == ctx.loja_id,
                Agendamento.local_id.in_(ids),
                Agendamento.inicio >= desde,
                Agendamento.status.not_in(INATIVOS),
            )
            .group_by(Agendamento.local_id)
        ).all()
    )
    saida = []
    for loc in locais:
        item = LocalSaida.model_validate(loc)
        item.servicos = servicos[loc.id]
        item.proximos_agendamentos = proximos.get(loc.id, 0)
        saida.append(item)
    return com_autor(db, ctx.loja_id, saida)


def _gravar_servicos(ctx: ContextoLoja, local: Local, servico_ids: list[UUID] | None) -> None:
    """Deixa o local vinculado exatamente a ``servico_ids`` (None = não mexe; módulo Serviços
    desligado = ignorado). Religar um vínculo removido restaura a linha existente."""
    if servico_ids is None or not ctx.acesso.modulo_ativo('servicos'):
        return
    conferir_ids(ctx.db, Servico, ctx.loja_id, servico_ids, MSG_SERVICO_404)
    sincronizar_vinculos(
        ctx.db, ServicoLocal, ctx.loja_id, {'local_id': local.id}, 'servico_id', {i: {} for i in servico_ids}
    )


# --- Rótulos (antes de /{local_id}) -------------------------------------------------------------


@router.get('/rotulos', summary='Como a loja chama os locais (Sala, Cadeira...)')
def obter_rotulos(ctx: Leitura) -> RotulosSaida:
    configuracao = configuracao_da_loja(ctx.db, ctx.loja_id)
    return com_autor(ctx.db, ctx.loja_id, [RotulosSaida.model_validate(configuracao)])[0]


@router.put('/rotulos', summary='Definir como a loja chama os locais (muda o menu e os textos do painel)')
def definir_rotulos(dados: RotulosEntrada, ctx: Escrita) -> RotulosSaida:
    configuracao = configuracao_da_loja(ctx.db, ctx.loja_id)
    configuracao.rotulo_local = dados.rotulo_local
    configuracao.rotulo_local_plural = dados.rotulo_local_plural
    ctx.db.flush()
    return com_autor(ctx.db, ctx.loja_id, [RotulosSaida.model_validate(configuracao)])[0]


# --- Locais ------------------------------------------------------------------------------------


@router.get('', summary='Locais da loja')
def listar(ctx: Leitura, ativo: bool | None = None) -> list[LocalSaida]:
    consulta = select(Local).where(Local.loja_id == ctx.loja_id)
    if ativo is not None:
        consulta = consulta.where(Local.ativo == ativo)
    return _saida(ctx, list(ctx.db.scalars(consulta.order_by(func.lower(Local.nome), Local.id))))


@router.get('/opcoes', summary='Serviços para o formulário de local')
def opcoes(ctx: Escrita) -> OpcoesLocal:
    """Quem edita locais escolhe os serviços sem precisar de acesso a Serviços (como em
    GET /servicos/opcoes). Ativos e inativos, para salvar o local sem apagar vínculos com inativos.
    Nulo com o módulo Serviços desligado.
    """
    if not ctx.acesso.modulo_ativo('servicos'):
        return OpcoesLocal(servicos=None)
    db = ctx.db
    # Só vínculos e locais não excluídos contam (filtro global de excluido_em do ORM)
    vinculados = dict(
        db.execute(
            select(ServicoLocal.servico_id, func.count())
            .join(Local, (Local.id == ServicoLocal.local_id) & (Local.loja_id == ServicoLocal.loja_id))
            .where(ServicoLocal.loja_id == ctx.loja_id)
            .group_by(ServicoLocal.servico_id)
        ).all()
    )
    servicos = [
        ServicoOpcaoLocal(id=i, nome=n, ativo=a, locais_vinculados=vinculados.get(i, 0))
        for i, n, a in db.execute(
            select(Servico.id, Servico.nome, Servico.ativo)
            .where(Servico.loja_id == ctx.loja_id)
            .order_by(func.lower(Servico.nome), Servico.id)
        )
    ]
    return OpcoesLocal(servicos=servicos)


@router.get('/{local_id}', summary='Um local')
def obter(local_id: UUID, ctx: Leitura) -> LocalSaida:
    return _saida(ctx, [buscar(ctx.db, Local, ctx.loja_id, local_id, MSG_404)])[0]


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar local (e os serviços dele)')
def criar(dados: LocalEntrada, ctx: Escrita) -> LocalSaida:
    local = Local(loja_id=ctx.loja_id, **dados.model_dump(exclude={'servico_ids'}))
    ctx.db.add(local)
    ctx.db.flush()
    _gravar_servicos(ctx, local, dados.servico_ids)
    return _saida(ctx, [local])[0]


@router.put('/{local_id}', summary='Editar local (inclui inativar) e os serviços dele')
def editar(local_id: UUID, dados: LocalEntrada, ctx: Escrita) -> LocalSaida:
    # FOR UPDATE quando os vínculos mudam: duas edições do mesmo local ao mesmo tempo não tentam
    # inserir o mesmo vínculo duas vezes (a segunda espera e enxerga o que a primeira gravou)
    local = buscar(ctx.db, Local, ctx.loja_id, local_id, MSG_404, travar=dados.servico_ids is not None)
    for campo, valor in dados.model_dump(exclude={'servico_ids'}).items():
        setattr(local, campo, valor)
    ctx.db.flush()
    _gravar_servicos(ctx, local, dados.servico_ids)
    return _saida(ctx, [local])[0]
