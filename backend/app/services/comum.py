"""Ajudantes usados por todas as rotas da loja: busca com 404, exclusão lógica, vínculos e autores."""

import logging
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db import FUSO_PADRAO
from app.models import Funcionario
from app.schemas.comum import MSG_NASCIMENTO, Paginacao, nascimento_valido

log = logging.getLogger('app.services')


def nao_encontrado(mensagem: str = 'Não encontrado.') -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, mensagem)


def invalido(mensagem: str) -> HTTPException:
    """Regra de negócio violada pelos dados enviados (422)."""
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem)


def conflito(mensagem: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, mensagem)


def proibido(mensagem: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, mensagem)


def buscar[M](
    db: Session,
    modelo: type[M],
    loja_id: UUID,
    id_: UUID,
    mensagem: str = 'Não encontrado.',
    *,
    travar: bool = False,
) -> M:
    """Linha da loja (não excluída) pelo id; 404 se não existir ou for de outra loja.

    Recurso de outra loja responde 404 (e não 403) para não revelar que ele existe.
    travar=True: SELECT ... FOR UPDATE até o fim da transação (regras "conferir e gravar").
    """
    consulta = select(modelo).where(modelo.id == id_, modelo.loja_id == loja_id)  # type: ignore[attr-defined]
    if travar:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    obj = db.scalar(consulta)
    if obj is None:
        raise nao_encontrado(mensagem)
    return obj


def excluir(db: Session, obj: Any) -> None:
    """Exclusão lógica: o trigger preenche excluido_por (e a auditoria registra 'excluir')."""
    obj.excluido_em = func.now()
    db.flush()


def sincronizar_vinculos(
    db: Session,
    modelo: type,
    loja_id: UUID,
    fixo: dict[str, Any],
    coluna: str,
    desejados: dict[UUID, dict[str, Any]],
) -> None:
    """Deixa a tabela de ligação igual a ``desejados`` (id -> demais colunas).

    - vínculo novo: insere;
    - vínculo excluído antes e religado agora: restaura a linha existente (excluido_em = NULL);
    - vínculo que saiu: exclusão lógica;
    - colunas extras (ex.: quantidade) são atualizadas quando mudam.
    """
    filtros = [modelo.loja_id == loja_id] + [getattr(modelo, c) == v for c, v in fixo.items()]
    existentes = {
        getattr(linha, coluna): linha
        for linha in db.scalars(select(modelo).where(*filtros).execution_options(incluir_excluidos=True))
    }
    for alvo, extras in desejados.items():
        linha = existentes.get(alvo)
        if linha is None:
            db.add(modelo(loja_id=loja_id, **fixo, **{coluna: alvo}, **extras))
            continue
        if linha.excluido_em is not None:
            linha.excluido_em = None
        for chave, valor in extras.items():
            if getattr(linha, chave) != valor:
                setattr(linha, chave, valor)
    for alvo, linha in existentes.items():
        if alvo not in desejados and linha.excluido_em is None:
            linha.excluido_em = func.now()
    db.flush()


def nomes_funcionarios(db: Session, loja_id: UUID, ids: Iterable[UUID | None]) -> dict[UUID, str]:
    """Nome de cada funcionário (inclusive excluídos, para histórico)."""
    alvo = {i for i in ids if i is not None}
    if not alvo:
        return {}
    linhas = db.execute(
        select(Funcionario.id, Funcionario.nome)
        .where(Funcionario.loja_id == loja_id, Funcionario.id.in_(alvo))
        .execution_options(incluir_excluidos=True)
    ).all()
    return dict(linhas)


def com_autor[S: BaseModel](db: Session, loja_id: UUID, itens: Sequence[S]) -> list[S]:
    """Preenche atualizado_por_nome (schemas que herdam de Controle) com uma consulta só."""
    nomes = nomes_funcionarios(db, loja_id, (getattr(i, 'atualizado_por', None) for i in itens))
    for item in itens:
        autor = getattr(item, 'atualizado_por', None)
        if autor is not None:
            item.atualizado_por_nome = nomes.get(autor)  # type: ignore[attr-defined]
    return list(itens)


# ---------------------------------------------------------------------------------------------
# Datas no fuso da loja
# ---------------------------------------------------------------------------------------------


@lru_cache(maxsize=128)  # o aviso sai uma vez por nome, não a cada requisição
def fuso(fuso_horario: str) -> ZoneInfo:
    """Fuso da loja. Nome desconhecido (dado antigo ou base de fusos desatualizada) não derruba a
    requisição: vale o fuso padrão e o problema fica no log (a validação da loja já barra na entrada).
    """
    try:
        return ZoneInfo(fuso_horario)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning('Fuso horário desconhecido (%r); usando %s', fuso_horario, FUSO_PADRAO)
        return ZoneInfo(FUSO_PADRAO)


def no_fuso(momento: datetime, zona: ZoneInfo) -> datetime:
    """Data/hora com fuso. Sem fuso (ex.: '2026-10-02T09:00'), vale o horário da loja."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=zona)
    return momento


def inicio_do_dia(dia: date, zona: ZoneInfo) -> datetime:
    return datetime.combine(dia, time.min, tzinfo=zona)


def intervalo_de_dias(inicio: date, fim: date, zona: ZoneInfo) -> tuple[datetime, datetime]:
    """[00:00 do primeiro dia, 00:00 do dia seguinte ao último) no fuso da loja."""
    return inicio_do_dia(inicio, zona), inicio_do_dia(fim + timedelta(days=1), zona)


def dia_semana(momento: datetime) -> int:
    """0 = domingo ... 6 = sábado (como em perfil_horarios)."""
    return (momento.weekday() + 1) % 7


def paginar(db: Session, consulta: Select, pag: Paginacao) -> tuple[list[Any], int]:
    """Executa a consulta paginada e devolve (linhas, total)."""
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    linhas = list(db.scalars(consulta.limit(pag.por_pagina).offset(pag.offset)))
    return linhas, total


def hoje(zona: ZoneInfo) -> date:
    """Data de hoje no fuso da loja."""
    return datetime.now(zona).date()


def erro_de_campo(campo: str, mensagem: str) -> RequestValidationError:
    """422 no mesmo formato da validação do corpo: {detail, erros: [{campo, mensagem}]}.

    Para regras de um campo que só a rota consegue conferir (ex.: depende do fuso da loja).
    """
    return RequestValidationError([{'type': 'regra', 'loc': ('body', campo), 'msg': mensagem}])


def conferir_nascimento(data_nascimento: date | None, zona: ZoneInfo) -> None:
    """Data de nascimento no futuro, considerando o dia de hoje no fuso da loja (GER-15): 422."""
    if data_nascimento is not None and not nascimento_valido(data_nascimento, hoje(zona)):
        raise erro_de_campo('data_nascimento', MSG_NASCIMENTO)
