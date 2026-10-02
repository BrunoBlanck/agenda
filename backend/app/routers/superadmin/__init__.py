"""Rotas da Plataforma (/api/superadmin/...). Só aceitam token de superadmin."""

from fastapi import APIRouter

from app.routers.superadmin import auditoria, auth, lojas, planos, usuarios, visao_geral

router = APIRouter(prefix='/api/superadmin')
router.include_router(auth.router)
router.include_router(visao_geral.router)
router.include_router(lojas.router)
router.include_router(planos.router)
router.include_router(usuarios.router)
router.include_router(auditoria.router)
