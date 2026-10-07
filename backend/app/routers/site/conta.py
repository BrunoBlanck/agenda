"""Conta do cliente no site (SIT-16 a SIT-21): entrar, sair, criar conta / esqueci a senha e Minha conta.

Páginas (todas ``noindex``, no limite por IP do site, 404 com a loja indisponível, sem JavaScript):

- ``GET/POST /<slug>/conta/entrar``: telefone + senha (SIT-19), com ``limite_login`` por IP e o bloqueio
  progressivo de ``BloqueioLogin`` (chave ``site`` + slug + telefone, por IP);
- ``POST /<slug>/conta/sair``: apaga o cookie;
- ``GET/POST /<slug>/conta/criar``: passo 1, telefone. Gera o código (SIT-17) e responde igual exista ou
  não cadastro/conta: 303 para o passo 2 com ``t`` (id do código assinado, 15 min);
- ``GET/POST /<slug>/conta/codigo?t=``: passo 2, o código de 6 dígitos;
- ``GET/POST /<slug>/conta/senha?v=``: passo 3, a senha (e nome/sobrenome se o telefone não tem cliente);
  ``v`` = telefone confirmado por aquele código, uso único;
- ``GET /<slug>/conta?pagina=``: Minha conta, próximos e histórico (SIT-21), com "Remarcar"/"Cancelar" nos
  próximos que ainda podem ser alterados (as páginas ficam em ``app/routers/site/conta_agendamentos.py``).

Todo ``POST`` confere ``mesma_origem`` (403 HTML). ``voltar`` só aceita páginas do próprio site
(``validar_voltar``). Formulário com erro: 200 com os valores (nunca a senha nem o código) e a mensagem ao
lado do campo + resumo no topo. DIR-003: nada leva ao painel; o texto usa "Entrar" e "Minha conta".
"""

import math
import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.auth.senhas import gerar_hash, verificar_senha
from app.limites import (
    MSG_MUITAS_REQUISICOES,
    BloqueioLogin,
    TentativasDoCodigo,
    limite_codigo_pedido,
    limite_codigo_telefone,
    limite_login_site,
)
from app.models import ClienteConta
from app.models.enums import StatusAgendamento
from app.routers.html import RespostaPronta, pagina, redirecionar
from app.routers.site.paginas import (
    METODOS,
    Pagina,
    abrir,
    dia_por_extenso,
    ler_formulario,
    limitar,
    mesma_origem,
    moeda,
    montar_url,
)
from app.routers.site.sessao import apagar_sessao, conta_padrao, gravar_sessao, validar_voltar
from app.schemas.comum import formatar_telefone, so_digitos
from app.services.agendamento_site import cliente_do_telefone
from app.services.conta_cliente import (
    HISTORICO_POR_PAGINA,
    PAGINA_MAXIMA,
    SENHA_MAXIMA,
    SENHA_MINIMA,
    SITUACOES_ATIVAS,
    VALIDADE_CODIGO,
    Conferencia,
    MeuAgendamento,
    SessaoCliente,
    codigo_aberto,
    codigo_confirmado,
    codigo_do_passo,
    conferir_codigo,
    confirmado,
    conta_do_telefone,
    definir_senha,
    erros_da_senha,
    ler_telefone,
    meus_agendamentos,
    obter_codigo,
    passo_da_senha,
    passo_do_codigo,
    provedor_de_codigo,
    registrar_acesso,
    travar_codigo,
)
from app.services.slugs import endereco_de_loja

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)
Formulario = Annotated[dict[str, str], Depends(ler_formulario)]

MSG_ORIGEM = 'Não foi possível enviar o formulário'
DICA_ORIGEM = 'Abra a página da loja e tente de novo.'
MSG_TELEFONE = 'Informe o telefone com DDD (ex.: (11) 99999-9999).'
MSG_SENHA_VAZIA = 'Informe a senha.'
MSG_ENTRAR = 'Telefone ou senha incorretos.'
MSG_CODIGO_FORMATO = 'Digite os 6 dígitos do código.'
MSG_CODIGO_ERRADO = 'Código incorreto ou vencido.'
MSG_CODIGO_VENCIDO = 'Este código venceu ou foi digitado errado vezes demais. Peça um novo código.'
MSG_TENTATIVAS_IP = 'Muitas tentativas. Peça um novo código mais tarde.'
MSG_MUITOS_CODIGOS = 'Muitos pedidos de código para este telefone. Aguarde um pouco e tente novamente.'
MSG_OBRIGATORIO = 'Campo obrigatório.'

