"""Login do superadmin e dados do usuário logado (/api/superadmin)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.auth.dependencias import ContextoSuperadminDep, DbDep, ip_da_requisicao, nao_autenticado
from app.auth.senhas import verificar_senha
from app.auth.tokens import criar_token
from app.db import definir_contexto
from app.limites import BloqueioLogin, limite_login
from app.models import SuperadminUsuario
from app.schemas.auth import LoginSuperadmin, SuperadminEu, Token
from app.schemas.comum import Erro
from app.schemas.superadmin import ZONA_PLATAFORMA

router = APIRouter(tags=['Superadmin: acesso'])


@router.post(
    '/auth/login',
    responses={401: {'model': Erro}, 429: {'model': Erro}},
    dependencies=[Depends(limite_login)],
    summary='Login do superadmin',
)
def login(dados: LoginSuperadmin, request: Request, db: DbDep) -> Token:
    bloqueio = BloqueioLogin(request, 'superadmin', dados.email)
    bloqueio.conferir()
    ip = ip_da_requisicao(request)
    definir_contexto(db, origem='superadmin', ip=ip)
    superadmin = db.scalar(
        select(SuperadminUsuario).where(func.lower(SuperadminUsuario.email) == dados.email.lower())
    )
    valida, novo_hash = verificar_senha(dados.senha, superadmin.senha_hash if superadmin else None)
    if superadmin is None or not valida or not superadmin.ativo:
        if not valida:
            bloqueio.falhou()
        raise nao_autenticado('E-mail ou senha inválidos.')
    bloqueio.acertou()

    # login=True: registrar o acesso (e o novo hash da mesma senha) não é uma alteração do cadastro
    definir_contexto(db, origem='superadmin', superadmin_id=superadmin.id, ip=ip, login=True)
    superadmin.ultimo_login_em = func.now()
    if novo_hash:
        superadmin.senha_hash = novo_hash
    token, expira_em = criar_token(superadmin.id, 'superadmin')
    return Token(token=token, expira_em=expira_em.astimezone(ZONA_PLATAFORMA))


@router.get('/eu', responses={401: {'model': Erro}}, summary='Superadmin logado')
def eu(ctx: ContextoSuperadminDep) -> SuperadminEu:
    return SuperadminEu.model_validate(ctx.superadmin)
