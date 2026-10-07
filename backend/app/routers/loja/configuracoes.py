"""Configurações › Dados da loja (/api/loja/configuracoes/loja e /configuracoes/site). Recurso: config_loja.

Grava direto em lojas (estrutura.md, 2.18). O trigger preenche atualizado_por_funcionario.
A logo é um arquivo (app/services/arquivos.py): enviada por PUT .../logo (multipart, campo ``arquivo``).
As cores do site do consumidor (SIT-13, SIT-14) ficam em loja_configuracoes (app/services/configuracoes.py).
Avisos e e-mail (CFG-05, CFG-06): antecedência do cliente e SMTP da loja
(app/services/config_notificacoes.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.auth.catalogo import MODULOS
from app.auth.dependencias import ContextoLoja, exigir, obter_contexto_loja
from app.db import get_sessionmaker
from app.limites import limite_teste_email
from app.models import Plano
from app.schemas.comum import Erro
from app.schemas.configuracoes import CoresSite, CoresSiteEntrada, DadosLoja, DadosLojaEntrada
from app.schemas.notificacoes import (
    ConfigNotificacoes,
    ConfigNotificacoesEntrada,
    TesteEmailEntrada,
    TesteEmailSaida,
)
from app.services.arquivos import remover_logo, trocar_logo
from app.services.comum import conflito
from app.services.config_notificacoes import (
    MSG_TESTE_SEM_CONFIG,
    config_notificacoes,
    config_para_teste,
    salvar_config_notificacoes,
    servidor_conferido,
)
from app.services.configuracoes import cores_do_site, salvar_cores_do_site
from app.services.envio_email import Email, FalhaEnvio, provedor_de_email
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

router_notificacoes = APIRouter(
    prefix='/configuracoes/notificacoes',
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


# --- Avisos e e-mail (CFG-05, CFG-06) --------------------------------------------------------------


_credenciais = HTTPBearer(auto_error=False)


def servidor_antes_da_transacao(
    dados: ConfigNotificacoesEntrada,
    request: Request,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_credenciais)],
) -> bool | None:
    """Confere o servidor SMTP (DNS, em produção) **fora** da transação da requisição: declarada antes de
    ``ctx`` na rota, roda antes da sessão do banco dela. Só consulta o DNS para quem tem **escrita** em
    ``config_loja`` (conferido numa sessão curta, já fechada quando o DNS roda); para os outros devolve
    None e a rota responde 401/403 pelo caminho de sempre (``exigir``)."""
    if not dados.email.servidor:
        return None
    with get_sessionmaker()() as db, db.begin():
        try:
            exigir('config_loja', 'escrita')(obter_contexto_loja(request, db, credenciais))
        except HTTPException:
            return None
    return servidor_conferido(dados)


@router_notificacoes.get('', summary='Antecedência do cliente e e-mail (SMTP) da loja; a senha nunca volta')
def obter_config_notificacoes(ctx: Leitura) -> ConfigNotificacoes:
    return config_notificacoes(ctx.db, ctx.loja)


@router_notificacoes.put(
    '', summary='Salvar a antecedência do cliente e o SMTP (senha ausente = mantém; null = apaga)'
)
def salvar_notificacoes(
    dados: ConfigNotificacoesEntrada,
    servidor_ok: Annotated[bool | None, Depends(servidor_antes_da_transacao)],
    ctx: Escrita,
) -> ConfigNotificacoes:
    return salvar_config_notificacoes(ctx.db, ctx.loja, dados, servidor_ok)


@router_notificacoes.post(
    '/testar-email',
    response_model=TesteEmailSaida,
    response_model_exclude_none=True,
    responses={409: {'model': Erro}, 429: {'model': Erro}},
    summary='Enviar um e-mail de teste com a configuração salva (5 por loja a cada 10 min)',
)
def testar_email(dados: TesteEmailEntrada, ctx: Escrita) -> TesteEmailSaida:
    """Usa a configuração salva. O envio acontece depois de encerrar a transação da requisição (nada de
    rede com ela aberta, PER-05); a rota é síncrona, então roda numa thread (o SMTP espera até 15 s)."""
    db, loja = ctx.db, ctx.loja
    config = config_para_teste(db, loja)
    if config is None:
        raise conflito(MSG_TESTE_SEM_CONFIG)
    limite_teste_email(loja.id)
    nome = loja.nome_fantasia or loja.nome
    db.commit()  # daqui em diante nada usa o banco
    if isinstance(config, str):  # senha que não abre com a chave atual
        return TesteEmailSaida(enviado=False, erro=config)
    email = Email(
        destino=str(dados.destino),
        assunto=f'E-mail de teste · {nome}',
        corpo=f'Este é um e-mail de teste de {nome}. Se ele chegou, o envio de avisos está funcionando.\n',
    )
    try:
        provedor_de_email().enviar(config, email)
    except FalhaEnvio as falha:
        return TesteEmailSaida(enviado=False, erro=falha.mensagem)
    return TesteEmailSaida(enviado=True)