# Avisos depois de redirecionar (``aviso=<código>``): texto fixo, nada do usuário é refletido
AVISOS = {
    'sessao': 'Sua sessão terminou. Entre de novo.',
    'cancelado': 'Agendamento cancelado.',
    'remarcado': 'Pedido de remarcação enviado.',
    'ocupado': 'Esse horário acabou de ser ocupado. Escolha outro.',
    'prazo': 'Este agendamento não pode mais ser alterado pelo site.',
    'horario': 'Escolha um dos horários livres.',
    'mesmo': 'Esse já é o horário do seu agendamento. Escolha outro.',
}

SITUACOES = {
    StatusAgendamento.pendente: 'Aguardando confirmação',
    StatusAgendamento.agendado: 'Agendado',
    StatusAgendamento.confirmado: 'Confirmado',
    StatusAgendamento.concluido: 'Concluído',
    StatusAgendamento.cancelado: 'Cancelado',
    StatusAgendamento.nao_compareceu: 'Não compareceu',
}

ROTULOS = {
    'telefone': 'Telefone',
    'senha': 'Senha',
    'repetir': 'Repetir senha',
    'codigo': 'Código',
    'nome': 'Nome',
    'sobrenome': 'Sobrenome',
}


# --- Ajudantes -----------------------------------------------------------------------------------


def origem_recusada(slug: str, request: Request) -> HTMLResponse | None:
    """403 HTML para envio vindo de outro site (CSRF), antes de consultar o banco."""
    if endereco_de_loja(slug) and not mesma_origem(request):
        return pagina('erro.html', status.HTTP_403_FORBIDDEN, titulo=MSG_ORIGEM, dica=DICA_ORIGEM)
    return None


def _com_voltar(site: Pagina, caminho: str, voltar: str, **parametros: object) -> str:
    """URL com ``voltar`` (omitido quando é o padrão, ``/<slug>/conta``)."""
    return montar_url(caminho, **parametros, voltar=None if voltar == conta_padrao(site.slug) else voltar)


def _formulario(
    site: Pagina,
    modelo: str,
    codigo: int = status.HTTP_200_OK,
    *,
    voltar: str,
    valores: dict[str, str] | None = None,
    erros: dict[str, str] | None = None,
    mensagem: str | None = None,
    extras: dict[str, str] | None = None,
    **contexto: object,
) -> HTMLResponse:
    erros = erros or {}
    return site.renderizar(
        modelo,
        None,
        codigo,
        extras=extras,
        voltar=voltar if voltar != conta_padrao(site.slug) else '',
        valores=valores or {},
        erros=erros,
        resumo_erros=[
            {'campo': campo, 'rotulo': ROTULOS[campo], 'mensagem': mensagem_campo}
            for campo, mensagem_campo in erros.items()
        ],
        mensagem=mensagem,
        **contexto,
    )


def _entrar_com_sessao(site: Pagina, voltar: str, conta: ClienteConta) -> Response:
    return gravar_sessao(redirecionar(voltar), site.slug, conta)


def exigir_sessao(site: Pagina) -> SessaoCliente:
    """Sessão válida, ou 303 para ``/conta/entrar?voltar=<esta página>`` (e o cookie velho é apagado)."""
    if site.sessao is not None:
        return site.sessao
    destino = montar_url(
        f'/{site.slug}/conta/entrar',
        voltar=validar_voltar(site.slug, site.caminho),
        aviso='sessao' if site.sessao_expirada else None,
    )
    resposta = redirecionar(destino)
    if site.sessao_expirada:
        apagar_sessao(resposta, site.slug)
    raise RespostaPronta(resposta)


# --- Entrar e sair -------------------------------------------------------------------------------


