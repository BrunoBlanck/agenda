"""Login do funcionário e dados do usuário logado (/api/loja)."""

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.auth.dependencias import (
    ContextoLojaDep,
    DbDep,
    ip_da_requisicao,
    nao_autenticado,
    verificar_status_loja,
)
from app.auth.senhas import verificar_senha
from app.auth.tokens import criar_token
from app.db import definir_contexto
from app.models import Cargo, Funcionario, Loja, LojaConfiguracao
from app.schemas.auth import CargoResumo, Eu, FuncionarioEu, LoginLoja, LojaEu, PerfilEu, Token
from app.schemas.comum import Erro

router = APIRouter(tags=['Loja: acesso'])

MSG_LOGIN_INVALIDO = 'Loja, e-mail ou senha inválidos.'


@router.post(
    '/auth/login',
    responses={401: {'model': Erro}, 403: {'model': Erro}},
    summary='Login do funcionário (loja pelo slug + e-mail + senha)',
)
def login(dados: LoginLoja, request: Request, db: DbDep) -> Token:
    ip = ip_da_requisicao(request)
    definir_contexto(db, origem='painel', ip=ip)
    loja = db.scalar(select(Loja).where(Loja.slug == dados.slug.strip().lower()))
    funcionario = None
    if loja is not None:
        # RLS: só enxerga os funcionários desta loja
        definir_contexto(db, origem='painel', loja_id=loja.id, ip=ip)
        funcionario = db.scalar(
            select(Funcionario).where(
                Funcionario.loja_id == loja.id,
                func.lower(Funcionario.email) == dados.email.lower(),
            )
        )
    valida, novo_hash = verificar_senha(dados.senha, funcionario.senha_hash if funcionario else None)
    if loja is None or funcionario is None or not valida:
        raise nao_autenticado(MSG_LOGIN_INVALIDO)
    # Daqui em diante a senha confere: pode dizer o motivo da recusa
    if not funcionario.ativo:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, 'Seu acesso está desativado. Fale com o administrador da loja.'
        )
    verificar_status_loja(loja)

    definir_contexto(db, origem='painel', funcionario_id=funcionario.id, loja_id=loja.id, ip=ip)
    funcionario.ultimo_login_em = func.now()
    if novo_hash:
        funcionario.senha_hash = novo_hash
    token, expira_em = criar_token(funcionario.id, 'funcionario', loja.id)
    return Token(token=token, expira_em=expira_em)


@router.get('/eu', responses={401: {'model': Erro}, 403: {'model': Erro}}, summary='Funcionário logado')
def eu(ctx: ContextoLojaDep) -> Eu:
    db = ctx.db
    configuracao = db.scalar(select(LojaConfiguracao).where(LojaConfiguracao.loja_id == ctx.loja_id))
    cargo = None
    if ctx.funcionario.cargo_id:
        cargo = db.scalar(
            select(Cargo).where(Cargo.id == ctx.funcionario.cargo_id, Cargo.loja_id == ctx.loja_id)
        )

    loja = LojaEu.model_validate(ctx.loja)
    if configuracao:
        loja.rotulo_local = configuracao.rotulo_local
        loja.rotulo_local_plural = configuracao.rotulo_local_plural
    funcionario = FuncionarioEu.model_validate(ctx.funcionario)
    funcionario.cargo = CargoResumo.model_validate(cargo) if cargo else None
    return Eu(
        funcionario=funcionario,
        perfil=PerfilEu.model_validate(ctx.perfil),
        loja=loja,
        modulos=ctx.acesso.modulos,
        acessos=ctx.acesso.niveis,
    )
