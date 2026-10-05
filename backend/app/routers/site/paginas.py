"""Site do consumidor em HTML (SIT-03, SIT-09, SIT-12): o fluxo de agendamento em ``/<slug>``.

Passos (cada um é uma página; tudo funciona sem JavaScript, ``/static/site/site.js`` só melhora):

1. ``GET /<slug>``: serviços (sem o módulo Serviços, já mostra o passo 2 do "Atendimento", SIT-08);
2. ``GET /<slug>/agendar?servico=&profissional=&dia=``: faixa de 31 dias e horários livres;
3. ``GET /<slug>/agendar/dados?servico=&profissional=&inicio=&local=``: resumo e formulário;
   ``POST /<slug>/agendar``: envia o pedido e redireciona (303) ao passo 4;
4. ``GET /<slug>/agendar/pronto?c=<código assinado>``: confirmação.

As regras são as da API pública (``app/services/agendamento_site.py``). Parâmetros da URL são lidos à
mão (nunca 422 em JSON nem 500): o que não vale volta ao passo anterior válido com um aviso curto
(``aviso=<código>``, texto fixo, nada do usuário é refletido) ou responde 404 quando não há para onde
voltar. Loja inexistente, excluída, suspensa ou cancelada: 404 em todas as páginas (SIT-01).
DIR-003: nenhuma página leva ao painel da loja.

Cores escolhidas pela loja (SIT-13 a SIT-15): um ``<style>`` com as variáveis CSS, reescritas a partir
do hex validado (``app/services/cores_site.py``), liberado na CSP só pelo nonce daquela resposta. Sem
cores escolhidas, a página e a CSP são as de sempre (só ``/static/site/site.css``).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.dependencias import DbDep, ip_da_requisicao
from app.erros import MSG_TENTE_DE_NOVO, mensagem_de_validacao
from app.limites import MSG_MUITAS_REQUISICOES, limite_site, limite_site_pedido
from app.models import Servico
from app.models.enums import StatusAgendamento
from app.routers.html import (
    CSP_SITE,
    MSG_LOJA_404,
    RespostaPronta,
    csp_site,
    muitas_requisicoes,
    nao_encontrada,
    novo_nonce,
    pagina,
    redirecionar,
    url_estatica,
)
from app.schemas.comum import ANO_MAX, ANO_MIN
from app.schemas.site import LojaPublica, SolicitacaoEntrada
from app.services.agendamento_site import (
    ContextoSite,
    HorarioEscolhido,
    HorarioIndisponivel,
    abrir_site,
    codigo_do_pedido,
    dias_livres,
    duracao_de,
    horario_oferecido,
    ler_codigo,
    nome_de,
    pedido_repetido,
    resumo_do_pedido,
    servico_escolhido,
    servicos_publicos,
    solicitar,
)
from app.services.comum import hoje, no_fuso
from app.services.cores_site import CLASSE_CORES, css_da_loja
from app.services.horarios_livres import DIAS_MAXIMOS, Livre, profissionais
from app.services.site import configuracao_publica, dados_publicos
from app.services.slugs import endereco_de_loja

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)
METODOS = ['GET', 'HEAD']

TIPOS = {'clinica': 'Clínica', 'barbearia': 'Barbearia', 'escola': 'Escola'}
# Provisório (especificação site-agendamento, seção 8)
FRASES = {
    'clinica': 'Agende sua consulta online, em poucos passos.',
    'barbearia': 'Marque seu horário online, em poucos passos.',
    'escola': 'Agende sua aula online, em poucos passos.',
}
PASSOS = ('Serviço', 'Horário', 'Seus dados', 'Pronto')
SERVICO, HORARIO, DADOS, PRONTO = range(4)

AVISOS = {
    'ocupado': 'Esse horário acabou de ser ocupado. Escolha outro.',
    'servico': 'Esse serviço não está mais disponível. Escolha outro.',
    'horario': 'Escolha um dos horários livres.',
}
MSG_PROFISSIONAL = 'Esse profissional não atende este serviço. Veja os horários de qualquer profissional.'
MSG_ORIGEM = 'Não foi possível enviar o pedido'
DICA_ORIGEM = 'Abra a página de agendamento da loja e tente de novo.'

CAMPO_ARMADILHA = 'zx_conferencia'  # escondido (display: none): só robô preenche (SIT-10)
CAMPOS_DO_CLIENTE = {
    'nome': 'Nome',
    'sobrenome': 'Sobrenome',
    'telefone': 'WhatsApp',
    'email': 'E-mail',
    'observacoes': 'Observações',
}

SEMANA_CURTA = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')
SEMANA = ('segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo')
MESES = (
    *('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho'),
    *('julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'),
)


# --- Formatos ------------------------------------------------------------------------------------


def dia_por_extenso(dia: date) -> str:
    """Ex.: "Segunda-feira, 7 de janeiro"."""
    return f'{SEMANA[dia.weekday()].capitalize()}, {dia.day} de {MESES[dia.month - 1]}'


def moeda(valor: Decimal) -> str:
    """Ex.: "R$ 1.234,50"."""
    texto = f'{valor:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'R$ {texto}'


def _endereco(loja: LojaPublica) -> str:
    """Endereço numa linha, só com as partes preenchidas."""
    rua = ', '.join(p for p in (loja.logradouro, loja.numero) if p)
    if rua and loja.complemento:
        rua = f'{rua} - {loja.complemento}'
    cidade = '/'.join(p for p in (loja.cidade, loja.uf) if p)
    return ' · '.join(p for p in (rua, loja.bairro, cidade) if p)


def _url(caminho: str, **parametros: object) -> str:
    preenchidos = {k: str(v) for k, v in parametros.items() if v is not None and v != ''}
    return f'{caminho}?{urlencode(preenchidos)}' if preenchidos else caminho


# --- Leitura dos parâmetros (nunca levanta erro) ---------------------------------------------------

_DATA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_MOMENTO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?$')
_UUID = re.compile(r'^[0-9a-fA-F]{8}-?(?:[0-9a-fA-F]{4}-?){3}[0-9a-fA-F]{12}$')


def ler_uuid(texto: str | None) -> UUID | None:
    return UUID(texto) if texto and _UUID.fullmatch(texto) else None


def ler_data(texto: str | None) -> date | None:
    if not texto or not _DATA.fullmatch(texto):
        return None
    try:
        dia = date.fromisoformat(texto)
    except ValueError:
        return None
    return dia if ANO_MIN <= dia.year <= ANO_MAX else None


def ler_momento(texto: str | None) -> datetime | None:
    if not texto or not _MOMENTO.fullmatch(texto):
        return None
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return momento if ANO_MIN <= momento.year <= ANO_MAX else None


# --- Contexto da página --------------------------------------------------------------------------


@dataclass
class Pagina:
    """O site aberto: regras (``ctx``), dados públicos da loja (cabeçalho) e o CSS das cores da loja."""

    ctx: ContextoSite
    loja: LojaPublica
    estilo: str | None = None

    @property
    def slug(self) -> str:
        return self.loja.slug

    @property
    def inicio(self) -> str:
        return f'/{self.slug}'

    @property
    def agendar(self) -> str:
        return f'/{self.slug}/agendar'

    def url_horarios(self, servico_id: UUID | None, **parametros: object) -> str:
        return _url(self.agendar, servico=servico_id, **parametros)

    def renderizar(
        self,
        modelo: str,
        passo: int,
        codigo: int = status.HTTP_200_OK,
        *,
        indexar: bool = False,
        extras: dict[str, str] | None = None,
        **contexto: object,
    ) -> HTMLResponse:
        telefone = re.sub(r'\D', '', self.loja.telefone or '')
        passos = PASSOS if self.ctx.usa_servicos else PASSOS[1:]
        nonce = novo_nonce() if self.estilo else None
        return pagina(
            modelo,
            codigo,
            csp=csp_site(nonce) if nonce else CSP_SITE,
            extras=extras,
            estilo=self.estilo,
            nonce=nonce,
            classe_cores=CLASSE_CORES,
            loja=self.loja,
            tipo=TIPOS.get(self.loja.tipo, ''),
            frase=FRASES.get(self.loja.tipo, FRASES['clinica']),
            endereco=_endereco(self.loja),
            telefone_link=f'tel:{telefone}' if telefone else None,
            passos=passos,
            passo_atual=passo - (len(PASSOS) - len(passos)),
            indexar=indexar,
            css=url_estatica('site.css'),
            js=url_estatica('site.js'),
            inicio=self.inicio,
            **contexto,
        )


def _limitar(limite: Callable[[Request], None], request: Request) -> HTTPException | None:
    """Conta a requisição no limite; devolve o 429 (sem levantar) se passou."""
    try:
        limite(request)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        return exc
    return None


def abrir(request: Request, db: DbDep, slug: str) -> Pagina:
    """Loja visível do endereço, com o limite de requisições do site (SIT-01, SIT-10)."""
    if not endereco_de_loja(slug):  # sem consulta ao banco (nem contagem do limite)
        raise RespostaPronta(nao_encontrada(MSG_LOJA_404))
    excesso = _limitar(limite_site, request)  # mesmo limite por IP da API do site
    if excesso is not None:
        raise RespostaPronta(muitas_requisicoes(excesso))
    ctx = abrir_site(db, slug, ip_da_requisicao(request))
    if ctx is None:
        raise RespostaPronta(nao_encontrada(MSG_LOJA_404))
    configuracao = configuracao_publica(db, ctx.loja)
    estilo = (
        css_da_loja(ctx.loja.tipo, configuracao.cor_site_topo, configuracao.cor_site_destaque)
        if configuracao
        else None
    )
    return Pagina(ctx=ctx, loja=dados_publicos(db, ctx.loja, ctx.modulos, configuracao), estilo=estilo)


def _ir(url: str) -> RespostaPronta:
    return RespostaPronta(redirecionar(url))


def _servico_da_url(site: Pagina, texto: str | None) -> Servico | None:
    """Serviço da URL; sem ele (ou inválido) volta ao passo 1. Sem o módulo Serviços: None."""
    if not site.ctx.usa_servicos:
        return None
    servico_id = ler_uuid(texto)
    if servico_id is None:
        raise _ir(_url(site.inicio, aviso='servico' if texto else None))
    try:
        return servico_escolhido(site.ctx, servico_id)
    except HTTPException:
        raise _ir(_url(site.inicio, aviso='servico')) from None


# --- Passo 1: serviço ----------------------------------------------------------------------------


@router.api_route('/{slug:segmento}', methods=METODOS)
def passo_servico(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    indexar = not request.query_params
    if not site.ctx.usa_servicos:  # SIT-08: direto aos horários do "Atendimento"
        return _pagina_horarios(site, request, indexar=indexar)
    servicos = [
        {
            'nome': s.nome,
            'descricao': s.descricao,
            'duracao': s.duracao_minutos,
            'preco': moeda(s.preco) if s.preco is not None else None,
            'url': site.url_horarios(s.id),
        }
        for s in servicos_publicos(site.ctx)
    ]
    return site.renderizar(
        'site/servicos.html',
        SERVICO,
        indexar=indexar,
        servicos=servicos,
        aviso=AVISOS.get(request.query_params.get('aviso', '')),
    )


# --- Passo 2: dia e horário ----------------------------------------------------------------------


@router.api_route('/{slug:segmento}/agendar', methods=METODOS)
def passo_horario(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    return _pagina_horarios(abrir(request, db, slug), request)


def _pagina_horarios(site: Pagina, request: Request, *, indexar: bool = False) -> HTMLResponse:
    ctx, parametros = site.ctx, request.query_params
    servico = _servico_da_url(site, parametros.get('servico'))
    servico_id = servico.id if servico else None
    aviso = AVISOS.get(parametros.get('aviso', ''))

    texto_profissional = parametros.get('profissional') or ''
    profissional_id = ler_uuid(texto_profissional)
    primeiro = hoje(ctx.zona)
    ultimo = primeiro + timedelta(days=DIAS_MAXIMOS - 1)
    dias = None
    if profissional_id is not None:
        try:
            dias, _ = dias_livres(ctx, servico, profissional_id, primeiro, ultimo)
        except HTTPException:  # profissional que não faz o serviço (ou de outra loja)
            dias = None
    if dias is None:
        if texto_profissional:  # inválido: mostra os horários de qualquer profissional
            profissional_id, aviso = None, MSG_PROFISSIONAL
        dias, _ = dias_livres(ctx, servico, None, primeiro, ultimo)

    pedido = ler_data(parametros.get('dia'))
    escolhido = pedido if pedido is not None and primeiro <= pedido <= ultimo else None
    if escolhido is None:
        escolhido = next((dia for dia, livres in dias if livres), None)
    livres_do_dia = next((livres for dia, livres in dias if dia == escolhido), [])

    def url_do_dia(dia: date) -> str:
        return site.url_horarios(servico_id, profissional=profissional_id, dia=dia.isoformat()) + '#horarios'

    faixa = [
        {
            'semana': 'Hoje' if dia == primeiro else SEMANA_CURTA[dia.weekday()],
            'data': f'{dia.day:02d}/{dia.month:02d}',
            'extenso': dia_por_extenso(dia),
            'total': len(livres),
            'url': url_do_dia(dia),
            'atual': dia == escolhido,
        }
        for dia, livres in dias
    ]
    return site.renderizar(
        'site/horarios.html',
        HORARIO,
        indexar=indexar,
        aviso=aviso,
        servico_nome=nome_de(servico),
        duracao=duracao_de(servico),
        voltar=site.inicio if ctx.usa_servicos else None,
        acao=site.agendar,
        servico_id=servico_id,
        equipe=[
            {'id': f.id, 'nome': f.nome, 'escolhido': f.id == profissional_id}
            for f in profissionais(ctx.db, ctx.loja.id, servico)
        ],
        dias=faixa,
        dia_escolhido=escolhido.isoformat() if escolhido else None,
        dia_extenso=dia_por_extenso(escolhido) if escolhido else None,
        nenhum_horario=not any(livres for _, livres in dias),
        horarios=[
            _horario(site, servico_id, livre, mostrar_quem=profissional_id is None) for livre in livres_do_dia
        ],
    )


def _horario(site: Pagina, servico_id: UUID | None, livre: Livre, *, mostrar_quem: bool) -> dict[str, object]:
    inicio = livre.inicio.astimezone(site.ctx.zona)
    return {
        'hora': inicio.strftime('%H:%M'),
        'profissional': livre.funcionario.nome if mostrar_quem else None,
        'url': _url(
            f'{site.agendar}/dados',
            servico=servico_id,
            profissional=livre.funcionario.id,
            inicio=inicio.isoformat(timespec='minutes'),
            local=livre.local_id,
        ),
    }


# --- Passo 3: seus dados -------------------------------------------------------------------------


@dataclass(frozen=True)
class Escolha:
    """O que veio da URL (ou dos campos ocultos) do passo 3, já conferido."""

    servico_id: UUID | None
    profissional_id: UUID
    inicio: datetime
    local_id: UUID | None
    horario: HorarioEscolhido


def _escolha(site: Pagina, valores: dict[str, str]) -> Escolha:
    """Serviço, profissional, início e local escolhidos; o horário precisa estar livre agora.

    Serviço inválido volta ao passo 1; horário inválido ou ocupado, ao passo 2 do mesmo dia.
    """
    servico = _servico_da_url(site, valores.get('servico'))
    servico_id = servico.id if servico else None
    profissional_id = ler_uuid(valores.get('profissional'))
    momento = ler_momento(valores.get('inicio'))
    inicio = no_fuso(momento, site.ctx.zona) if momento else None
    texto_local = valores.get('local') or ''
    local_id = ler_uuid(texto_local)
    dia = inicio.astimezone(site.ctx.zona).date() if inicio else None
    if profissional_id is None or inicio is None or (texto_local and local_id is None):
        raise _ir(_passo_horario(site, servico_id, dia, 'horario'))
    try:
        horario = horario_oferecido(site.ctx, servico, profissional_id, inicio, local_id)
    except HorarioIndisponivel:
        raise _ir(_passo_horario(site, servico_id, dia, 'ocupado')) from None
    except HTTPException:  # profissional que não faz o serviço, local que não é do serviço
        raise _ir(_passo_horario(site, servico_id, dia, 'horario')) from None
    return Escolha(servico_id, profissional_id, inicio, local_id, horario)


def _passo_horario(site: Pagina, servico_id: UUID | None, dia: date | None, aviso: str) -> str:
    """Volta ao passo 2 (qualquer profissional) no dia do horário, com o aviso."""
    return site.url_horarios(servico_id, dia=dia.isoformat() if dia else None, aviso=aviso) + '#horarios'


def _pagina_dados(
    site: Pagina,
    escolha: Escolha,
    codigo: int = status.HTTP_200_OK,
    *,
    valores: dict[str, str] | None = None,
    erros: dict[str, str] | None = None,
    mensagem: str | None = None,
    extras: dict[str, str] | None = None,
) -> HTMLResponse:
    horario = escolha.horario
    inicio = horario.livre.inicio.astimezone(site.ctx.zona)
    local = horario.local
    erros = erros or {}
    return site.renderizar(
        'site/dados.html',
        DADOS,
        codigo,
        extras=extras,
        servico_nome=nome_de(horario.servico),
        duracao=duracao_de(horario.servico),
        preco=moeda(horario.servico.preco) if horario.servico and horario.servico.preco is not None else None,
        dia_extenso=dia_por_extenso(inicio.date()),
        hora=inicio.strftime('%H:%M'),
        profissional=horario.livre.funcionario.nome,
        local=local.nome if local else None,
        rotulo_local=site.loja.rotulo_local,
        trocar=site.url_horarios(escolha.servico_id, dia=inicio.date().isoformat()) + '#horarios',
        acao=site.agendar,
        ocultos={
            'servico': escolha.servico_id or '',
            'profissional': escolha.profissional_id,
            'inicio': inicio.isoformat(timespec='minutes'),
            'local': escolha.local_id or '',
        },
        armadilha=CAMPO_ARMADILHA,
        valores={campo: (valores or {}).get(campo, '') for campo in CAMPOS_DO_CLIENTE},
        erros=erros,
        resumo_erros=[
            {'campo': campo, 'rotulo': rotulo, 'mensagem': erros[campo]}
            for campo, rotulo in CAMPOS_DO_CLIENTE.items()
            if campo in erros
        ],
        mensagem=mensagem,
    )


@router.api_route('/{slug:segmento}/agendar/dados', methods=METODOS)
def passo_dados(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    return _pagina_dados(site, _escolha(site, dict(request.query_params)))


async def ler_formulario(request: Request) -> dict[str, str]:
    """Campos de texto do formulário (``application/x-www-form-urlencoded``). Mal formado = vazio."""
    try:
        formulario = await request.form(max_files=0, max_fields=50)
    except StarletteHTTPException:
        return {}
    return {chave: valor for chave, valor in formulario.items() if isinstance(valor, str)}


def _nome_do_host(valor: str) -> str | None:
    try:
        return urlsplit(valor).hostname
    except ValueError:
        return None


def mesma_origem(request: Request) -> bool:
    """Proteção simples contra envio vindo de outro site (CSRF): ``Origin`` e ``Referer``, quando
    presentes, precisam ser do próprio endereço (``Host``). Compara o nome do host, sem a porta: atrás
    do nginx o ``Host`` chega sem ela. ``Origin: null`` (página isolada ou sandbox) não passa.
    """
    proprio = _nome_do_host(f'//{request.headers.get("host", "")}')
    for cabecalho in ('origin', 'referer'):
        valor = request.headers.get(cabecalho)
        if valor is not None and (proprio is None or _nome_do_host(valor) != proprio):
            return False
    return True


def _pronto(site: Pagina, agendamento_id: UUID | None) -> RedirectResponse:
    return redirecionar(_url(f'{site.agendar}/pronto', c=codigo_do_pedido(site.ctx.loja.id, agendamento_id)))


def _erros_do_cliente(exc: ValidationError) -> dict[str, str]:
    erros: dict[str, str] = {}
    for erro in exc.errors():
        campo = str(erro['loc'][0]) if erro.get('loc') else ''
        if campo in CAMPOS_DO_CLIENTE and campo not in erros:
            erros[campo] = mensagem_de_validacao(erro)
    return erros


@router.post('/{slug:segmento}/agendar', response_model=None)
def enviar_pedido(
    slug: str,
    request: Request,
    db: DbDep,
    formulario: Annotated[dict[str, str], Depends(ler_formulario)],
) -> Response:
    if endereco_de_loja(slug) and not mesma_origem(request):
        return pagina('erro.html', status.HTTP_403_FORBIDDEN, titulo=MSG_ORIGEM, dica=DICA_ORIGEM)
    site = abrir(request, db, slug)
    excesso = _limitar(limite_site_pedido, request)  # pedidos por IP nesta loja, antes de tudo
    if excesso is not None:
        return _pagina_dados(
            site,
            _escolha(site, formulario),
            status.HTTP_429_TOO_MANY_REQUESTS,
            valores=formulario,
            mensagem=MSG_MUITAS_REQUISICOES,
            extras=excesso.headers,
        )
    if formulario.get(CAMPO_ARMADILHA, '').strip():
        return _pronto(site, None)  # robô: parece que deu certo, nada é gravado

    dados, erros = _validar(site, formulario)
    if dados is not None:
        repetido = pedido_repetido(site.ctx, dados)
        if repetido is not None:  # o mesmo formulário de novo: a confirmação do pedido já gravado
            return _pronto(site, repetido)
    try:
        escolha = _escolha(site, formulario)
    except RespostaPronta:
        # O horário pode ter sido ocupado agora pelo mesmo formulário, enviado junto (LOG-07)
        repetido = pedido_repetido(site.ctx, dados) if dados is not None else None
        if repetido is not None:
            return _pronto(site, repetido)
        raise
    if dados is None:
        return _pagina_dados(site, escolha, valores=formulario, erros=erros)
    dados = dados.model_copy(update={'servico_id': escolha.servico_id})

    try:
        with db.begin_nested():  # a falha do banco desfaz só o pedido; a transação segue (aviso, repetição)
            criado = solicitar(site.ctx, dados)
    except HorarioIndisponivel:
        return _ocupado(site, escolha, dados)
    except DBAPIError as exc:
        sqlstate = getattr(exc.orig, 'sqlstate', None)
        if sqlstate == '23P01':  # o banco recusou: outro pedido levou o horário agora (SIT-05)
            return _ocupado(site, escolha, dados)
        if sqlstate not in ('40P01', '40001'):
            raise
        return _pagina_dados(
            site, escolha, status.HTTP_409_CONFLICT, valores=formulario, mensagem=MSG_TENTE_DE_NOVO
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            return redirecionar(_url(site.inicio, aviso='servico'))  # serviço desativado no meio do caminho
        # Limite de pendentes por telefone. Se quem ocupou a vaga foi este mesmo pedido (dois envios
        # ao mesmo tempo), mostra a confirmação dele (LOG-07)
        repetido = pedido_repetido(site.ctx, dados)
        if repetido is not None:
            return _pronto(site, repetido)
        return _pagina_dados(site, escolha, exc.status_code, valores=formulario, mensagem=str(exc.detail))
    return _pronto(site, criado.id)


def _validar(site: Pagina, formulario: dict[str, str]) -> tuple[SolicitacaoEntrada | None, dict[str, str]]:
    """Formulário inteiro validado como ``SolicitacaoEntrada`` (mesmas mensagens da API), sem consultar
    o banco. Campos ocultos ilegíveis: (None, {}), e a escolha volta ao passo certo depois."""
    profissional_id = ler_uuid(formulario.get('profissional'))
    momento = ler_momento(formulario.get('inicio'))
    if profissional_id is None or momento is None:
        return None, {}
    campos = {campo: formulario[campo] for campo in CAMPOS_DO_CLIENTE if formulario.get(campo, '').strip()}
    try:
        dados = SolicitacaoEntrada(
            servico_id=ler_uuid(formulario.get('servico')),
            funcionario_id=profissional_id,
            inicio=no_fuso(momento, site.ctx.zona),
            local_id=ler_uuid(formulario.get('local')),
            **campos,
        )
    except ValidationError as exc:
        return None, _erros_do_cliente(exc)
    return dados, {}


def _ocupado(site: Pagina, escolha: Escolha, dados: SolicitacaoEntrada) -> RedirectResponse:
    """Horário ocupado: volta ao passo 2 do mesmo dia. Se quem ocupou foi este mesmo pedido (enviado
    duas vezes), mostra a confirmação dele (LOG-07)."""
    repetido = pedido_repetido(site.ctx, dados)
    if repetido is not None:
        return _pronto(site, repetido)
    dia = escolha.inicio.astimezone(site.ctx.zona).date()
    return redirecionar(_passo_horario(site, escolha.servico_id, dia, 'ocupado'))


# --- Passo 4: pronto -----------------------------------------------------------------------------

TEXTOS_DA_SITUACAO = {
    StatusAgendamento.pendente: 'Seu horário fica reservado até a {loja} confirmar.',
    StatusAgendamento.agendado: 'A {loja} já confirmou seu horário.',
    StatusAgendamento.confirmado: 'A {loja} já confirmou seu horário.',
    StatusAgendamento.concluido: 'Este atendimento já foi concluído.',
    StatusAgendamento.cancelado: 'Este pedido foi cancelado. Se precisar, fale com a {loja}.',
    StatusAgendamento.nao_compareceu: 'Este atendimento já passou.',
}


@router.api_route('/{slug:segmento}/agendar/pronto', methods=METODOS)
def passo_pronto(slug: str, request: Request, db: DbDep) -> HTMLResponse:
    site = abrir(request, db, slug)
    lido = ler_codigo(request.query_params.get('c', ''), site.ctx.loja.id)
    if lido is None:
        return nao_encontrada()
    if lido.falso:
        return site.renderizar('site/pronto.html', PRONTO, resumo=None, situacao=None)
    resumo = resumo_do_pedido(site.ctx, lido.agendamento_id)
    if resumo is None:
        return nao_encontrada()
    return site.renderizar(
        'site/pronto.html',
        PRONTO,
        resumo={
            'servico': resumo.servico_nome,
            'dia': dia_por_extenso(resumo.inicio.date()),
            'hora': resumo.inicio.strftime('%H:%M'),
            'profissional': resumo.funcionario_nome,
            'local': resumo.local_nome,
            'preco': moeda(resumo.preco) if resumo.preco is not None else None,
        },
        rotulo_local=site.loja.rotulo_local,
        situacao=TEXTOS_DA_SITUACAO[resumo.status].format(loja=site.loja.nome_fantasia),
    )