def _pagina_entrar(
    site: Pagina, voltar: str, codigo: int = status.HTTP_200_OK, **contexto: object
) -> HTMLResponse:
    return _formulario(
        site,
        'site/conta_entrar.html',
        codigo,
        voltar=voltar,
        acao=f'/{site.slug}/conta/entrar',
        criar=_com_voltar(site, f'/{site.slug}/conta/criar', voltar),
        **contexto,
    )


@router.api_route('/{slug:segmento}/conta/entrar', methods=METODOS)
def entrar(slug: str, request: Request, db: DbDep) -> Response:
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, request.query_params.get('voltar'))
    if site.sessao is not None:
        return redirecionar(conta_padrao(site.slug))
    resposta = _pagina_entrar(site, voltar, aviso=AVISOS.get(request.query_params.get('aviso', '')))
    if site.sessao_expirada:
        apagar_sessao(resposta, site.slug)
    return resposta


@router.post('/{slug:segmento}/conta/entrar', response_model=None)
def enviar_entrar(slug: str, request: Request, db: DbDep, formulario: Formulario) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, formulario.get('voltar'))
    valores = {'telefone': formulario.get('telefone', '')[:30]}
    excesso = limitar(limite_login_site, request)  # tentativas por IP (contador próprio do site)
    if excesso is not None:
        return _pagina_entrar(
            site,
            voltar,
            status.HTTP_429_TOO_MANY_REQUESTS,
            valores=valores,
            mensagem=MSG_MUITAS_REQUISICOES,
            extras=excesso.headers,
        )
    digitos = ler_telefone(formulario.get('telefone'))
    senha = formulario.get('senha', '')
    erros: dict[str, str] = {}
    if digitos is None:
        erros['telefone'] = MSG_TELEFONE
    if not senha:
        erros['senha'] = MSG_SENHA_VAZIA
    if erros or digitos is None:
        return _pagina_entrar(site, voltar, valores=valores, erros=erros)

    bloqueio = BloqueioLogin(request, 'site', site.slug, digitos)
    try:
        bloqueio.conferir()
    except HTTPException as exc:
        segundos = int((exc.headers or {}).get('Retry-After', '60'))
        return _pagina_entrar(
            site,
            voltar,
            status.HTTP_429_TOO_MANY_REQUESTS,
            valores=valores,
            mensagem=f'Muitas tentativas. Aguarde {math.ceil(segundos / 60)} minuto(s) e tente novamente.',
            extras=exc.headers,
        )
    conta = conta_do_telefone(db, site.ctx.loja.id, digitos)
    valida, novo_hash = (
        verificar_senha(senha, conta.senha_hash if conta else None)
        if len(senha) <= SENHA_MAXIMA
        else (False, None)
    )
    if conta is None or not valida:
        bloqueio.falhou()
        return _pagina_entrar(site, voltar, valores=valores, mensagem=MSG_ENTRAR)
    bloqueio.acertou()
    registrar_acesso(db, site.ctx.loja.id, conta, novo_hash, ip_da_requisicao(request))
    return _entrar_com_sessao(site, voltar, conta)


@router.post('/{slug:segmento}/conta/sair', response_model=None)
def sair(slug: str, request: Request, db: DbDep) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    return apagar_sessao(redirecionar(site.inicio), site.slug)


# --- Criar conta / esqueci a senha: passo 1, telefone ------------------------------------------------


def _pagina_criar(
    site: Pagina, voltar: str, codigo: int = status.HTTP_200_OK, **contexto: object
) -> HTMLResponse:
    return _formulario(
        site,
        'site/conta_criar.html',
        codigo,
        voltar=voltar,
        acao=f'/{site.slug}/conta/criar',
        entrar=_com_voltar(site, f'/{site.slug}/conta/entrar', voltar),
        **contexto,
    )


