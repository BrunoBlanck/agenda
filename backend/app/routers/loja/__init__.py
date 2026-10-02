"""Rotas do Painel da Loja (/api/loja/...). Todas usam o loja_id do token."""

from fastapi import APIRouter

from app.routers.loja import (
    agendamentos,
    auth,
    clientes,
    funcionarios,
    locais,
    materiais,
    perfis,
    servicos,
)

router = APIRouter(prefix='/api/loja')
router.include_router(auth.router)
router.include_router(clientes.router)
router.include_router(funcionarios.router)
router.include_router(perfis.router)
router.include_router(locais.router)
router.include_router(materiais.router)
router.include_router(servicos.router)
router.include_router(agendamentos.router)
