"""Controle de Tempo (/api/loja/ponto). Recursos: ponto_proprio e ponto_equipe (módulo controle_tempo).

- Entrada e saída usam a hora do servidor, nunca a do navegador. O pedido diz a ação (entrada ou
  saída): se não bater com a situação atual (ex.: dois cliques), responde 409.
- Só um registro em aberto por funcionário (índice único no banco) e nenhum período sobreposto do
  mesmo funcionário (EXCLUDE no banco, conferido antes para a mensagem sair clara).
- Correções e lançamentos manuais: escrita em Ponto da equipe, com justificativa (origem manual).
- Horas trabalhadas = saída - entrada, calculadas na consulta; a data usa o fuso da loja.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Funcionario, RegistroPonto
from app.models.enums import NivelAcesso, OrigemPonto
from app.schemas.comum import Data, Erro
from app.schemas.ponto import (
    CorrecaoEntrada,
    FuncionarioPonto,
    PontoManualEntrada,
    PontoPeriodo,
    RegistrarEntrada,
    RegistroFeito,
    RegistroSaida,
    TotalDia,
)
from app.services.comum import (
    buscar,
    com_autor,
    conflito,
    fuso,
    hoje,
    intervalo_de_dias,
    invalido,
    nao_encontrado,
    no_fuso,
    nomes_funcionarios,
    proibido,
)

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(prefix='/ponto', tags=['Loja: controle de tempo'], responses=ERROS)

PONTO = ('ponto_proprio', 'ponto_equipe')
Leitura = Annotated[ContextoLoja, Depends(exigir(PONTO))]
Escrita = Annotated[ContextoLoja, Depends(exigir(PONTO, 'escrita'))]
Correcao = Annotated[ContextoLoja, Depends(exigir('ponto_equipe', 'escrita'))]
Equipe = Annotated[ContextoLoja, Depends(exigir('ponto_equipe'))]
MAX_DIAS = 62
MSG_404 = 'Registro de ponto não encontrado.'
MSG_SOBREPOSTO = 'Este funcionário já tem um registro de ponto nesse período.'
MSG_JA_ABERTO = 'Este funcionário já tem um registro de ponto em aberto.'
MSG_JA_EM_SERVICO = 'A entrada já foi registrada. Para encerrar, registre a saída.'
MSG_SEM_ENTRADA = 'Não há entrada em aberto. Registre a entrada primeiro.'


def _minutos(r: RegistroPonto) -> int | None:
    return int((r.saida - r.entrada).total_seconds() // 60) if r.saida else None


def _saida(ctx: ContextoLoja, registros: list[RegistroPonto], zona: ZoneInfo) -> list[RegistroSaida]:
    nomes = nomes_funcionarios(
        ctx.db, ctx.loja_id, [r.funcionario_id for r in registros] + [r.editado_por for r in registros]
    )
    saida = []
    for r in registros:
        item = RegistroSaida.model_validate(r)
        item.entrada = r.entrada.astimezone(zona)
        item.saida = r.saida.astimezone(zona) if r.saida else None
        item.data = item.entrada.date()
        item.minutos = _minutos(r)
        item.funcionario_nome = nomes.get(r.funcionario_id)
        item.editado_por_nome = nomes.get(r.editado_por) if r.editado_por else None
        saida.append(item)
    return com_autor(ctx.db, ctx.loja_id, saida)


def _travar_funcionario(ctx: ContextoLoja, funcionario_id: UUID) -> None:
    """Serializa as alterações de ponto do mesmo funcionário (advisory lock até o fim da transação).

    Dois cliques simultâneos em "registrar" ou dois lançamentos ao mesmo tempo: o segundo espera o
    primeiro e já vê o que ele gravou.
    """
    ctx.db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f'ponto:{funcionario_id}', 0))))


def _conferir_sobreposicao(
    ctx: ContextoLoja,
    funcionario_id: UUID,
    entrada: datetime,
    saida: datetime | None,
    exceto: UUID | None = None,
) -> None:
    """409 se o período [entrada, saída) encosta em outro registro do funcionário (aberto = sem fim)."""
    if saida is None:
        aberto = select(RegistroPonto.id).where(
            RegistroPonto.loja_id == ctx.loja_id,
            RegistroPonto.funcionario_id == funcionario_id,
            RegistroPonto.saida.is_(None),
            *([RegistroPonto.id != exceto] if exceto is not None else []),
        )
        if ctx.db.scalar(aberto.limit(1)) is not None:
            raise conflito(MSG_JA_ABERTO)
    condicoes = [
        RegistroPonto.loja_id == ctx.loja_id,
        RegistroPonto.funcionario_id == funcionario_id,
        (RegistroPonto.saida.is_(None)) | (RegistroPonto.saida > entrada),
    ]
    if saida is not None:
        condicoes.append(RegistroPonto.entrada < saida)
    if exceto is not None:
        condicoes.append(RegistroPonto.id != exceto)
    if ctx.db.scalar(select(RegistroPonto.id).where(*condicoes).limit(1)) is not None:
        raise conflito(MSG_SOBREPOSTO)


def _horarios(ctx: ContextoLoja, dados: CorrecaoEntrada) -> tuple[datetime, datetime | None]:
    zona = fuso(ctx.loja.fuso_horario)
    entrada = no_fuso(dados.entrada, zona)
    saida = no_fuso(dados.saida, zona) if dados.saida else None
    agora = datetime.now(zona) + timedelta(minutes=1)
    if entrada > agora or (saida and saida > agora):
        raise invalido('O registro de ponto não pode ficar no futuro.')
    if saida is not None and saida <= entrada:
        raise invalido('A saída deve ser depois da entrada.')
    return entrada, saida


@router.get('', summary='Registros de ponto do período e o total por dia')
def listar(
    ctx: Leitura,
    inicio: Annotated[Data | None, Query(description='Padrão: hoje (no fuso da loja)')] = None,
    fim: Annotated[Data | None, Query(description='Último dia, inclusive (padrão: o início)')] = None,
    funcionario_id: Annotated[UUID | None, Query(description='Só deste funcionário')] = None,
) -> PontoPeriodo:
    zona = fuso(ctx.loja.fuso_horario)
    inicio = inicio or hoje(zona)
    fim = fim or inicio
    if fim < inicio:
        raise invalido('O fim do período deve ser depois do início.')
    if fim - inicio > timedelta(days=MAX_DIAS):
        raise invalido(f'O período pode ter no máximo {MAX_DIAS} dias.')
    de, ate = intervalo_de_dias(inicio, fim, zona)
    consulta = select(RegistroPonto).where(
        RegistroPonto.loja_id == ctx.loja_id, RegistroPonto.entrada >= de, RegistroPonto.entrada < ate
    )
    if not ctx.pode('ponto_equipe'):
        funcionario_id = ctx.funcionario.id  # só os próprios
    if funcionario_id is not None:
        consulta = consulta.where(RegistroPonto.funcionario_id == funcionario_id)
    registros = list(ctx.db.scalars(consulta.order_by(RegistroPonto.entrada, RegistroPonto.id)))
    saida = _saida(ctx, registros, zona)

    totais: dict[tuple[UUID, date], int] = defaultdict(int)
    nomes: dict[UUID, str | None] = {}
    for item in saida:
        nomes[item.funcionario_id] = item.funcionario_nome
        if item.minutos is not None and item.data is not None:
            totais[item.funcionario_id, item.data] += item.minutos
    return PontoPeriodo(
        inicio=inicio,
        fim=fim,
        registros=saida,
        totais=[
            TotalDia(funcionario_id=f, funcionario_nome=nomes.get(f), data=d, minutos=m)
            for (f, d), m in sorted(totais.items(), key=lambda t: (t[0][1], nomes.get(t[0][0]) or ''))
        ],
    )


@router.get('/funcionarios', summary='Funcionários para o ponto da equipe (escolher, lançar e filtrar)')
def funcionarios(ctx: Equipe) -> list[FuncionarioPonto]:
    """Lista de apoio de Ponto da equipe: não exige acesso a Funcionários. Inclui os inativos (filtro)."""
    return [
        FuncionarioPonto.model_validate(f)
        for f in ctx.db.scalars(
            select(Funcionario)
            .where(Funcionario.loja_id == ctx.loja_id)
            .order_by(func.lower(Funcionario.nome), Funcionario.id)
        )
    ]


@router.get('/aberto', summary='Registro em aberto (em serviço) do funcionário, se houver')
def aberto(ctx: Leitura, funcionario_id: UUID | None = None) -> RegistroSaida | None:
    alvo = funcionario_id or ctx.funcionario.id
    if alvo != ctx.funcionario.id and not ctx.pode('ponto_equipe'):
        raise proibido('Você só pode ver o seu próprio ponto.')
    registro = ctx.db.scalar(
        select(RegistroPonto).where(
            RegistroPonto.loja_id == ctx.loja_id,
            RegistroPonto.funcionario_id == alvo,
            RegistroPonto.saida.is_(None),
        )
    )
    return _saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0] if registro else None


@router.post('/registrar', summary='Registrar entrada ou saída agora (hora do servidor)')
def registrar(dados: RegistrarEntrada, ctx: Escrita) -> RegistroFeito:
    alvo = dados.funcionario_id or ctx.funcionario.id
    if alvo == ctx.funcionario.id:
        if not ctx.pode('ponto_proprio', NivelAcesso.escrita) and not ctx.pode(
            'ponto_equipe', NivelAcesso.escrita
        ):
            raise proibido('Você não tem permissão para registrar o ponto.')
    elif not ctx.pode('ponto_equipe', NivelAcesso.escrita):
        raise proibido('Você só pode registrar o seu próprio ponto.')
    funcionario = buscar(ctx.db, Funcionario, ctx.loja_id, alvo, 'Funcionário não encontrado.')
    if not funcionario.ativo:
        raise invalido('Funcionário inativo não registra ponto.')
    _travar_funcionario(ctx, funcionario.id)
    agora = datetime.now(fuso(ctx.loja.fuso_horario)).replace(microsecond=0)
    registro = ctx.db.scalar(
        select(RegistroPonto)
        .where(
            RegistroPonto.loja_id == ctx.loja_id,
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.saida.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    if dados.acao == 'saida':
        if registro is None:
            raise conflito(MSG_SEM_ENTRADA)
        registro.saida = max(agora, registro.entrada + timedelta(seconds=1))
    else:
        if registro is not None:
            raise conflito(MSG_JA_EM_SERVICO)
        _conferir_sobreposicao(ctx, funcionario.id, agora, None)
        registro = RegistroPonto(
            loja_id=ctx.loja_id, funcionario_id=funcionario.id, entrada=agora, origem=OrigemPonto.sistema
        )
        ctx.db.add(registro)
    ctx.db.flush()
    return RegistroFeito(acao=dados.acao, registro=_saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0])


@router.post('', status_code=status.HTTP_201_CREATED, summary='Lançamento manual (com justificativa)')
def lancar(dados: PontoManualEntrada, ctx: Correcao) -> RegistroSaida:
    funcionario = buscar(
        ctx.db, Funcionario, ctx.loja_id, dados.funcionario_id, 'Funcionário não encontrado.'
    )
    entrada, saida = _horarios(ctx, dados)
    _travar_funcionario(ctx, funcionario.id)
    _conferir_sobreposicao(ctx, funcionario.id, entrada, saida)
    registro = RegistroPonto(
        loja_id=ctx.loja_id,
        funcionario_id=funcionario.id,
        entrada=entrada,
        saida=saida,
        origem=OrigemPonto.manual,
        justificativa=dados.justificativa,
        editado_por=ctx.funcionario.id,
    )
    ctx.db.add(registro)
    ctx.db.flush()
    return _saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0]


@router.put('/{registro_id}', summary='Corrigir registro (com justificativa)')
def corrigir(registro_id: UUID, dados: CorrecaoEntrada, ctx: Correcao) -> RegistroSaida:
    registro = ctx.db.scalar(
        select(RegistroPonto).where(RegistroPonto.id == registro_id, RegistroPonto.loja_id == ctx.loja_id)
    )
    if registro is None:
        raise nao_encontrado(MSG_404)
    entrada, saida = _horarios(ctx, dados)
    _travar_funcionario(ctx, registro.funcionario_id)
    _conferir_sobreposicao(ctx, registro.funcionario_id, entrada, saida, exceto=registro.id)
    registro.entrada, registro.saida = entrada, saida
    registro.origem = OrigemPonto.manual
    registro.justificativa = dados.justificativa
    registro.editado_por = ctx.funcionario.id
    ctx.db.flush()
    return _saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0]