@router.api_route('/{slug:segmento}/conta/criar', methods=METODOS)
def criar(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    return _pagina_criar(site, validar_voltar(site.slug, request.query_params.get('voltar')))


@router.post('/{slug:segmento}/conta/criar', response_model=None)
def enviar_criar(slug: str, request: Request, db: DbDep, formulario: Formulario) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, formulario.get('voltar'))
    valores = {'telefone': formulario.get('telefone', '')[:30]}
    digitos = ler_telefone(formulario.get('telefone'))
    if digitos is None:
        return _pagina_criar(site, voltar, valores=valores, erros={'telefone': MSG_TELEFONE})
    try:
        limite_codigo_pedido(request, site.slug, digitos)
        # Com um código pendente, o mesmo (SIT-17); o limite por telefone conta só os gerados de fato
        codigo = obter_codigo(
            db, site.ctx.loja.id, digitos, lambda: limite_codigo_telefone(site.slug, digitos)
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        return _pagina_criar(
            site,
            voltar,
            status.HTTP_429_TOO_MANY_REQUESTS,
            valores=valores,
            mensagem=MSG_MUITOS_CODIGOS,
            extras=exc.headers,
        )
    t = passo_do_codigo(site.ctx.loja.id, codigo.id)
    return redirecionar(_com_voltar(site, f'/{site.slug}/conta/codigo', voltar, t=t))


# --- Passo 2: código -----------------------------------------------------------------------------


def _pagina_codigo(
    site: Pagina,
    voltar: str,
    t: str,
    telefone_digitos: str,
    codigo_http: int = status.HTTP_200_OK,
    *,
    vencido: bool = False,
    **contexto: object,
) -> HTMLResponse:
    return _formulario(
        site,
        'site/conta_codigo.html',
        codigo_http,
        voltar=voltar,
        acao=f'/{site.slug}/conta/codigo',
        t=t,
        vencido=vencido,
        telefone=formatar_telefone(telefone_digitos),
        instrucao=provedor_de_codigo().instrucao(site.loja.nome_fantasia),
        novo_codigo=_com_voltar(site, f'/{site.slug}/conta/criar', voltar),
        **contexto,
    )


def _voltar_ao_inicio(site: Pagina, voltar: str) -> RespostaPronta:
    """Passo sem ``t``/``v`` válido (adulterado, vencido, de outra loja, já usado): volta ao passo 1."""
    return RespostaPronta(redirecionar(_com_voltar(site, f'/{site.slug}/conta/criar', voltar)))


@router.api_route('/{slug:segmento}/conta/codigo', methods=METODOS)
def passo_codigo(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, request.query_params.get('voltar'))
    t = request.query_params.get('t', '')
    codigo = codigo_do_passo(db, site.ctx.loja.id, t)
    if codigo is None:
        raise _voltar_ao_inicio(site, voltar)
    vencido = not codigo_aberto(codigo)
    return _pagina_codigo(
        site,
        voltar,
        t,
        codigo.telefone_digitos,
        vencido=vencido,
        mensagem=MSG_CODIGO_VENCIDO if vencido else None,
    )


@router.post('/{slug:segmento}/conta/codigo', response_model=None)
def enviar_codigo(slug: str, request: Request, db: DbDep, formulario: Formulario) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, formulario.get('voltar'))
    t = formulario.get('t', '')
    codigo = codigo_do_passo(db, site.ctx.loja.id, t)
    if codigo is None:
        raise _voltar_ao_inicio(site, voltar)
    texto = formulario.get('codigo', '')
    digitado = so_digitos(texto)  # só dígitos ASCII
    telefone = codigo.telefone_digitos
    if len(digitado) != 6 or len(texto) > 20:  # fora do formato: não conta tentativa
        if not codigo_aberto(codigo):
            return _pagina_codigo(site, voltar, t, telefone, vencido=True, mensagem=MSG_CODIGO_VENCIDO)
        return _pagina_codigo(site, voltar, t, telefone, erros={'codigo': MSG_CODIGO_FORMATO})
    codigo = travar_codigo(db, codigo)  # telefone primeiro, depois o código (a mesma ordem de todos)
    tentativas = TentativasDoCodigo(request, codigo.id, int(VALIDADE_CODIGO.total_seconds()))
    if codigo_aberto(codigo) and tentativas.esgotadas():
        return _tentativas_esgotadas(site, voltar, t, telefone)
    resultado = conferir_codigo(db, codigo, digitado)
    if resultado == Conferencia.certo:
        v = passo_da_senha(site.ctx.loja.id, codigo.id)
        return redirecionar(_com_voltar(site, f'/{site.slug}/conta/senha', voltar, v=v))
    if resultado == Conferencia.vencido:
        return _pagina_codigo(site, voltar, t, telefone, vencido=True, mensagem=MSG_CODIGO_VENCIDO)
    if tentativas.errou():  # o 5o erro deste IP: só este IP para de tentar este código
        return _tentativas_esgotadas(site, voltar, t, telefone)
    return _pagina_codigo(site, voltar, t, telefone, erros={'codigo': MSG_CODIGO_ERRADO})


