"""Estoque (estrutura.md, 2.11, 2.14 e 2.15).

materiais.quantidade_atual só muda por movimentacoes_estoque: um trigger soma a quantidade da
movimentação na mesma transação. Movimentações nunca são alteradas nem excluídas.

📌 Ponto em aberto (estrutura.md, 5): o estoque pode ficar negativo. Decisão conservadora desta
etapa: a conclusão do atendimento NÃO é bloqueada por falta de estoque (o material passa a
aparecer como "Repor"). Para bloquear, troque PERMITIR_ESTOQUE_NEGATIVO para False.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgendamentoMaterial, Material, MovimentacaoEstoque
from app.models.enums import TipoMovimentacao
from app.services.comum import conflito, invalido

PERMITIR_ESTOQUE_NEGATIVO = True
MOTIVO_ESTORNO = 'Estorno: atendimento reaberto'
SALDO_MAXIMO = Decimal('99999999.99')  # materiais.quantidade_atual é numeric(10,2)
MSG_SALDO = 'Com esta movimentação o estoque passaria do limite permitido (99.999.999,99).'


def lancar(
    db: Session,
    loja_id: UUID,
    material_id: UUID,
    tipo: TipoMovimentacao,
    quantidade: Decimal,
    motivo: str | None = None,
    agendamento_id: UUID | None = None,
) -> MovimentacaoEstoque:
    """Lança a movimentação (o trigger soma no material).

    Trava o material (FOR UPDATE) e confere o saldo resultante antes de gravar: o numeric(10,2) não
    estoura e lançamentos simultâneos no mesmo material somam um depois do outro.
    """
    material = db.scalar(
        select(Material)
        .where(Material.loja_id == loja_id, Material.id == material_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if material is not None and abs(material.quantidade_atual + quantidade) > SALDO_MAXIMO:
        raise invalido(MSG_SALDO)
    movimentacao = MovimentacaoEstoque(
        loja_id=loja_id,
        material_id=material_id,
        tipo=tipo,
        quantidade=quantidade,
        motivo=motivo,
        agendamento_id=agendamento_id,
    )
    db.add(movimentacao)
    db.flush()
    # O trigger mudou a quantidade no banco: relê o material
    if material is not None:
        db.refresh(material, ['quantidade_atual'])
    return movimentacao


def baixar_materiais(db: Session, loja_id: UUID, agendamento_id: UUID) -> None:
    """Atendimento concluído: uma saída por material usado (agendamento_materiais)."""
    # Sempre na ordem de material_id: duas baixas simultâneas travam os materiais na mesma ordem
    # (sem deadlock entre atendimentos que usam os mesmos materiais)
    usados = db.scalars(
        select(AgendamentoMaterial)
        .where(AgendamentoMaterial.loja_id == loja_id, AgendamentoMaterial.agendamento_id == agendamento_id)
        .order_by(AgendamentoMaterial.material_id)
    ).all()
    if not PERMITIR_ESTOQUE_NEGATIVO:
        for uso in usados:
            atual = db.scalar(select(Material.quantidade_atual).where(Material.id == uso.material_id))
            if atual is not None and atual < uso.quantidade:
                raise conflito('Estoque insuficiente para concluir o atendimento.')
    for uso in usados:
        lancar(
            db,
            loja_id,
            uso.material_id,
            TipoMovimentacao.saida_atendimento,
            -uso.quantidade,
            agendamento_id=agendamento_id,
        )


def estornar_materiais(db: Session, loja_id: UUID, agendamento_id: UUID) -> None:
    """Atendimento concluído reaberto: devolve ao estoque o saldo que saiu por ele (nada é apagado)."""
    saldos = db.execute(
        select(MovimentacaoEstoque.material_id, func.sum(MovimentacaoEstoque.quantidade))
        .where(MovimentacaoEstoque.loja_id == loja_id, MovimentacaoEstoque.agendamento_id == agendamento_id)
        .group_by(MovimentacaoEstoque.material_id)
        .order_by(MovimentacaoEstoque.material_id)
    ).all()
    for material_id, saldo in saldos:
        if saldo < 0:
            lancar(
                db,
                loja_id,
                material_id,
                TipoMovimentacao.ajuste,
                -saldo,
                MOTIVO_ESTORNO,
                agendamento_id=agendamento_id,
            )
