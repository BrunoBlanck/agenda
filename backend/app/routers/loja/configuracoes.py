"""Configurações › Dados da loja (/api/loja/configuracoes/loja e /configuracoes/site). Recurso: config_loja.

Grava direto em lojas (estrutura.md, 2.18). O trigger preenche atualizado_por_funcionario.
A logo é um arquivo (app/services/arquivos.py): enviada por PUT .../logo (multipart, campo ``arquivo``).
As cores do site do consumidor (SIT-13, SIT-14) ficam em loja_configuracoes (app/services/configuracoes.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select

from app.auth.catalogo import MODULOS
from app.auth.dependencias import ContextoLoja, exigir
from app.models import Plano
from app.schemas.comum import Erro
from app.schemas.configuracoes import CoresSite, CoresSiteEntrada, DadosLoja, DadosLojaEntrada
from app.services.arquivos import remover_logo, trocar_logo
from app.services.configuracoes import cores_do_site, salvar_cores_do_site
from app.services.plataforma import ultima_alteracao_loja

router = APIRouter(
    prefix='/configuracoes/loja',
    tags=['Loja: configurações'],
    responses={403: {'model': Erro}, 409: {'model': Erro}},
)
router_site = APIRouter(
    prefix='/configuracoes/site',
    tags=['Loja: configurações'],
    responses={403: {'model': Erro}, 422: {'model': Erro}},
)

Leitura = Annotated[ContextoLoja, Depends(exigir('config_loja'))]
Escrita = Annotated[ContextoLoja, Depends(exigir('config_loja', 'escrita'))]


def _dados(ctx: ContextoLoja) -> DadosLoja:
    db, loja = ctx.db, ctx.loja
    plano = db.scalar(select(Plano.nome).where(Plano.id == loja.plano_id)) if loja.plano_id else None
    ultima = ultima_alteracao_loja(db, loja.id)
    return DadosLoja(
        **{campo: getattr(loja, campo) for campo in DadosLojaEntrada.model_fields},
        logo_url=loja.logo_url,
        tipo=loja.tipo,
        slug=loja.slug,
        plano_nome=plano,
        status=loja.status,
        fuso_horario=loja.fuso_horario,
        modulos={codigo: ctx.acesso.modulo_ativo(codigo) for codigo, opcional in MODULOS.items() if opcional},
        criado_em=loja.criado_em,
        atualizado_em=loja.atualizado_em,
        # Só o funcionário aparece como autor; superadmin e sistema ficam nulos (GER-13)
        atualizado_por=ultima.funcionario_id,
        atualizado_por_nome=ultima.nome if ultima.funcionario_id else None,
    )


@router.get('', summary='Dados da loja')
def obter(ctx: Leitura) -> DadosLoja:
    return _dados(ctx)


@router.put('', summary='Editar os dados da loja (nome, razão social, contato, endereço e CNPJ)')
def editar(dados: DadosLojaEntrada, ctx: Escrita) -> DadosLoja:
    for campo, valor in dados.model_dump().items():
        if getattr(ctx.loja, campo) != valor:
            setattr(ctx.loja, campo, valor)
    ctx.db.flush()
    return _dados(ctx)


@router.put(
    '/logo',
    responses={413: {'model': Erro}, 422: {'model': Erro}},
    summary='Enviar a logo (multipart, campo "arquivo": PNG, JPEG ou WebP, até 2 MB)',
)
def enviar_logo(
    arquivo: Annotated[UploadFile, File(description='PNG, JPEG ou WebP')], ctx: Escrita
) -> DadosLoja:
    trocar_logo(ctx.db, ctx.loja_id, arquivo.file)
    return _dados(ctx)


@router.delete('/logo', status_code=status.HTTP_204_NO_CONTENT, summary='Remover a logo (apaga o arquivo)')
def excluir_logo(ctx: Escrita) -> None:
    remover_logo(ctx.db, ctx.loja_id)


# --- Cores do site do consumidor -----------------------------------------------------------------


@router_site.get('', summary='Cores do site de agendamento (null = padrão do tipo da loja)')
def obter_cores_site(ctx: Leitura) -> CoresSite:
    return cores_do_site(ctx.db, ctx.loja)


@router_site.put('', summary='Escolher as cores do site de agendamento (topo e destaque; null = padrão)')
def definir_cores_site(dados: CoresSiteEntrada, ctx: Escrita) -> CoresSite:
    return salvar_cores_do_site(ctx.db, ctx.loja, dados)
