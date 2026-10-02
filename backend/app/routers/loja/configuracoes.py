"""Configurações › Dados da loja (/api/loja/configuracoes/loja). Recurso: config_loja.

Grava direto em lojas (estrutura.md, 2.18). O trigger preenche atualizado_por_funcionario.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.auth.catalogo import MODULOS
from app.auth.dependencias import ContextoLoja, exigir
from app.models import Auditoria, Funcionario, Plano, SuperadminUsuario
from app.schemas.comum import Erro
from app.schemas.configuracoes import DadosLoja, DadosLojaEntrada

router = APIRouter(
    prefix='/configuracoes/loja',
    tags=['Loja: configurações'],
    responses={403: {'model': Erro}, 409: {'model': Erro}},
)

Leitura = Annotated[ContextoLoja, Depends(exigir('config_loja'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('config_loja', 'escrita'))]


def _dados(ctx: ContextoLoja) -> DadosLoja:
    db, loja = ctx.db, ctx.loja
    plano = db.scalar(select(Plano.nome).where(Plano.id == loja.plano_id)) if loja.plano_id else None
    # Quem fez a última alteração: a auditoria diz se foi a loja ou o superadmin
    ultima = db.execute(
        select(Auditoria.funcionario_id, Auditoria.superadmin_id)
        .where(Auditoria.loja_id == loja.id, Auditoria.tabela == 'lojas')
        .order_by(Auditoria.id.desc())
        .limit(1)
    ).first()
    autor, nome = None, None
    if ultima is not None and ultima.funcionario_id:
        autor = 'funcionario'
        nome = db.scalar(
            select(Funcionario.nome)
            .where(Funcionario.id == ultima.funcionario_id, Funcionario.loja_id == loja.id)
            .execution_options(incluir_excluidos=True)
        )
    elif ultima is not None and ultima.superadmin_id:
        autor = 'superadmin'
        nome = db.scalar(
            select(SuperadminUsuario.nome)
            .where(SuperadminUsuario.id == ultima.superadmin_id)
            .execution_options(incluir_excluidos=True)
        )
    return DadosLoja(
        **{campo: getattr(loja, campo) for campo in DadosLojaEntrada.model_fields},
        logo_url=loja.logo_url,
        tipo=loja.tipo,
        slug=loja.slug,
        plano_nome=plano,
        status=loja.status,
        fuso_horario=loja.fuso_horario,
        modulos={codigo: ctx.acesso.modulo_ativo(codigo) for codigo, opcional in MODULOS.items() if opcional},
        atualizado_em=loja.atualizado_em,
        atualizado_por=autor,
        atualizado_por_nome=nome,
    )


@router.get('', summary='Dados da loja')
def obter(ctx: Leitura) -> DadosLoja:
    return _dados(ctx)


@router.put('', summary='Editar os dados da loja (nome, razão social, contato, endereço e CNPJ)')
def editar(dados: DadosLojaEntrada, ctx: Escrita) -> DadosLoja:
    for campo, valor in dados.model_dump().items():
        if getattr(ctx.loja, campo) != valor:
            setattr(ctx.loja, campo, valor)
    ctx.db.flush()
    return _dados(ctx)


@router.delete(
    '/logo',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Remover a logo (o envio de arquivo chega junto com o storage)',
)
def remover_logo(ctx: Escrita) -> None:
    ctx.loja.logo_url = None
    ctx.db.flush()
