"""Rotas do Painel da Loja (/api/loja/...). Todas usam o loja_id do token."""

from fastapi import APIRouter

from app.routers.loja import auth

router = APIRouter(prefix='/api/loja')
router.include_router(auth.router)
