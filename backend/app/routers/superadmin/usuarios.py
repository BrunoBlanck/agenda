"""Usuários admin (/api/superadmin/usuarios): contas de quem administra a plataforma (estrutura.md, 1.1).

Regras: ninguém se exclui nem se desativa, e a plataforma nunca fica sem um superadmin ativo.
"""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.auth.dependencias import ContextoSuperadmin, ContextoSuperadminDep
from app.auth.senhas import gerar_hash, gerar_senha_provisoria
from app.models import SuperadminUsuario
from app.schemas.comum import Erro
from app.schemas.superadmin import SuperadminCriado, SuperadminEntrada, SuperadminSaida
from app.services.comum import conflito, excluir, nao_encontrado

router = APIRouter(
    prefix='/usuarios',
    tags=['Superadmin: usuários admin'],
    responses={404: {'model': Erro}, 409: {'model': Erro}},
)

MSG_404 = 'Usuário admin não encontrado.'
MSG_ULTIMO = 'A plataforma precisa de pelo menos um usuário admin ativo.'


def _saida(ctx: ContextoSuperadmin, usuario: SuperadminUsuario) -> SuperadminSaida:
    item = SuperadminSaida.model_validate(usuario)
    item.voce = usuario.id == ctx.superadmin.id
    return item


def _buscar(ctx: ContextoSuperadmin, usuario_id: UUID) -> SuperadminUsuario:
    usuario = ctx.db.scalar(select(SuperadminUsuario).where(SuperadminUsuario.id == usuario_id))
    if usuario is None:
        raise nao_encontrado(MSG_404)
    return usuario


def _outros_ativos(ctx: ContextoSuperadmin, exceto: UUID) -> int:
    """Outros superadmins ativos.

    Trava todas as contas ativas: dois admins desativando um ao outro ao mesmo tempo são serializados
    e o segundo já vê o primeiro inativo.
    """
    ids = ctx.db.scalars(
        select(SuperadminUsuario.id)
        .where(SuperadminUsuario.ativo, SuperadminUsuario.excluido_em.is_(None))
        .with_for_update()
    ).all()
    return sum(1 for i in ids if i != exceto)


@router.get('', summary='Usuários admin')
def listar(ctx: ContextoSuperadminDep) -> list[SuperadminSaida]:
    usuarios = ctx.db.scalars(select(SuperadminUsuario).order_by(func.lower(SuperadminUsuario.nome)))
    return [_saida(ctx, u) for u in usuarios]


@router.get('/{usuario_id}', summary='Dados do usuário admin')
def obter(usuario_id: UUID, ctx: ContextoSuperadminDep) -> SuperadminSaida:
    return _saida(ctx, _buscar(ctx, usuario_id))


@router.post('', status_code=status.HTTP_201_CREATED, summary='Cadastrar usuário admin')
def criar(dados: SuperadminEntrada, ctx: ContextoSuperadminDep) -> SuperadminCriado:
    senha = dados.senha or gerar_senha_provisoria()
    usuario = SuperadminUsuario(
        nome=dados.nome, email=dados.email, ativo=dados.ativo, senha_hash=gerar_hash(senha)
    )
    ctx.db.add(usuario)
    ctx.db.flush()
    return SuperadminCriado(
        **_saida(ctx, usuario).model_dump(), senha_provisoria=None if dados.senha else senha
    )


@router.put('/{usuario_id}', summary='Editar usuário admin (senha só se for trocar)')
def editar(usuario_id: UUID, dados: SuperadminEntrada, ctx: ContextoSuperadminDep) -> SuperadminSaida:
    usuario = _buscar(ctx, usuario_id)
    if usuario.ativo and not dados.ativo:
        if usuario.id == ctx.superadmin.id:
            raise conflito('Você não pode desativar o seu próprio usuário.')
        if not _outros_ativos(ctx, usuario.id):
            raise conflito(MSG_ULTIMO)
    for campo in ('nome', 'email', 'ativo'):
        valor = getattr(dados, campo)
        if getattr(usuario, campo) != valor:
            setattr(usuario, campo, valor)
    if dados.senha:
        usuario.senha_hash = gerar_hash(dados.senha)
    ctx.db.flush()
    return _saida(ctx, usuario)


@router.delete('/{usuario_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Excluir usuário admin')
def remover(usuario_id: UUID, ctx: ContextoSuperadminDep) -> None:
    usuario = _buscar(ctx, usuario_id)
    if usuario.id == ctx.superadmin.id:
        raise conflito('Você não pode excluir o seu próprio usuário.')
    if usuario.ativo and not _outros_ativos(ctx, usuario.id):
        raise conflito(MSG_ULTIMO)
    excluir(ctx.db, usuario)
