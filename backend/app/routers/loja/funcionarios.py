"""Funcionários e cargos (/api/loja/funcionarios, /api/loja/cargos). Recurso: funcionarios.

Regras (estrutura.md, 2.2 e 2.4; ACE-19 e ACE-20):
- só um Administrador atribui o perfil Administrador ou altera outro Administrador;
- ninguém atribui um perfil com nível acima do seu, troca o próprio perfil ou troca a senha de quem
  tem nível acima do seu;
- a loja não fica sem nenhum Administrador ativo (com trava contra alterações simultâneas);
- funcionário não é excluído: é inativado (o histórico continua).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import exists, func, select

from app.auth.dependencias import ContextoLoja, exigir
from app.auth.senhas import gerar_hash
from app.models import Cargo, Funcionario, Perfil
from app.schemas.comum import Erro
from app.schemas.funcionarios import CargoEntrada, CargoSaida, FuncionarioEntrada, FuncionarioSaida
from app.services.acesso import acima_do_teto, niveis_do_perfil
from app.services.comum import buscar, com_autor, conflito, excluir, invalido, proibido
from app.services.funcionarios import MSG_ULTIMO_ADMIN, deixa_loja_sem_admin

ERROS = {403: {'model': Erro}, 404: {'model': Erro}, 409: {'model': Erro}}
router = APIRouter(tags=['Loja: funcionários'], responses=ERROS)

MSG_404 = 'Funcionário não encontrado.'
MSG_CARGO_404 = 'Cargo não encontrado.'

Leitura = Annotated[ContextoLoja, Depends(exigir('funcionarios'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('funcionarios', 'escrita'))]


def _saida(ctx: ContextoLoja, funcionarios: list[Funcionario]) -> list[FuncionarioSaida]:
    db = ctx.db
    perfis = {
        p.id: p
        for p in db.scalars(
            select(Perfil)
            .where(Perfil.loja_id == ctx.loja_id, Perfil.id.in_({f.perfil_id for f in funcionarios}))
            .execution_options(incluir_excluidos=True)
        )
    }
    ids_cargos = {f.cargo_id for f in funcionarios if f.cargo_id}
    cargos = dict(
        db.execute(
            select(Cargo.id, Cargo.nome)
            .where(Cargo.loja_id == ctx.loja_id, Cargo.id.in_(ids_cargos))
            .execution_options(incluir_excluidos=True)
        ).all()
    )
    saida = []
    for f in funcionarios:
        item = FuncionarioSaida.model_validate(f)
        perfil = perfis.get(f.perfil_id)
        item.perfil_nome = perfil.nome if perfil else None
        item.perfil_acesso_total = bool(perfil and perfil.acesso_total)
        item.cargo_nome = cargos.get(f.cargo_id) if f.cargo_id else None
        saida.append(item)
    return com_autor(db, ctx.loja_id, saida)


def _sem_escalada(
    ctx: ContextoLoja,
    dados: FuncionarioEntrada,
    perfil: Perfil,
    atual: Funcionario | None,
    perfil_atual: Perfil | None,
) -> None:
    """ACE-19 para quem não é Administrador: nada de conceder (ou tomar) acesso acima do próprio."""
    if ctx.perfil.acesso_total:
        return
    teto = niveis_do_perfil(ctx.db, ctx.loja_id, ctx.perfil)
    troca_perfil = atual is None or perfil.id != atual.perfil_id
    if troca_perfil and acima_do_teto(niveis_do_perfil(ctx.db, ctx.loja_id, perfil), teto):
        raise proibido('Você não pode atribuir um perfil com acesso maior que o seu.')
    colega = atual is not None and atual.id != ctx.funcionario.id
    if (
        colega
        and dados.senha
        and perfil_atual is not None
        and acima_do_teto(niveis_do_perfil(ctx.db, ctx.loja_id, perfil_atual), teto)
    ):
        raise proibido('Você não pode trocar a senha de quem tem acesso maior que o seu.')


def _validar(ctx: ContextoLoja, dados: FuncionarioEntrada, atual: Funcionario | None) -> None:
    perfil = ctx.db.scalar(select(Perfil).where(Perfil.id == dados.perfil_id, Perfil.loja_id == ctx.loja_id))
    if perfil is None:
        raise invalido('Perfil não encontrado.')
    if dados.cargo_id is not None:
        cargo = ctx.db.scalar(select(Cargo).where(Cargo.id == dados.cargo_id, Cargo.loja_id == ctx.loja_id))
        if cargo is None:
            raise invalido(MSG_CARGO_404)
    sou_admin = ctx.perfil.acesso_total
    era_admin = False
    perfil_atual = None
    if atual is not None:
        if atual.id == ctx.funcionario.id and perfil.id != atual.perfil_id:
            raise proibido('Você não pode trocar o seu próprio perfil de acesso.')
        perfil_atual = ctx.db.scalar(
            select(Perfil).where(Perfil.id == atual.perfil_id, Perfil.loja_id == ctx.loja_id)
        )
        era_admin = bool(perfil_atual and perfil_atual.acesso_total)
        if era_admin and not sou_admin:
            raise proibido('Só um Administrador pode alterar outro Administrador.')
    if perfil.acesso_total and not sou_admin:
        raise proibido('Só um Administrador pode atribuir o perfil Administrador.')
    _sem_escalada(ctx, dados, perfil, atual, perfil_atual)
    continua_admin = perfil.acesso_total and dados.ativo
    if atual is not None and deixa_loja_sem_admin(ctx.db, ctx.loja_id, atual, era_admin, continua_admin):
        raise conflito(MSG_ULTIMO_ADMIN)


# --- Funcionários ------------------------------------------------------------------------------


@router.get('/funcionarios', summary='Lista de funcionários')
def listar(ctx: Leitura, ativo: bool | None = None) -> list[FuncionarioSaida]:
    consulta = select(Funcionario).where(Funcionario.loja_id == ctx.loja_id)
    if ativo is not None:
        consulta = consulta.where(Funcionario.ativo == ativo)
    return _saida(ctx, list(ctx.db.scalars(consulta.order_by(Funcionario.nome, Funcionario.id))))


@router.get('/funcionarios/{funcionario_id}', summary='Dados do funcionário')
def obter(funcionario_id: UUID, ctx: Leitura) -> FuncionarioSaida:
    return _saida(ctx, [buscar(ctx.db, Funcionario, ctx.loja_id, funcionario_id, MSG_404)])[0]


@router.post('/funcionarios', status_code=status.HTTP_201_CREATED, summary='Cadastrar funcionário')
def criar(dados: FuncionarioEntrada, ctx: Escrita) -> FuncionarioSaida:
    if not dados.senha:
        raise invalido('Informe uma senha inicial (mínimo de 8 caracteres).')
    _validar(ctx, dados, None)
    valores = dados.model_dump(exclude={'senha'})
    funcionario = Funcionario(loja_id=ctx.loja_id, senha_hash=gerar_hash(dados.senha), **valores)
    ctx.db.add(funcionario)
    ctx.db.flush()
    return _saida(ctx, [funcionario])[0]


@router.put('/funcionarios/{funcionario_id}', summary='Editar funcionário (inclui inativar e trocar perfil)')
def editar(funcionario_id: UUID, dados: FuncionarioEntrada, ctx: Escrita) -> FuncionarioSaida:
    funcionario = buscar(ctx.db, Funcionario, ctx.loja_id, funcionario_id, MSG_404)
    _validar(ctx, dados, funcionario)
    for campo, valor in dados.model_dump(exclude={'senha'}).items():
        setattr(funcionario, campo, valor)
    if dados.senha:
        funcionario.senha_hash = gerar_hash(dados.senha)
    ctx.db.flush()
    return _saida(ctx, [funcionario])[0]


# --- Cargos ------------------------------------------------------------------------------------


def _cargos(ctx: ContextoLoja, cargos: list[Cargo]) -> list[CargoSaida]:
    return com_autor(ctx.db, ctx.loja_id, [CargoSaida.model_validate(c) for c in cargos])


@router.get('/cargos', summary='Cargos da loja')
def listar_cargos(ctx: Leitura) -> list[CargoSaida]:
    consulta = select(Cargo).where(Cargo.loja_id == ctx.loja_id).order_by(func.lower(Cargo.nome))
    return _cargos(ctx, list(ctx.db.scalars(consulta)))


@router.post('/cargos', status_code=status.HTTP_201_CREATED, summary='Cadastrar cargo')
def criar_cargo(dados: CargoEntrada, ctx: Escrita) -> CargoSaida:
    cargo = Cargo(loja_id=ctx.loja_id, **dados.model_dump())
    ctx.db.add(cargo)
    ctx.db.flush()
    return _cargos(ctx, [cargo])[0]


@router.put('/cargos/{cargo_id}', summary='Editar cargo')
def editar_cargo(cargo_id: UUID, dados: CargoEntrada, ctx: Escrita) -> CargoSaida:
    cargo = buscar(ctx.db, Cargo, ctx.loja_id, cargo_id, MSG_CARGO_404)
    for campo, valor in dados.model_dump().items():
        setattr(cargo, campo, valor)
    ctx.db.flush()
    return _cargos(ctx, [cargo])[0]


@router.delete(
    '/cargos/{cargo_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Excluir cargo (sem funcionários)'
)
def remover_cargo(cargo_id: UUID, ctx: Escrita) -> None:
    cargo = buscar(ctx.db, Cargo, ctx.loja_id, cargo_id, MSG_CARGO_404)
    em_uso = ctx.db.scalar(
        select(
            exists().where(
                Funcionario.loja_id == ctx.loja_id,
                Funcionario.cargo_id == cargo.id,
                Funcionario.excluido_em.is_(None),
            )
        )
    )
    if em_uso:
        raise conflito('Há funcionários com este cargo. Troque o cargo deles antes de excluir, ou inative-o.')
    excluir(ctx.db, cargo)
