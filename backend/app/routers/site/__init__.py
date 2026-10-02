"""Rotas públicas do site do consumidor (/api/site/{slug}/...). Criadas na etapa 3."""

from fastapi import APIRouter

router = APIRouter(prefix='/api/site/{slug}', tags=['Site do consumidor'])
