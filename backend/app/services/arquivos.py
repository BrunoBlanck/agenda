"""Arquivos enviados pelo painel: por enquanto só a logo da loja (SEG-13).

- Ficam no disco, em ``ARQUIVOS_DIR/logos/<loja_id>/<nome>``. O banco guarda só a URL pública
  (``/api/arquivos/logos/<loja_id>/<nome>``), servida por app/routers/arquivos.py.
- O tipo é conferido pelos primeiros bytes (assinatura do arquivo), nunca pela extensão nem pelo
  content-type enviados. Só PNG, JPEG e WebP; SVG (pode levar script) e o resto são recusados.
- O nome é gerado pelo servidor (aleatório): nada do que o cliente envia entra no caminho.
- Trocar ou remover não deixa a loja sem arquivo: o novo é gravado antes; o anterior só é apagado
  depois do commit (e o novo, se a transação for desfeita).
"""

import logging
import os
import re
import secrets
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Loja
from app.services.comum import invalido, nao_encontrado

log = logging.getLogger('app.arquivos')

PREFIXO_URL_LOGOS = '/api/arquivos/logos'
NOME_LOGO = re.compile(r'[0-9a-f]{32}\.(png|jpg|webp)')
TIPOS_IMAGEM = {'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp'}

MSG_FORMATO = 'Formato não aceito. Envie uma imagem PNG, JPEG ou WebP.'
MSG_FALHA_GRAVAR = 'Não foi possível salvar a imagem. Tente novamente em instantes.'


def extensao_da_imagem(inicio: bytes) -> str | None:
    """Extensão pela assinatura do arquivo (PNG, JPEG ou WebP); None para qualquer outro formato."""
    if inicio.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if inicio.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if len(inicio) >= 12 and inicio[:4] == b'RIFF' and inicio[8:12] == b'WEBP':
        return 'webp'
    return None


def _tamanho_legivel(tamanho: int) -> str:
    return f'{tamanho / (1024 * 1024):g} MB'.replace('.', ',')


def pasta_logos(loja_id: UUID) -> Path:
    return get_settings().arquivos_dir / 'logos' / str(loja_id)


def caminho_logo(loja_id: UUID, nome: str) -> Path | None:
    """Arquivo da logo, ou None se ``nome`` não for um nome que o servidor gera (sem path traversal)."""
    if not NOME_LOGO.fullmatch(nome):
        return None
    return pasta_logos(loja_id) / nome


def _arquivo_da_url(loja_id: UUID, url: str | None) -> Path | None:
    """Arquivo local de uma logo desta loja. Qualquer outra URL: None (nada é apagado)."""
    prefixo = f'{PREFIXO_URL_LOGOS}/{loja_id}/'
    if not url or not url.startswith(prefixo):
        return None
    return caminho_logo(loja_id, url.removeprefix(prefixo))


def _apagar(caminho: Path) -> None:
    try:
        caminho.unlink(missing_ok=True)
    except OSError as erro:
        log.warning('Arquivo não apagado: %s (%s)', caminho.name, type(erro).__name__)


def _depois_da_transacao(db: Session, *, se_confirmar: Path | None, se_desfizer: Path | None) -> None:
    """Apaga ``se_confirmar`` depois do commit, ou ``se_desfizer`` se a transação for desfeita."""

    def confirmada(_sessao: Session) -> None:
        if event.contains(db, 'after_rollback', desfeita):
            event.remove(db, 'after_rollback', desfeita)
        if se_confirmar is not None:
            _apagar(se_confirmar)

    def desfeita(_sessao: Session) -> None:
        if event.contains(db, 'after_commit', confirmada):
            event.remove(db, 'after_commit', confirmada)
        if se_desfizer is not None:
            _apagar(se_desfizer)

    event.listen(db, 'after_commit', confirmada)
    event.listen(db, 'after_rollback', desfeita)


def _travar_loja(db: Session, loja_id: UUID) -> Loja:
    """A loja com a linha travada: duas trocas ao mesmo tempo não deixam arquivo órfão."""
    loja = db.scalar(
        select(Loja).where(Loja.id == loja_id).with_for_update().execution_options(populate_existing=True)
    )
    if loja is None:
        raise nao_encontrado('Loja não encontrada.')
    return loja


def ler_imagem(arquivo: BinaryIO) -> tuple[bytes, str]:
    """Conteúdo e extensão da imagem enviada (413 se passar do tamanho, 422 se não for PNG/JPEG/WebP)."""
    maximo = get_settings().logo_tamanho_maximo
    conteudo = arquivo.read(maximo + 1)
    if len(conteudo) > maximo:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f'A imagem deve ter no máximo {_tamanho_legivel(maximo)}.'
        )
    extensao = extensao_da_imagem(conteudo[:12])
    if extensao is None:
        raise invalido(MSG_FORMATO)
    return conteudo, extensao


def trocar_logo(db: Session, loja_id: UUID, arquivo: BinaryIO) -> Loja:
    """Grava a imagem como logo da loja e agenda a remoção da anterior para depois do commit."""
    conteudo, extensao = ler_imagem(arquivo)
    loja = _travar_loja(db, loja_id)
    nome = f'{secrets.token_hex(16)}.{extensao}'
    pasta = pasta_logos(loja_id)
    novo = pasta / nome
    parcial = pasta / f'{nome}.parcial'
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        parcial.write_bytes(conteudo)
        os.replace(parcial, novo)
    except OSError as erro:
        _apagar(parcial)
        log.error('Falha ao gravar a logo (%s)', type(erro).__name__)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, MSG_FALHA_GRAVAR) from None
    anterior = _arquivo_da_url(loja_id, loja.logo_url)
    loja.logo_url = f'{PREFIXO_URL_LOGOS}/{loja_id}/{nome}'
    _depois_da_transacao(db, se_confirmar=anterior, se_desfizer=novo)
    db.flush()
    return loja


def remover_logo(db: Session, loja_id: UUID) -> Loja:
    """Tira a logo da loja; o arquivo é apagado depois do commit."""
    loja = _travar_loja(db, loja_id)
    anterior = _arquivo_da_url(loja_id, loja.logo_url)
    if loja.logo_url is not None:
        loja.logo_url = None
        db.flush()
    _depois_da_transacao(db, se_confirmar=anterior, se_desfizer=None)
    return loja
