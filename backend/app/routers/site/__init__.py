"""Rotas públicas do site do consumidor (/api/site/{slug}/...).

Sem login. A loja vem do slug; loja inexistente, excluída, suspensa ou cancelada responde 404. Cada
requisição grava o contexto ``app.origem = 'site'`` e ``app.loja_id`` (RLS), sem funcionário: o que o
cliente cria fica com ``atualizado_por`` NULL e aparece na auditoria como "Cliente, pelo site".

Só sai o necessário: dados de contato da loja, serviços ativos, nome dos profissionais habilitados,
locais (sem links) e horários livres. Nada de outros clientes nem dados internos.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.db import definir_contexto
from app.models import Agendamento, AgendamentoMaterial, Cliente, Local, Loja, LojaConfiguracao, Servico
from app.models.enums import CanalCliente, OrigemAgendamento, StatusAgendamento, StatusLoja
from app.schemas.comum import Erro
from app.schemas.site import (
    DiaLivre,
    HorarioLivre,
    LocalPublico,
    LojaPublica,
    ProfissionalPublico,
    ServicoPublico,
    SolicitacaoEntrada,
    SolicitacaoSaida,
)
from app.services.acesso import modulos_da_loja
from app.services.agendamentos import materiais_do_servico
from app.services.comum import conflito, fuso, hoje, invalido, nao_encontrado, no_fuso
from app.services.horarios_livres import (
    DIAS_MAXIMOS,
    DURACAO_SEM_SERVICO,
    Agenda,
    Livre,
    locais_permitidos,
    profissionais,
)

router = APIRouter(
    prefix='/api/site/{slug}',
    tags=['Site do consumidor'],
    responses={404: {'model': Erro}, 422: {'model': Erro}},
)

MSG_LOJA_404 = 'Loja não encontrada.'
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


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


def obter_contexto_site(
    slug: Annotated[str, Path(max_length=60, description='Endereço da loja (ex.: clinica-sorriso)')],
    request: Request,
    db: DbDep,
) -> ContextoSite:
    if not SLUG.fullmatch(slug):
        raise nao_encontrado(MSG_LOJA_404)
    ip = ip_da_requisicao(request)
    definir_contexto(db, origem='site', ip=ip)
    loja = db.scalar(select(Loja).where(Loja.slug == slug))
    if loja is None or loja.status != StatusLoja.ativa:
        raise nao_encontrado(MSG_LOJA_404)
    # RLS: daqui em diante só enxerga os dados desta loja
    definir_contexto(db, origem='site', loja_id=loja.id, ip=ip)
    return ContextoSite(db=db, loja=loja, modulos=modulos_da_loja(db, loja.id), zona=fuso(loja.fuso_horario))


Site = Annotated[ContextoSite, Depends(obter_contexto_site)]


def _servico(ctx: ContextoSite, servico_id: UUID | None) -> Servico | None:
    """Serviço escolhido (ativo). Sem o módulo Serviços, não há serviço (atendimento genérico)."""
    if not ctx.usa_servicos:
        return None
    if servico_id is None:
        raise invalido('Escolha o serviço.')
    servico = ctx.db.scalar(
        select(Servico).where(Servico.id == servico_id, Servico.loja_id == ctx.loja.id, Servico.ativo)
    )
    if servico is None:
        raise invalido('Serviço não encontrado.')
    return servico


def _agenda(
    ctx: ContextoSite, servico: Servico | None, funcionario_id: UUID | None, primeiro: date, ultimo: date
) -> tuple[Agenda, dict[UUID, Local]]:
    candidatos = profissionais(ctx.db, ctx.loja.id, servico)
    if funcionario_id is not None:
        candidatos = [f for f in candidatos if f.id == funcionario_id]
        if not candidatos:
            raise invalido('Profissional não encontrado para este serviço.')
    locais = locais_permitidos(ctx.db, ctx.loja.id, servico) if ctx.usa_locais else None
    agenda = Agenda(
        ctx.db,
        ctx.loja.id,
        ctx.zona,
        candidatos,
        [local.id for local in locais] if locais is not None else None,
        primeiro,
        ultimo,
    )
    return agenda, {local.id: local for local in locais or []}


def _local(locais: dict[UUID, Local], local_id: UUID | None) -> LocalPublico | None:
    return LocalPublico.model_validate(locais[local_id]) if local_id in locais else None


def _horario(ctx: ContextoSite, livre: Livre, locais: dict[UUID, Local]) -> HorarioLivre:
    return HorarioLivre(
        hora=livre.inicio.astimezone(ctx.zona).strftime('%H:%M'),
        inicio=livre.inicio.astimezone(ctx.zona),
        funcionario_id=livre.funcionario.id,
        funcionario_nome=livre.funcionario.nome,
        local=_local(locais, livre.local_id),
    )


# --- Leitura -------------------------------------------------------------------------------------


@router.get('', summary='Dados públicos da loja')
def loja(ctx: Site) -> LojaPublica:
    dados = ctx.loja
    configuracao = ctx.db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == dados.id))
    return LojaPublica(
        tipo=dados.tipo,
        slug=dados.slug,
        nome_fantasia=dados.nome_fantasia or dados.nome,
        logo_url=dados.logo_url,
        telefone=dados.telefone,
        email=dados.email,
        logradouro=dados.logradouro,
        numero=dados.numero,
        complemento=dados.complemento,
        bairro=dados.bairro,
        cidade=dados.cidade,
        uf=dados.uf,
        fuso_horario=dados.fuso_horario,
        usa_servicos=ctx.usa_servicos,
        usa_locais=ctx.usa_locais,
        rotulo_local=configuracao.rotulo_local if configuracao else 'Local',
    )


@router.get('/servicos', summary='Serviços ativos com os profissionais habilitados')
def servicos(ctx: Site) -> list[ServicoPublico]:
    if not ctx.usa_servicos:
        equipe = profissionais(ctx.db, ctx.loja.id, None)
        return [
            ServicoPublico(
                id=None,
                nome='Atendimento',
                duracao_minutos=DURACAO_SEM_SERVICO,
                profissionais=[ProfissionalPublico.model_validate(f) for f in equipe],
            )
        ]
    saida = []
    for servico in ctx.db.scalars(
        select(Servico).where(Servico.loja_id == ctx.loja.id, Servico.ativo).order_by(Servico.nome)
    ):
        equipe = profissionais(ctx.db, ctx.loja.id, servico)
        if equipe:  # serviço sem ninguém para atender não aparece
            saida.append(
                ServicoPublico(
                    id=servico.id,
                    nome=servico.nome,
                    descricao=servico.descricao,
                    duracao_minutos=servico.duracao_minutos,
                    preco=servico.preco,
                    profissionais=[ProfissionalPublico.model_validate(f) for f in equipe],
                )
            )
    return saida


@router.get('/locais', summary='Locais ativos (vazio sem o módulo Locais)')
def locais(
    ctx: Site, servico_id: Annotated[UUID | None, Query(description='Só os permitidos para o serviço')] = None
) -> list[LocalPublico]:
    if not ctx.usa_locais:
        return []
    servico = _servico(ctx, servico_id) if servico_id is not None else None
    return [LocalPublico.model_validate(local) for local in locais_permitidos(ctx.db, ctx.loja.id, servico)]


@router.get('/horarios', summary='Horários livres por dia, para um serviço (e um profissional, opcional)')
def horarios(
    ctx: Site,
    servico_id: UUID | None = None,
    funcionario_id: Annotated[UUID | None, Query(description='Vazio = qualquer profissional')] = None,
    inicio: Annotated[date | None, Query(description='Primeiro dia (padrão: hoje)')] = None,
    fim: Annotated[date | None, Query(description='Último dia (padrão: o primeiro)')] = None,
) -> list[DiaLivre]:
    primeiro = inicio or hoje(ctx.zona)
    ultimo = fim or primeiro
    if ultimo < primeiro:
        raise invalido('O último dia deve ser depois do primeiro.')
    if (ultimo - primeiro).days >= DIAS_MAXIMOS:
        raise invalido(f'Consulte no máximo {DIAS_MAXIMOS} dias por vez.')
    servico = _servico(ctx, servico_id)
    duracao = servico.duracao_minutos if servico else DURACAO_SEM_SERVICO
    agenda, mapa_locais = _agenda(ctx, servico, funcionario_id, primeiro, ultimo)
    agora = datetime.now(UTC)
    dias = [primeiro + timedelta(days=i) for i in range((ultimo - primeiro).days + 1)]
    return [
        DiaLivre(
            data=dia,
            horarios=[
                _horario(ctx, livre, mapa_locais) for livre in agenda.livres_no_dia(dia, duracao, agora)
            ],
        )
        for dia in dias
    ]


# --- Pedido de agendamento -----------------------------------------------------------------------


def _cliente(ctx: ContextoSite, dados: SolicitacaoEntrada) -> Cliente:
    """Cliente pelo telefone: se já existe na loja, ganha o canal "site"; senão, é cadastrado.

    O cadastro existente não é alterado (nome e e-mail ficam como a loja registrou) e nada dele é
    devolvido, para o site não revelar dados de quem já é cliente.
    """
    digitos = re.sub(r'\D', '', dados.telefone)
    existente = ctx.db.scalar(
        select(Cliente)
        .where(
            Cliente.loja_id == ctx.loja.id,
            func.regexp_replace(Cliente.telefone, r'\D', '', 'g') == digitos,
        )
        .order_by(Cliente.criado_em, Cliente.id)
        .limit(1)
    )
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


@router.post(
    '/agendamentos',
    status_code=status.HTTP_201_CREATED,
    responses={409: {'model': Erro}},
    summary='Pedir um agendamento (entra como "Aguardando aceite" no painel da loja)',
)
def solicitar(dados: SolicitacaoEntrada, ctx: Site) -> SolicitacaoSaida:
    db = ctx.db
    servico = _servico(ctx, dados.servico_id)
    duracao = servico.duracao_minutos if servico else DURACAO_SEM_SERVICO
    inicio = no_fuso(dados.inicio, ctx.zona)
    dia = inicio.astimezone(ctx.zona).date()
    agenda, mapa_locais = _agenda(ctx, servico, dados.funcionario_id, dia, dia)

    # O horário precisa ser um dos oferecidos (jornada, bloqueios, antecedência e ocupação)
    livre = next(
        (h for h in agenda.livres_no_dia(dia, duracao, datetime.now(UTC)) if h.inicio == inicio), None
    )
    if livre is None:
        raise conflito('Este horário não está mais disponível. Escolha outro horário.')
    local_id = livre.local_id
    if dados.local_id is not None and ctx.usa_locais:
        if dados.local_id not in mapa_locais:
            raise invalido('Local não encontrado para este serviço.')
        if dados.local_id not in agenda.locais_livres(livre.inicio, livre.fim):
            raise conflito('Este local já está ocupado nesse horário. Escolha outro horário.')
        local_id = dados.local_id

    cliente = _cliente(ctx, dados)
    db.flush()
    agendamento = Agendamento(
        loja_id=ctx.loja.id,
        cliente_id=cliente.id,
        servico_id=servico.id if servico else None,
        funcionario_id=livre.funcionario.id,
        local_id=local_id,
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
        servico_nome=servico.nome if servico else 'Atendimento',
        funcionario_nome=livre.funcionario.nome,
        local=_local(mapa_locais, local_id),
        preco=agendamento.preco,
        cliente_nome=dados.nome,
        mensagem=f'Pedido enviado. {ctx.loja.nome_fantasia or ctx.loja.nome} vai confirmar o seu horário.',
    )