def _tentativas_esgotadas(site: Pagina, voltar: str, t: str, telefone: str) -> HTMLResponse:
    """Este IP errou o código vezes demais; para os outros, o código continua valendo (SIT-17)."""
    return _pagina_codigo(
        site, voltar, t, telefone, status.HTTP_429_TOO_MANY_REQUESTS, vencido=True, mensagem=MSG_TENTATIVAS_IP
    )


# --- Passo 3: senha ------------------------------------------------------------------------------


def _pagina_senha(
    site: Pagina,
    voltar: str,
    v: str,
    telefone_digitos: str,
    codigo: int = status.HTTP_200_OK,
    **contexto: object,
) -> HTMLResponse:
    loja_id = site.ctx.loja.id
    tem_conta = conta_do_telefone(site.ctx.db, loja_id, telefone_digitos) is not None
    return _formulario(
        site,
        'site/conta_senha.html',
        codigo,
        voltar=voltar,
        acao=f'/{site.slug}/conta/senha',
        v=v,
        telefone=formatar_telefone(telefone_digitos),
        tem_conta=tem_conta,
        titulo_pagina='Nova senha' if tem_conta else 'Crie sua senha',
        pede_nome=cliente_do_telefone(site.ctx.db, loja_id, telefone_digitos) is None,
        senha_minima=SENHA_MINIMA,
        senha_maxima=SENHA_MAXIMA,
        **contexto,
    )


