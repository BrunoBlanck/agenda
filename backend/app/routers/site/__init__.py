"""Rotas públicas do site do consumidor (/api/site/{slug}/...).

Sem login. A loja vem do slug; loja inexistente, excluída, suspensa ou cancelada responde 404. Cada
requisição grava o contexto ``app.origem = 'site'`` e ``app.loja_id`` (RLS), sem funcionário: o que o
cliente cria fica com ``atualizado_por`` NULL e aparece na auditoria como "Cliente, pelo site".

Só sai o necessário: dados de contato da loja, serviços ativos, nome dos profissionais habilitados,
locais (sem links) e horários livres. Nada de outros clientes nem dados internos.

As regras ficam em ``app/services/agendamento_site.py``, as mesmas das páginas HTML do site
(``app/routers/site/paginas.py``).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.limites import limite_site, limite_site_pedido
from app.schemas.comum import Data, Erro
from app.schemas.site import (
    DiaLivre,
    HorarioLivre,
    LocalPublico,
    LojaPublica,
    ServicoPublico,
    SolicitacaoEntrada,
    SolicitacaoSaida,
)
from app.services.agendamento_site import (
    ContextoSite,
    abrir_site,
    dias_livres,
    local_publico,
    servico_escolhido,
    servicos_publicos,
)
from app.services.agendamento_site import solicitar as solicitar_agendamento
from app.services.comum import hoje, invalido, nao_encontrado
from app.services.horarios_livres import DIAS_MAXIMOS, locais_permitidos
from app.services.site import dados_publicos

router = APIRouter(
    prefix='/api/site/{slug}',
    tags=['Site do consumidor'],
    responses={404: {'model': Erro}, 422: {'model': Erro}, 429: {'model': Erro}},
    dependencies=[Depends(limite_site)],  # requisições por IP (app/limites.py)
)

MSG_LOJA_404 = 'Loja não encontrada.'


def obter_contexto_site(
    slug: Annotated[str, Path(max_length=60, description='Endereço da loja (ex.: clinica-sorriso)')],
    request: Request,
    db: DbDep,
) -> ContextoSite:
    ctx = abrir_site(db, slug, ip_da_requisicao(request))
    if ctx is None:
        raise nao_encontrado(MSG_LOJA_404)
    return ctx


Site = Annotated[ContextoSite, Depends(obter_contexto_site)]


# --- Leitura -------------------------------------------------------------------------------------


@router.get('', summary='Dados públicos da loja')
def loja(ctx: Site) -> LojaPublica:
    return dados_publicos(ctx.db, ctx.loja, ctx.modulos)


@router.get('/servicos', summary='Serviços ativos com os profissionais habilitados')
def servicos(ctx: Site) -> list[ServicoPublico]:
    return servicos_publicos(ctx)


@router.get('/locais', summary='Locais ativos (vazio sem o módulo Locais)')
def locais(
    ctx: Site, servico_id: Annotated[UUID | None, Query(description='Só os permitidos para o serviço')] = None
) -> list[LocalPublico]:
    if not ctx.usa_locais:
        return []
    servico = servico_escolhido(ctx, servico_id) if servico_id is not None else None
    return [LocalPublico.model_validate(local) for local in locais_permitidos(ctx.db, ctx.loja.id, servico)]


@router.get('/horarios', summary='Horários livres por dia, para um serviço (e um profissional, opcional)')
def horarios(
    ctx: Site,
    servico_id: UUID | None = None,
    funcionario_id: Annotated[UUID | None, Query(description='Vazio = qualquer profissional')] = None,
    local_id: Annotated[
        UUID | None, Query(description='Só horários com este local livre (módulo Locais; vazio = qualquer)')
    ] = None,
    inicio: Annotated[Data | None, Query(description='Primeiro dia (padrão: hoje)')] = None,
    fim: Annotated[Data | None, Query(description='Último dia (padrão: o primeiro)')] = None,
) -> list[DiaLivre]:
    primeiro = inicio or hoje(ctx.zona)
    ultimo = fim or primeiro
    if ultimo < primeiro:
        raise invalido('O último dia deve ser depois do primeiro.')
    if (ultimo - primeiro).days >= DIAS_MAXIMOS:
        raise invalido(f'Consulte no máximo {DIAS_MAXIMOS} dias por vez.')
    servico = servico_escolhido(ctx, servico_id)
    dias, mapa_locais = dias_livres(ctx, servico, funcionario_id, primeiro, ultimo, local_id)
    return [
        DiaLivre(
            data=dia,
            horarios=[
                HorarioLivre(
                    hora=livre.inicio.astimezone(ctx.zona).strftime('%H:%M'),
                    inicio=livre.inicio.astimezone(ctx.zona),
                    funcionario_id=livre.funcionario.id,
                    funcionario_nome=livre.funcionario.nome,
                    local=local_publico(mapa_locais, livre.local_id),
                )
                for livre in livres
            ],
        )
        for dia, livres in dias
    ]


# --- Pedido de agendamento -----------------------------------------------------------------------


@router.post(
    '/agendamentos',
    status_code=status.HTTP_201_CREATED,
    responses={409: {'model': Erro}},
    dependencies=[Depends(limite_site_pedido)],  # pedidos por IP nesta loja
    summary='Pedir um agendamento (entra como "Aguardando aceite" no painel da loja)',
)
def solicitar(dados: SolicitacaoEntrada, ctx: Site) -> SolicitacaoSaida:
    return solicitar_agendamento(ctx, dados)
