"""Controle de Tempo (/api/loja/ponto). Recursos: ponto_proprio e ponto_equipe (módulo controle_tempo).

- Entrada e saída usam a hora do servidor, nunca a do navegador.
- Só um registro em aberto por funcionário (índice único no banco).
- Correções e lançamentos manuais: escrita em Ponto da equipe, com justificativa (origem manual).
- Horas trabalhadas = saída - entrada, calculadas na consulta; a data usa o fuso da loja.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import Funcionario, RegistroPonto
from app.models.enums import NivelAcesso, OrigemPonto
from app.schemas.comum import Erro
from app.schemas.ponto import (
    CorrecaoEntrada,
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
MAX_DIAS = 62
MSG_404 = 'Registro de ponto não encontrado.'


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
    inicio: Annotated[date | None, Query(description='Padrão: hoje (no fuso da loja)')] = None,
    fim: Annotated[date | None, Query(description='Último dia, inclusive (padrão: o início)')] = None,
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
def registrar(ctx: Escrita, dados: RegistrarEntrada | None = None) -> RegistroFeito:
    alvo = (dados.funcionario_id if dados else None) or ctx.funcionario.id
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
    agora = datetime.now(fuso(ctx.loja.fuso_horario)).replace(microsecond=0)
    registro = ctx.db.scalar(
        select(RegistroPonto).where(
            RegistroPonto.loja_id == ctx.loja_id,
            RegistroPonto.funcionario_id == funcionario.id,
            RegistroPonto.saida.is_(None),
        )
    )
    if registro is not None:
        registro.saida = max(agora, registro.entrada + timedelta(seconds=1))
        acao = 'saida'
    else:
        registro = RegistroPonto(
            loja_id=ctx.loja_id, funcionario_id=funcionario.id, entrada=agora, origem=OrigemPonto.sistema
        )
        ctx.db.add(registro)
        acao = 'entrada'
    ctx.db.flush()
    return RegistroFeito(acao=acao, registro=_saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0])


@router.post('', status_code=status.HTTP_201_CREATED, summary='Lançamento manual (com justificativa)')
def lancar(dados: PontoManualEntrada, ctx: Correcao) -> RegistroSaida:
    funcionario = buscar(
        ctx.db, Funcionario, ctx.loja_id, dados.funcionario_id, 'Funcionário não encontrado.'
    )
    entrada, saida = _horarios(ctx, dados)
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
    registro.entrada, registro.saida = _horarios(ctx, dados)
    registro.origem = OrigemPonto.manual
    registro.justificativa = dados.justificativa
    registro.editado_por = ctx.funcionario.id
    ctx.db.flush()
    return _saida(ctx, [registro], fuso(ctx.loja.fuso_horario))[0]