@router.api_route('/{slug:segmento}/conta/senha', methods=METODOS)
def passo_senha(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    voltar = validar_voltar(site.slug, request.query_params.get('voltar'))
    v = request.query_params.get('v', '')
    codigo = codigo_confirmado(db, site.ctx.loja.id, v)
    if codigo is None:
        raise _voltar_ao_inicio(site, voltar)
    return _pagina_senha(site, voltar, v, codigo.telefone_digitos)


def _texto(formulario: dict[str, str], campo: str, maximo: int, erros: dict[str, str]) -> str:
    valor = formulario.get(campo, '').strip()
    if not valor:
        erros[campo] = MSG_OBRIGATORIO
    elif len(valor) > maximo:
        erros[campo] = f'Texto muito longo (máximo de {maximo} caracteres).'
    return valor


@router.post('/{slug:segmento}/conta/senha', response_model=None)
def enviar_senha(slug: str, request: Request, db: DbDep, formulario: Formulario) -> Response:
    if (recusa := origem_recusada(slug, request)) is not None:
        return recusa
    site = abrir(request, db, slug)
    loja_id = site.ctx.loja.id
    voltar = validar_voltar(site.slug, formulario.get('voltar'))
    v = formulario.get('v', '')
    codigo = codigo_confirmado(db, loja_id, v)  # sem trava: o telefone é travado antes do código
    if codigo is None:
        raise _voltar_ao_inicio(site, voltar)
    digitos = codigo.telefone_digitos
    erros = erros_da_senha(formulario.get('senha', ''), formulario.get('repetir', ''), digitos)
    nome, sobrenome = _nome_se_preciso(db, loja_id, digitos, formulario, erros)
    if erros:
        return _senha_com_erros(site, voltar, v, digitos, formulario, erros)
    senha_hash = gerar_hash(formulario['senha'])  # o Argon2 é lento: antes de qualquer trava
    codigo = travar_codigo(db, codigo)
    if not confirmado(codigo):  # outro envio já usou o passo, ou um código novo o derrubou
        raise _voltar_ao_inicio(site, voltar)
    nome, sobrenome = _nome_se_preciso(db, loja_id, digitos, formulario, erros)  # pode ter mudado
    if erros:
        return _senha_com_erros(site, voltar, v, digitos, formulario, erros)
    conta = definir_senha(db, loja_id, codigo, senha_hash, nome, sobrenome)
    return _entrar_com_sessao(site, voltar, conta)


def _nome_se_preciso(
    db: Session, loja_id: UUID, digitos: str, formulario: dict[str, str], erros: dict[str, str]
) -> tuple[str | None, str | None]:
    """Nome e sobrenome do formulário, só se nenhum cliente da loja tiver o telefone (SIT-18)."""
    if cliente_do_telefone(db, loja_id, digitos) is not None:
        return None, None
    return _texto(formulario, 'nome', 60, erros), _texto(formulario, 'sobrenome', 100, erros)


def _senha_com_erros(
    site: Pagina, voltar: str, v: str, digitos: str, formulario: dict[str, str], erros: dict[str, str]
) -> HTMLResponse:
    valores = {campo: formulario.get(campo, '')[:100] for campo in ('nome', 'sobrenome')}
    return _pagina_senha(site, voltar, v, digitos, valores=valores, erros=erros)


# --- Minha conta ---------------------------------------------------------------------------------


def _ler_pagina(texto: str | None) -> int:
    """Página do histórico: só dígitos ASCII (``isdigit`` aceitaria "²" e dígitos árabes), senão 1."""
    if not texto or re.fullmatch(r'[0-9]{1,6}', texto) is None:
        return 1
    return int(texto) if 1 <= int(texto) <= PAGINA_MAXIMA else 1


def item_da_conta(site: Pagina, item: MeuAgendamento, *, futuro: bool = True) -> dict[str, object]:
    """Um agendamento como as páginas da conta mostram. Nos próximos, os links de remarcar e cancelar
    (SIT-23/24) quando ainda dá, ou o aviso de falar com a loja quando passou do prazo."""
    inicio: datetime = item.inicio.astimezone(site.ctx.zona)
    base = f'/{site.slug}/conta/agendamentos/{item.id}'
    alteravel = futuro and item.alteravel
    return {
        'id': item.id,
        'servico': item.servico_nome,
        'dia': dia_por_extenso(inicio.date()) if futuro else inicio.strftime('%d/%m/%Y'),
        'hora': inicio.strftime('%H:%M'),
        'profissional': item.funcionario_nome,
        'local': item.local_nome,
        'preco': moeda(item.preco) if item.preco is not None else None,
        'situacao': SITUACOES[item.status],
        'classe': item.status.value,
        'remarcar': f'{base}/remarcar' if alteravel else None,
        'cancelar': f'{base}/cancelar' if alteravel else None,
        'so_com_a_loja': futuro and not item.alteravel and item.status in SITUACOES_ATIVAS,
    }


@router.api_route('/{slug:segmento}/conta', methods=METODOS)
def minha_conta(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    sessao = exigir_sessao(site)
    pagina_atual = _ler_pagina(request.query_params.get('pagina'))
    dados = meus_agendamentos(
        db, site.ctx.loja.id, sessao.conta.telefone_digitos, pagina_atual, site.ctx.antecedencia
    )
    paginas = max(1, math.ceil(dados.total_historico / HISTORICO_POR_PAGINA))
    base = f'/{site.slug}/conta'
    return site.renderizar(
        'site/conta.html',
        None,
        nome=sessao.nome,
        telefone=sessao.telefone,
        aviso=AVISOS.get(request.query_params.get('aviso', '')),
        proximos=[item_da_conta(site, item) for item in dados.proximos],
        historico=[item_da_conta(site, item, futuro=False) for item in dados.historico],
        total_historico=dados.total_historico,
        pagina=pagina_atual,
        paginas=paginas,
        anterior=montar_url(base, pagina=pagina_atual - 1) + '#historico' if pagina_atual > 1 else None,
        proxima=montar_url(base, pagina=pagina_atual + 1) + '#historico' if pagina_atual < paginas else None,
        rotulo_local=site.loja.rotulo_local,
        sair=f'{base}/sair',
        agendar=site.inicio,
    )
