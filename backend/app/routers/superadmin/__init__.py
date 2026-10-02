"""Rotas da Plataforma (/api/superadmin/...). Só aceitam token de superadmin."""

from fastapi import APIRouter

from app.routers.superadmin import auth

router = APIRouter(prefix='/api/superadmin')
router.include_router(auth.router)
