"""Rotas do Painel da Loja (/api/loja/...). Todas usam o loja_id do token."""

from fastapi import APIRouter

from app.routers.loja import auth, clientes, funcionarios, perfis

router = APIRouter(prefix='/api/loja')
router.include_router(auth.router)
router.include_router(clientes.router)
router.include_router(funcionarios.router)
router.include_router(perfis.router)
