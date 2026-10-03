"""Arquivos públicos (/api/arquivos/...): a logo da loja, usada no painel e no site.

Sem login. O caminho é montado só com o id da loja e um nome no formato que o servidor gera
(app/services/arquivos.py); qualquer outra coisa responde 404. Loja inexistente, excluída, suspensa
ou cancelada também responde 404, sem dizer o motivo (GER-25, como no site). O nome muda a cada
envio, então a resposta pode ficar em cache por muito tempo.
"""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.db import definir_contexto
from app.models import Loja
from app.models.enums import StatusLoja
from app.schemas.comum import Erro
from app.services.arquivos import TIPOS_IMAGEM, caminho_logo
from app.services.comum import nao_encontrado

router = APIRouter(prefix='/api/arquivos', tags=['Arquivos'])

MSG_ARQUIVO_404 = 'Arquivo não encontrado.'

CABECALHOS = {
    'Cache-Control': 'public, max-age=31536000, immutable',
    'X-Content-Type-Options': 'nosniff',
    # Mesmo que alguém abra a imagem direto no navegador, nada nela é executado
    'Content-Security-Policy': "default-src 'none'; sandbox",
}


@router.head('/logos/{loja_id}/{nome}', include_in_schema=False)
@router.get(
    '/logos/{loja_id}/{nome}',
    response_class=FileResponse,
    responses={200: {'content': {t: {} for t in TIPOS_IMAGEM.values()}}, 404: {'model': Erro}},
    summary='Logo da loja ativa (PNG, JPEG ou WebP; também responde a HEAD)',
)
def logo(loja_id: str, nome: str, request: Request, db: DbDep) -> FileResponse:
    try:
        id_loja = UUID(loja_id)
    except ValueError:
        raise nao_encontrado(MSG_ARQUIVO_404) from None
    caminho = caminho_logo(id_loja, nome)
    if caminho is None:
        raise nao_encontrado(MSG_ARQUIVO_404)
    definir_contexto(db, origem='site', ip=ip_da_requisicao(request))
    situacao = db.scalar(select(Loja.status).where(Loja.id == id_loja))  # excluída: None
    if situacao != StatusLoja.ativa or not caminho.is_file():
        raise nao_encontrado(MSG_ARQUIVO_404)
    return FileResponse(
        caminho, media_type=TIPOS_IMAGEM[caminho.suffix.removeprefix('.')], headers=CABECALHOS
    )
