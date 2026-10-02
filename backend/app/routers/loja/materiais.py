"""Materiais, categorias e estoque (/api/loja/materiais, /api/loja/categorias-material). Recurso: materiais.

O estoque (materiais.quantidade_atual) só muda por movimentacoes_estoque: o cadastro lança a
quantidade inicial como entrada, e entradas, ajustes e perdas são lançados à parte. A saída por
atendimento é automática, ao concluir o agendamento (app/services/estoque.py).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import exists, func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.models import CategoriaMaterial, Material, MovimentacaoEstoque, Servico, ServicoMaterial
from app.models.enums import TipoMovimentacao
from app.schemas.comum import Erro, Pagina, Paginacao, paginacao
from app.schemas.materiais import (
    CategoriaEntrada,
    CategoriaSaida,
    MaterialEdicao,
    MaterialNovo,
    MaterialSaida,
    MovimentacaoEntrada,
    MovimentacaoSaida,
)
from app.services.comum import buscar, com_autor, conflito, excluir, invalido, nomes_funcionarios, paginar
from app.services.estoque import lancar

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(tags=['Loja: materiais'], responses=ERROS)

MSG_404 = 'Material não encontrado.'
MSG_CATEGORIA_404 = 'Categoria não encontrada.'

Leitura = Annotated[ContextoLoja, Depends(exigir('materiais'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('materiais', 'escrita'))]


def _materiais(ctx: ContextoLoja, materiais: list[Material]) -> list[MaterialSaida]:
    ids_categoria = {m.categoria_id for m in materiais if m.categoria_id}
    categorias = dict(
        ctx.db.execute(
            select(CategoriaMaterial.id, CategoriaMaterial.nome)
            .where(CategoriaMaterial.loja_id == ctx.loja_id, CategoriaMaterial.id.in_(ids_categoria))
            .execution_options(incluir_excluidos=True)
        ).all()
    )
    saida = []
    for m in materiais:
        item = MaterialSaida.model_validate(m)
        item.categoria_nome = categorias.get(m.categoria_id) if m.categoria_id else None
        item.repor = m.quantidade_atual < m.estoque_minimo
        saida.append(item)
    return com_autor(ctx.db, ctx.loja_id, saida)


def _validar_categoria(ctx: ContextoLoja, categoria_id: UUID | None) -> None:
    if categoria_id is not None:
        existe = ctx.db.scalar(
            select(CategoriaMaterial.id).where(
                CategoriaMaterial.id == categoria_id, CategoriaMaterial.loja_id == ctx.loja_id
            )
        )
        if existe is None:
            raise invalido(MSG_CATEGORIA_404)


# --- Categorias --------------------------------------------------------------------------------


def _categorias(ctx: ContextoLoja, categorias: list[CategoriaMaterial]) -> list[CategoriaSaida]:
    return com_autor(ctx.db, ctx.loja_id, [CategoriaSaida.model_validate(c) for c in categorias])


@router.get('/categorias-material', summary='Categorias de material')
def listar_categorias(ctx: Leitura) -> list[CategoriaSaida]:
    consulta = select(CategoriaMaterial).where(CategoriaMaterial.loja_id == ctx.loja_id)
    return _categorias(ctx, list(ctx.db.scalars(consulta.order_by(func.lower(CategoriaMaterial.nome)))))


@router.post('/categorias-material', status_code=status.HTTP_201_CREATED, summary='Cadastrar categoria')
def criar_categoria(dados: CategoriaEntrada, ctx: Escrita) -> CategoriaSaida:
    categoria = CategoriaMaterial(loja_id=ctx.loja_id, nome=dados.nome)
    ctx.db.add(categoria)
    ctx.db.flush()
    return _categorias(ctx, [categoria])[0]


@router.put('/categorias-material/{categoria_id}', summary='Renomear categoria')
def editar_categoria(categoria_id: UUID, dados: CategoriaEntrada, ctx: Escrita) -> CategoriaSaida:
    categoria = buscar(ctx.db, CategoriaMaterial, ctx.loja_id, categoria_id, MSG_CATEGORIA_404)
    categoria.nome = dados.nome
    ctx.db.flush()
    return _categorias(ctx, [categoria])[0]


@router.delete(
    '/categorias-material/{categoria_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir categoria (sem materiais)',
)
def remover_categoria(categoria_id: UUID, ctx: Escrita) -> None:
    categoria = buscar(ctx.db, CategoriaMaterial, ctx.loja_id, categoria_id, MSG_CATEGORIA_404)
    em_uso = ctx.db.scalar(
        select(
            exists().where(
                Material.loja_id == ctx.loja_id,
                Material.categoria_id == categoria.id,
                Material.excluido_em.is_(None),
            )
        )
    )
    if em_uso:
        raise conflito('Há materiais nesta categoria. Troque a categoria deles antes de excluir.')
    excluir(ctx.db, categoria)


# --- Materiais ---------------------------------------------------------------------------------


@router.get('/materiais', summary='Materiais e estoque')
def listar(
    ctx: Leitura,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria_id: UUID | None = None,
    ativo: bool | None = None,
    repor: Annotated[bool | None, Query(description='Só os abaixo do estoque mínimo')] = None,
) -> list[MaterialSaida]:
    consulta = select(Material).where(Material.loja_id == ctx.loja_id)
    if busca and busca.strip():
        consulta = consulta.where(Material.nome.icontains(busca.strip(), autoescape=True))
    if categoria_id is not None:
        consulta = consulta.where(Material.categoria_id == categoria_id)
    if ativo is not None:
        consulta = consulta.where(Material.ativo == ativo)
    if repor is not None:
        abaixo = Material.quantidade_atual < Material.estoque_minimo
        consulta = consulta.where(abaixo if repor else ~abaixo)
    return _materiais(ctx, list(ctx.db.scalars(consulta.order_by(func.lower(Material.nome), Material.id))))


@router.get('/materiais/{material_id}', summary='Um material')
def obter(material_id: UUID, ctx: Leitura) -> MaterialSaida:
    return _materiais(ctx, [buscar(ctx.db, Material, ctx.loja_id, material_id, MSG_404)])[0]


@router.post('/materiais', status_code=status.HTTP_201_CREATED, summary='Cadastrar material')
def criar(dados: MaterialNovo, ctx: Escrita) -> MaterialSaida:
    _validar_categoria(ctx, dados.categoria_id)
    material = Material(loja_id=ctx.loja_id, **dados.model_dump(exclude={'quantidade_inicial'}))
    ctx.db.add(material)
    ctx.db.flush()
    if dados.quantidade_inicial > 0:
        lancar(
            ctx.db,
            ctx.loja_id,
            material.id,
            TipoMovimentacao.entrada,
            dados.quantidade_inicial,
            'Estoque inicial',
        )
    return _materiais(ctx, [material])[0]


@router.put('/materiais/{material_id}', summary='Editar material (o estoque muda por movimentação)')
def editar(material_id: UUID, dados: MaterialEdicao, ctx: Escrita) -> MaterialSaida:
    material = buscar(ctx.db, Material, ctx.loja_id, material_id, MSG_404)
    _validar_categoria(ctx, dados.categoria_id)
    for campo, valor in dados.model_dump().items():
        setattr(material, campo, valor)
    ctx.db.flush()
    return _materiais(ctx, [material])[0]


@router.delete(
    '/materiais/{material_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Excluir material (não pode estar em uso por um serviço)',
)
def remover(material_id: UUID, ctx: Escrita) -> None:
    material = buscar(ctx.db, Material, ctx.loja_id, material_id, MSG_404)
    em_uso = ctx.db.scalar(
        select(func.count())
        .select_from(ServicoMaterial)
        .join(
            Servico, (Servico.id == ServicoMaterial.servico_id) & (Servico.loja_id == ServicoMaterial.loja_id)
        )
        .where(
            ServicoMaterial.loja_id == ctx.loja_id,
            ServicoMaterial.material_id == material.id,
            ServicoMaterial.excluido_em.is_(None),
            Servico.excluido_em.is_(None),
        )
    )
    if em_uso:
        raise conflito('Este material é usado em serviços. Retire-o dos serviços ou inative-o.')
    excluir(ctx.db, material)


# --- Movimentações -----------------------------------------------------------------------------


def _movimentacoes(ctx: ContextoLoja, linhas: list[MovimentacaoEstoque]) -> list[MovimentacaoSaida]:
    nomes = nomes_funcionarios(ctx.db, ctx.loja_id, (m.funcionario_id for m in linhas))
    saida = []
    for m in linhas:
        item = MovimentacaoSaida.model_validate(m)
        item.funcionario_nome = nomes.get(m.funcionario_id) if m.funcionario_id else None
        saida.append(item)
    return com_autor(ctx.db, ctx.loja_id, saida)


@router.get('/materiais/{material_id}/movimentacoes', summary='Histórico do estoque do material (paginado)')
def listar_movimentacoes(
    material_id: UUID, ctx: Leitura, pag: Annotated[Paginacao, Depends(paginacao)]
) -> Pagina[MovimentacaoSaida]:
    material = buscar(ctx.db, Material, ctx.loja_id, material_id, MSG_404)
    consulta = (
        select(MovimentacaoEstoque)
        .where(MovimentacaoEstoque.loja_id == ctx.loja_id, MovimentacaoEstoque.material_id == material.id)
        .order_by(MovimentacaoEstoque.criado_em.desc(), MovimentacaoEstoque.id)
    )
    itens, total = paginar(ctx.db, consulta, pag)
    return Pagina(itens=_movimentacoes(ctx, itens), total=total, pagina=pag.pagina, por_pagina=pag.por_pagina)


@router.post(
    '/materiais/{material_id}/movimentacoes',
    status_code=status.HTTP_201_CREATED,
    summary='Lançar entrada, ajuste ou perda',
)
def lancar_movimentacao(material_id: UUID, dados: MovimentacaoEntrada, ctx: Escrita) -> MovimentacaoSaida:
    material = buscar(ctx.db, Material, ctx.loja_id, material_id, MSG_404)
    movimentacao = lancar(
        ctx.db, ctx.loja_id, material.id, TipoMovimentacao(dados.tipo), dados.quantidade, dados.motivo
    )
    return _movimentacoes(ctx, [movimentacao])[0]
