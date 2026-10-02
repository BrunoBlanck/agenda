"""Serviços com os vínculos (profissionais, locais e materiais), montados em poucas consultas."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Funcionario,
    Local,
    Material,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
    ServicoMaterial,
)
from app.schemas.comum import Referencia
from app.schemas.servicos import LocalDoServico, MaterialDoServicoSaida, ServicoSaida
from app.services.comum import com_autor


def descrever_servicos(
    db: Session,
    loja_id: UUID,
    servicos: Sequence[Servico],
    *,
    com_locais: bool,
    com_materiais: bool,
    so_profissionais_ativos: bool = False,
) -> list[ServicoSaida]:
    """Serviços com profissionais, locais (se o módulo Locais estiver ativo) e materiais (idem)."""
    ids = [s.id for s in servicos]
    saida = {s.id: ServicoSaida.model_validate(s) for s in servicos}

    consulta = (
        select(ServicoFuncionario.servico_id, Funcionario.id, Funcionario.nome)
        .join(
            Funcionario,
            (Funcionario.id == ServicoFuncionario.funcionario_id)
            & (Funcionario.loja_id == ServicoFuncionario.loja_id),
        )
        .where(ServicoFuncionario.loja_id == loja_id, ServicoFuncionario.servico_id.in_(ids))
        .order_by(Funcionario.nome)
    )
    if so_profissionais_ativos:
        consulta = consulta.where(Funcionario.ativo)
    for servico_id, funcionario_id, nome in db.execute(consulta):
        saida[servico_id].funcionario_ids.append(funcionario_id)
        saida[servico_id].profissionais.append(Referencia(id=funcionario_id, nome=nome))

    if com_locais:
        for servico_id, local in db.execute(
            select(ServicoLocal.servico_id, Local)
            .join(Local, (Local.id == ServicoLocal.local_id) & (Local.loja_id == ServicoLocal.loja_id))
            .where(ServicoLocal.loja_id == loja_id, ServicoLocal.servico_id.in_(ids))
            .order_by(Local.nome)
        ):
            saida[servico_id].local_ids.append(local.id)
            saida[servico_id].locais.append(LocalDoServico(id=local.id, nome=local.nome, tipo=local.tipo))

    if com_materiais:
        for servico_id, quantidade, material in db.execute(
            select(ServicoMaterial.servico_id, ServicoMaterial.quantidade, Material)
            .join(
                Material,
                (Material.id == ServicoMaterial.material_id) & (Material.loja_id == ServicoMaterial.loja_id),
            )
            .where(ServicoMaterial.loja_id == loja_id, ServicoMaterial.servico_id.in_(ids))
            .order_by(Material.nome)
        ):
            saida[servico_id].materiais.append(
                MaterialDoServicoSaida(
                    material_id=material.id,
                    nome=material.nome,
                    unidade=material.unidade,
                    quantidade=quantidade,
                )
            )
    return com_autor(db, loja_id, list(saida.values()))
