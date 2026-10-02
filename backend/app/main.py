"""Aplicação FastAPI: routers, CORS e tratamento de erros."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.auth.dependencias import DbDep
from app.config import get_settings
from app.erros import registrar_tratadores
from app.routers import loja, site, superadmin


def criar_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title='Agenda: API',
        version='0.1.0',
        description='API do sistema de agendamento multi-loja (painel da loja, SUPERADMIN e site).',
        docs_url=None if settings.ambiente == 'producao' else '/docs',
        redoc_url=None,
        openapi_url=None if settings.ambiente == 'producao' else '/openapi.json',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origens,
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['Authorization', 'Content-Type'],
    )
    registrar_tratadores(app)

    @app.get('/api/saude', tags=['Saúde'], summary='A API e o banco estão no ar?')
    def saude(db: DbDep) -> dict[str, str]:
        db.execute(text('SELECT 1'))
        return {'status': 'ok'}

    app.include_router(loja.router)
    app.include_router(superadmin.router)
    app.include_router(site.router)
    return app


app = criar_app()
