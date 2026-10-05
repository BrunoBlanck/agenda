"""Site do consumidor em HTML (SIT-01 a SIT-12, DIR-003): o fluxo de agendamento em /{slug}.

Usa a loja de tests/clinica.py (Limpeza: 60 min, R$ 200, Admin e Profissional, locais Sala 1 e Online;
Avaliação: 30 min, só Admin). O fixture ``site`` acrescenta jornada em todos os dias da semana, para
a faixa de 31 dias a partir de hoje ter horários. Os pedidos diretos (sem passar pelas páginas) usam a
segunda-feira fixa de 2030 (``SEGUNDA``), que tem jornada no cenário.
"""

import html
import re
import threading
from datetime import UTC, datetime, time, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.models import PerfilHorario
from app.models.enums import StatusLoja
from app.routers.html import CSP_SITE
from app.services.agendamento_site import codigo_do_pedido
from tests.clinica import SEGUNDA
from tests.fabricas import criar_loja, inserir, mudar_modulo

FUSO = ZoneInfo('America/Sao_Paulo')
LOJA = '/loja-a'
MSG_OCUPADO = 'Esse horário acabou de ser ocupado. Escolha outro.'
MSG_PENDENTES = (
    'Já há pedidos deste telefone aguardando a confirmação da loja. '
    'Aguarde a resposta antes de pedir outro horário.'
)
CLIENTE = {'nome': 'Ana', 'sobrenome': 'Souza', 'telefone': '(11) 97777-6666', 'email': 'ana@example.com'}


# --- Ajudantes ------------------------------------------------------------------------------------


def hrefs(texto: str) -> list[str]:
    return [html.unescape(h) for h in re.findall(r'href="([^"]*)"', texto)]


def link(texto: str, prefixo: str) -> str:
    return next(h for h in hrefs(texto) if h.startswith(prefixo))


def ocultos(texto: str) -> dict[str, str]:
    return {
        nome: html.unescape(valor)
        for nome, valor in re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', texto)
    }


def parametros(url: str) -> dict[str, str]:
    return {chave: valores[0] for chave, valores in parse_qs(urlsplit(url).query).items()}


def pagina_html(resposta, codigo: int = 200) -> str:
    assert resposta.status_code == codigo, resposta.text[:500]
    assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
    return resposta.text


def eh_do_site(resposta) -> None:
    assert resposta.headers['content-security-policy'] == CSP_SITE
    assert resposta.headers['cache-control'] == 'no-store'
    assert resposta.headers['x-content-type-options'] == 'nosniff'
    assert resposta.headers['x-frame-options'] == 'DENY'


def contar(engine, sql: str, **params) -> int:
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).scalar_one()


def alterar_loja(engine, slug: str, **campos) -> None:
    atribuicoes = ', '.join(f'{campo} = :{campo}' for campo in campos)
    with engine.begin() as conexao:
        conexao.execute(text(f'UPDATE lojas SET {atribuicoes} WHERE slug = :slug'), {'slug': slug, **campos})


def formulario_direto(clinica, hora: str = '08:00', **extra) -> dict[str, str]:
    """Campos do passo 3 para um horário da segunda de 2030 (Profissional, Limpeza)."""
    return {
        'servico': clinica.limpeza,
        'profissional': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T{hora}-03:00',
        'local': '',
        **CLIENTE,
        **extra,
    }


def enviar(cliente, dados: dict[str, str], slug: str = 'loja-a', **kwargs):
    return cliente.post(f'/{slug}/agendar', data=dados, follow_redirects=False, **kwargs)


@pytest.fixture
def site(clinica, engine_dono):
    """A clínica com jornada em todos os dias (08–12 e 13–18), para a faixa de 31 dias a partir de hoje."""
    lt = clinica.lt
    inserir(
        engine_dono,
        *[
            PerfilHorario(
                loja_id=lt.loja.id, perfil_id=perfil.id, dia_semana=dia, hora_inicio=ini, hora_fim=fim
            )
            for perfil in lt.perfis.values()
            for dia in (0, 2, 3, 4, 5, 6)
            for ini, fim in ((time(8), time(12)), (time(13), time(18)))
        ],
    )
    return clinica


def passo_horarios(cliente, clinica, **params) -> str:
    return pagina_html(cliente.get(f'{LOJA}/agendar', params={'servico': clinica.limpeza, **params}))


def primeiro_horario(texto: str) -> str:
    return link(texto, f'{LOJA}/agendar/dados?')


# --- Fluxo completo sem JavaScript ----------------------------------------------------------------


def test_fluxo_completo_sem_js(cliente, site, engine_dono):
    inicio = cliente.get(LOJA)
    passo1 = pagina_html(inicio)
    eh_do_site(inicio)
    assert 'noindex' not in passo1  # a página inicial da loja pode ser indexada
    assert '<li aria-current="step"><span class="passo-num" aria-hidden="true">1</span>' in passo1
    assert 'Limpeza' in passo1
    assert 'R$ 200,00' in passo1
    assert '60 min' in passo1

    passo2 = pagina_html(cliente.get(link(passo1, f'{LOJA}/agendar?servico={site.limpeza}')))
    assert '<meta name="robots" content="noindex">' in passo2
    assert 'Limpeza · 60 min' in passo2
    assert len(re.findall(r'class="dia[" ]', passo2)) == 31
    assert passo2.count('aria-current="date"') == 1
    assert '<option value="">Qualquer profissional</option>' in passo2

    horario = primeiro_horario(passo2)
    escolha = parametros(horario)
    assert set(escolha) == {'servico', 'profissional', 'inicio', 'local'}
    passo3 = pagina_html(cliente.get(horario))
    assert '<form class="formulario" method="post" action="/loja-a/agendar" data-enviar>' in passo3
    assert 'A Loja loja-a vai confirmar seu horário pelo WhatsApp.' in passo3
    assert 'Trocar horário' in passo3
    campos = ocultos(passo3)
    assert campos == escolha

    resposta = enviar(cliente, {**campos, **CLIENTE, 'observacoes': 'Primeira vez'})
    assert resposta.status_code == 303
    pronto_url = resposta.headers['location']
    assert pronto_url.startswith(f'{LOJA}/agendar/pronto?c=')

    pronto = pagina_html(cliente.get(pronto_url))
    assert 'Pedido enviado!' in pronto
    assert 'Limpeza' in pronto
    assert 'R$ 200,00' in pronto
    assert 'Seu horário fica reservado até a Loja loja-a confirmar.' in pronto
    assert link(pronto, '/loja-a') == '/loja-a'  # "Fazer outro agendamento"
    for pessoal in ('97777', 'ana@example.com', 'Souza'):
        assert pessoal not in pronto

    agendamento = (
        engine_dono.connect()
        .execute(
            text(
                'SELECT a.id, a.status::text AS status, a.origem::text AS origem, a.observacoes, a.preco,'
                ' a.funcionario_id::text AS funcionario_id, a.inicio'
                ' FROM agendamentos a'
            )
        )
        .mappings()
        .one()
    )
    assert (agendamento['status'], agendamento['origem']) == ('pendente', 'site')
    assert agendamento['observacoes'] == 'Primeira vez'
    assert agendamento['funcionario_id'] == escolha['profissional']
    assert agendamento['inicio'] == datetime.fromisoformat(escolha['inicio'])
    auditoria = engine_dono.connect().execute(
        text("SELECT tabela, operacao::text FROM auditoria WHERE origem = 'site' ORDER BY id")
    )
    assert {tuple(linha) for linha in auditoria} == {
        ('clientes', 'inserir'),
        ('agendamentos', 'inserir'),
        ('agendamento_materiais', 'inserir'),
    }


def test_o_pedido_aparece_no_painel_e_a_loja_aceita(cliente, clinica):
    resposta = enviar(cliente, formulario_direto(clinica, '14:00'))
    assert resposta.status_code == 303
    h = clinica.lt.h_recepcao
    lista = cliente.get('/api/loja/agendamentos', params={'status': 'pendente'}, headers=h).json()
    assert [(a['origem'], a['cliente_nome']) for a in lista['itens']] == [('site', 'Ana Souza')]
    aceito = cliente.post(f'/api/loja/agendamentos/{lista["itens"][0]["id"]}/aceitar', headers=h)
    assert aceito.status_code == 200, aceito.json()
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    assert 'A Loja loja-a já confirmou seu horário.' in pronto


# --- Passo 2: profissionais, dias e horários --------------------------------------------------------


def test_qualquer_profissional_mostra_quem_atende(cliente, site):
    passo2 = passo_horarios(cliente, site)
    blocos = re.findall(
        r'<a class="horario" href="([^"]+)">\s*<strong>(\d\d:\d\d)</strong>\s*(?:<span>([^<]+)</span>)?',
        passo2,
    )
    assert blocos
    assert all(nome in ('Admin', 'Profissional') for _, _, nome in blocos)
    for url, _, nome in blocos:
        quem = {'Admin': site.lt.admin.id, 'Profissional': site.lt.prof.id}[nome]
        assert parametros(html.unescape(url))['profissional'] == str(quem)


def test_escolher_um_profissional_filtra_os_horarios(cliente, site):
    prof = str(site.lt.prof.id)
    passo2 = passo_horarios(cliente, site, profissional=prof)
    assert f'<option value="{prof}" selected>Profissional</option>' in passo2
    urls = [h for h in hrefs(passo2) if h.startswith(f'{LOJA}/agendar/dados?')]
    assert urls
    assert all(parametros(u)['profissional'] == prof for u in urls)
    assert '<span>Profissional</span>' not in passo2  # com um profissional escolhido, não repete o nome
    # Os links dos dias mantêm o profissional escolhido
    dias = [h for h in hrefs(passo2) if '&dia=' in h]
    assert dias
    assert all(parametros(d)['profissional'] == prof for d in dias)


def test_faixa_de_dias_marca_o_dia_escolhido_e_os_dias_sem_horario(cliente, site, engine_dono):
    hoje = datetime.now(FUSO).date()
    depois = hoje + timedelta(days=3)
    passo2 = passo_horarios(cliente, site, dia=depois.isoformat())
    marcado = re.search(r'<a class="dia" href="([^"]+)"[^>]*aria-current="date"', passo2)
    assert marcado is not None
    assert parametros(html.unescape(marcado.group(1)))['dia'] == depois.isoformat()
    urls = [parametros(u) for u in hrefs(passo2) if u.startswith(f'{LOJA}/agendar/dados?')]
    assert urls
    assert all(datetime.fromisoformat(u['inicio']).date() == depois for u in urls)

    # Sem jornada no domingo: o dia aparece desabilitado, "Sem horários"
    with engine_dono.begin() as conexao:
        conexao.execute(text('DELETE FROM perfil_horarios WHERE dia_semana = 0'))
    passo2 = passo_horarios(cliente, site)
    assert 'Sem horários' in passo2
    assert '<span class="dia sem" aria-disabled="true"' in passo2


@pytest.mark.parametrize('dia', ['ontem', 'longe', '2030-02-30', 'amanhã', '9999-12-31', '0001-01-01'])
def test_dia_fora_da_faixa_ou_invalido_marca_o_primeiro_com_horarios(cliente, site, dia):
    hoje = datetime.now(FUSO).date()
    valor = {
        'ontem': (hoje - timedelta(days=1)).isoformat(),
        'longe': (hoje + timedelta(days=31)).isoformat(),
    }
    passo2 = passo_horarios(cliente, site, dia=valor.get(dia, dia))
    assert passo2.count('aria-current="date"') == 1


def test_sem_horarios_em_31_dias_mostra_o_telefone(cliente, clinica, engine_dono):
    alterar_loja(engine_dono, 'loja-a', telefone='(11) 3333-4444')
    with engine_dono.begin() as conexao:  # ninguém tem jornada
        conexao.execute(text('DELETE FROM perfil_horarios'))
    passo2 = passo_horarios(cliente, clinica)
    assert 'Nenhum horário livre nos próximos 31 dias.' in passo2
    assert '<a href="tel:1133334444">(11) 3333-4444</a>' in passo2
    assert 'class="horario"' not in passo2


def test_profissional_invalido_mostra_qualquer_profissional_com_aviso(cliente, site):
    for valor in ('abc', str(uuid4()), str(site.lt.recepcao.id)):  # Recepção não faz a Limpeza
        passo2 = passo_horarios(cliente, site, profissional=valor)
        assert 'Esse profissional não atende este serviço.' in passo2
        assert '<option value="" selected' not in passo2
        assert primeiro_horario(passo2)


# --- SIT-08 e módulo Locais -------------------------------------------------------------------------


def test_sem_modulo_servicos_a_pagina_inicial_ja_mostra_os_horarios(cliente, site, engine_dono):
    mudar_modulo(engine_dono, site.lt.loja.id, 'servicos', habilitado=False)
    inicio = pagina_html(cliente.get(LOJA))
    assert 'Atendimento · 30 min' in inicio
    assert 'Escolha o serviço' not in inicio
    assert 'class="voltar"' not in inicio  # não há passo 1 para voltar
    assert '>Serviço<' not in inicio  # indicador sem o passo "Serviço"
    assert '<li aria-current="step"><span class="passo-num" aria-hidden="true">1</span>' in inicio
    # Recepção também atende (todos com jornada)
    assert '<option value="' + str(site.lt.recepcao.id) + '">Recepção</option>' in inicio

    horario = primeiro_horario(inicio)
    assert 'servico' not in parametros(horario)
    passo3 = pagina_html(cliente.get(horario))
    assert 'Atendimento' in passo3
    resposta = enviar(cliente, {**ocultos(passo3), **CLIENTE})
    assert resposta.status_code == 303
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    assert 'Atendimento' in pronto
    assert 'R$' not in pronto  # sem preço


def test_com_locais_o_local_e_escolhido_e_mostrado_sem_link(cliente, clinica, engine_dono):
    rotulo = cliente.get('/api/site/loja-a').json()['rotulo_local']
    resposta = enviar(cliente, formulario_direto(clinica, '14:00'))
    assert resposta.status_code == 303
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    assert f'{rotulo}: Online' in pronto  # primeiro local permitido e livre (ordem alfabética)
    assert 'meet.example.com' not in pronto
    local = contar(engine_dono, 'SELECT count(*) FROM agendamentos WHERE local_id = :l', l=clinica.online)
    assert local == 1

    passo3 = pagina_html(
        cliente.get(
            f'{LOJA}/agendar/dados',
            params={
                'servico': clinica.limpeza,
                'profissional': str(clinica.lt.prof.id),
                'inicio': f'{SEGUNDA}T15:00-03:00',
                'local': clinica.sala1,
            },
        )
    )
    assert f'{rotulo}: Sala 1' in passo3
    assert 'meet.example.com' not in passo3


def test_sem_modulo_locais_nao_ha_local(cliente, clinica, engine_dono):
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'locais', habilitado=False)
    resposta = enviar(cliente, formulario_direto(clinica, '14:00', local=clinica.sala2))  # ignorado
    assert resposta.status_code == 303
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    assert 'Online' not in pronto
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos WHERE local_id IS NULL') == 1


# --- SIT-01: loja que não aparece ------------------------------------------------------------------

PAGINAS = ['', '/agendar', '/agendar/dados', '/agendar/pronto?c=x']


@pytest.mark.parametrize('situacao', [StatusLoja.suspensa, StatusLoja.cancelada, 'excluida', 'inexistente'])
def test_loja_que_nao_aparece_responde_404_em_todas_as_paginas(cliente, engine_dono, situacao):
    if situacao == 'inexistente':
        slug = 'nao-existe'
    else:
        slug = 'fechada'
        criar_loja(engine_dono, slug, status=StatusLoja.ativa if situacao == 'excluida' else situacao)
        if situacao == 'excluida':
            alterar_loja(engine_dono, slug, excluido_em=datetime.now(UTC))
    for pagina in PAGINAS:
        texto = pagina_html(cliente.get(f'/{slug}{pagina}'), 404)
        assert 'Loja não encontrada' in texto
        assert 'Loja fechada' not in texto
    texto = pagina_html(enviar(cliente, {'nome': 'Ana'}, slug=slug), 404)
    assert 'Loja não encontrada' in texto


@pytest.mark.parametrize('slug', ['LOJA-A', 'admin', 'static', 'a' * 61])
def test_endereco_invalido_ou_reservado_responde_404(cliente, clinica, slug):
    for pagina in PAGINAS:
        pagina_html(cliente.get(f'/{slug}{pagina}'), 404)
    pagina_html(enviar(cliente, formulario_direto(clinica), slug=slug), 404)


# --- Parâmetros inválidos nunca dão 500 ---------------------------------------------------------------


def _parametros_estranhos(clinica):
    servico, prof = clinica.limpeza, str(clinica.lt.prof.id)
    return [
        ('/agendar', {}),
        ('/agendar', {'servico': 'abc'}),
        ('/agendar', {'servico': str(uuid4())}),
        ('/agendar', {'servico': servico, 'profissional': 'x' * 5000}),
        ('/agendar', {'servico': servico, 'dia': '2030-13-01'}),
        ('/agendar', {'servico': servico, 'dia': '99999-01-01'}),
        ('/agendar', {'servico': servico, 'aviso': '<script>'}),
        ('/agendar/dados', {}),
        ('/agendar/dados', {'servico': servico}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': 'amanhã'}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': '9999-12-31T23:30'}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': '0001-01-01T00:00'}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': '2030-01-07T25:00'}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': '2030-01-07T08:00+99:00'}),
        ('/agendar/dados', {'servico': servico, 'profissional': prof, 'inicio': f'{SEGUNDA}T08:10'}),
        ('/agendar/dados', {'servico': servico, 'profissional': 'abc', 'inicio': f'{SEGUNDA}T08:00'}),
        ('/agendar/dados', {'servico': servico, 'profissional': str(uuid4()), 'inicio': f'{SEGUNDA}T08:00'}),
        (
            '/agendar/dados',
            {'servico': servico, 'profissional': str(clinica.lt.recepcao.id), 'inicio': f'{SEGUNDA}T08:00'},
        ),
        (
            '/agendar/dados',
            {'servico': servico, 'profissional': prof, 'inicio': f'{SEGUNDA}T08:00', 'local': 'x'},
        ),
        (
            '/agendar/dados',
            {'servico': servico, 'profissional': prof, 'inicio': f'{SEGUNDA}T08:00', 'local': clinica.sala2},
        ),
        ('/agendar/pronto', {}),
        ('/agendar/pronto', {'c': 'x' * 5000}),
        ('/agendar/pronto', {'c': f'{"0" * 40}.{"A" * 22}'}),
    ]


def test_parametros_invalidos_nunca_dao_erro_do_servidor(cliente, clinica):
    for caminho, params in _parametros_estranhos(clinica):
        resposta = cliente.get(f'{LOJA}{caminho}', params=params, follow_redirects=False)
        assert resposta.status_code in (200, 303, 404), (caminho, params, resposta.status_code)
        if resposta.status_code != 303:
            assert resposta.headers['content-type'] == 'text/html; charset=utf-8', (caminho, params)
        else:
            destino = cliente.get(resposta.headers['location'])
            assert destino.status_code == 200, (caminho, params)
            assert '<script>' not in destino.text


def test_servico_invalido_volta_ao_passo_1_com_aviso(cliente, clinica):
    resposta = cliente.get(f'{LOJA}/agendar', params={'servico': str(uuid4())}, follow_redirects=False)
    assert (resposta.status_code, resposta.headers['location']) == (303, f'{LOJA}?aviso=servico')
    passo1 = pagina_html(cliente.get(resposta.headers['location']))
    assert 'Esse serviço não está mais disponível. Escolha outro.' in passo1
    sem_servico = cliente.get(f'{LOJA}/agendar', follow_redirects=False)
    assert (sem_servico.status_code, sem_servico.headers['location']) == (303, LOJA)


def test_horario_que_nao_e_oferecido_volta_ao_passo_2_do_dia(cliente, clinica):
    resposta = cliente.get(
        f'{LOJA}/agendar/dados',
        params={
            'servico': clinica.limpeza,
            'profissional': str(clinica.lt.prof.id),
            'inicio': f'{SEGUNDA}T08:10',
        },
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    destino = parametros(resposta.headers['location'])
    assert destino == {'servico': clinica.limpeza, 'dia': SEGUNDA, 'aviso': 'ocupado'}


# --- Horário ocupado e corrida --------------------------------------------------------------------


def test_horario_ocupado_entre_o_passo_3_e_o_envio(cliente, clinica, engine_dono):
    passo3 = pagina_html(
        cliente.get(
            f'{LOJA}/agendar/dados',
            params={
                'servico': clinica.limpeza,
                'profissional': str(clinica.lt.prof.id),
                'inicio': f'{SEGUNDA}T09:00',
            },
        )
    )
    # A recepção marca o mesmo horário pelo painel antes do envio
    ocupado = cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=clinica.lt.h_admin)
    assert ocupado.status_code == 201, ocupado.json()

    resposta = enviar(cliente, {**ocultos(passo3), **CLIENTE})
    assert resposta.status_code == 303
    assert parametros(resposta.headers['location']) == {
        'servico': clinica.limpeza,
        'dia': SEGUNDA,
        'aviso': 'ocupado',
    }
    assert resposta.headers['location'].endswith('#horarios')
    assert MSG_OCUPADO in pagina_html(cliente.get(resposta.headers['location']))
    assert contar(engine_dono, "SELECT count(*) FROM agendamentos WHERE origem = 'site'") == 0
    assert contar(engine_dono, "SELECT count(*) FROM clientes WHERE telefone = '(11) 97777-6666'") == 0


def test_dois_pedidos_no_mesmo_horario_o_segundo_volta_com_aviso(cliente, clinica, engine_dono):
    assert enviar(cliente, formulario_direto(clinica, '10:00')).status_code == 303
    segundo = enviar(cliente, formulario_direto(clinica, '10:00', telefone='(11) 95555-4444'))
    assert segundo.status_code == 303
    assert parametros(segundo.headers['location'])['aviso'] == 'ocupado'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def test_corrida_recusada_pelo_banco_volta_ao_passo_2(cliente, clinica, engine_dono, monkeypatch):
    """Outro pedido grava o horário entre a conferência e a gravação: o EXCLUDE recusa (23P01)."""
    from app.services.horarios_livres import Agenda

    assert enviar(cliente, formulario_direto(clinica, '10:00')).status_code == 303
    monkeypatch.setattr(Agenda, '_sobrepoe', staticmethod(lambda *_: False))
    segundo = enviar(cliente, formulario_direto(clinica, '10:00', telefone='(11) 95555-4444'))
    assert segundo.status_code == 303
    assert parametros(segundo.headers['location'])['aviso'] == 'ocupado'
    # A recusa desfez só o pedido: nem o cliente novo ficou gravado
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1
    assert contar(engine_dono, "SELECT count(*) FROM clientes WHERE telefone = '(11) 95555-4444'") == 0


def test_envio_repetido_do_mesmo_pedido_mostra_a_mesma_confirmacao(cliente, clinica, engine_dono):
    """LOG-07: o mesmo formulário enviado duas vezes (duplo clique sem JS) não cria dois pedidos nem
    diz que o horário foi ocupado."""
    primeiro = enviar(cliente, formulario_direto(clinica, '10:00'))
    segundo = enviar(cliente, formulario_direto(clinica, '10:00'))
    assert (primeiro.status_code, segundo.status_code) == (303, 303)
    assert segundo.headers['location'].startswith(f'{LOJA}/agendar/pronto?c=')
    assert pagina_html(cliente.get(primeiro.headers['location'])) == pagina_html(
        cliente.get(segundo.headers['location'])
    )
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1
    # Maiúsculas diferentes no nome também contam como o mesmo formulário
    terceiro = enviar(cliente, formulario_direto(clinica, '10:00', nome='ANA', sobrenome='souza'))
    assert terceiro.headers['location'].startswith(f'{LOJA}/agendar/pronto?c=')
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def _destino(resposta) -> str:
    return urlsplit(resposta.headers['location']).path


@pytest.mark.parametrize(
    ('extra', 'esperado'),
    [
        (
            {'nome': '', 'sobrenome': '', 'email': ''},
            f'{LOJA}/agendar',
        ),  # só telefone, profissional e horário
        ({'nome': 'Outra', 'sobrenome': 'Pessoa'}, f'{LOJA}/agendar'),
        ({'email': 'outra@example.com'}, f'{LOJA}/agendar'),
        ({'email': ''}, f'{LOJA}/agendar'),
        ({'observacoes': 'Outra observação'}, f'{LOJA}/agendar'),
    ],
)
def test_quem_so_conhece_telefone_e_horario_nao_recebe_o_pedido_alheio(
    cliente, clinica, engine_dono, extra, esperado
):
    """SIT-07/SEG-06: a repetição só vale com o formulário inteiro igual; senão é um pedido novo
    (que encontra o horário ocupado) ou um formulário com erros. O código do pedido nunca é entregue."""
    assert enviar(cliente, formulario_direto(clinica, '10:00')).status_code == 303
    resposta = enviar(cliente, formulario_direto(clinica, '10:00', **extra))
    assert resposta.status_code == 303
    assert _destino(resposta) == esperado
    assert parametros(resposta.headers['location'])['aviso'] == 'ocupado'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def test_telefone_de_cliente_ja_cadastrado_nunca_conta_como_repeticao(cliente, clinica, engine_dono):
    """O telefone é da Maria (cadastro da loja): o nome digitado não fica gravado, então o envio
    repetido não é reconhecido e volta à escolha de horário, sem mostrar o pedido."""
    dados = formulario_direto(
        clinica, '10:00', nome='Maria', sobrenome='Oliveira', telefone='(11) 98888-1111'
    )
    assert _destino(enviar(cliente, dados)) == f'{LOJA}/agendar/pronto'
    repetido = enviar(cliente, dados)
    assert _destino(repetido) == f'{LOJA}/agendar'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def test_repeticao_acima_do_limite_de_pedidos_nao_mostra_o_pedido(clinica, com_ip, monkeypatch, engine_dono):
    """O limite de pedidos por IP vem antes da repetição: quem passou dele não recebe código nenhum."""
    monkeypatch.setattr(get_settings(), 'limite_site_pedidos_por_ip', 1)
    assert enviar(com_ip('198.51.100.50'), formulario_direto(clinica, '10:00')).status_code == 303
    c = com_ip('198.51.100.51')
    assert _destino(enviar(c, formulario_direto(clinica, '10:00'))) == f'{LOJA}/agendar/pronto'  # 1º do IP
    excesso = enviar(c, formulario_direto(clinica, '10:00'))
    # Acima do limite, a escolha é conferida para mostrar o formulário: já não é oferecida, volta ao passo 2
    assert excesso.status_code == 303
    assert _destino(excesso) == f'{LOJA}/agendar'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def _postar_ao_mesmo_tempo(url: str, formularios: list[dict[str, str]]) -> list[httpx.Response]:
    barreira = threading.Barrier(len(formularios))
    respostas: list[httpx.Response | None] = [None] * len(formularios)
    erros: list[BaseException] = []

    def postar(i: int) -> None:
        try:
            with httpx.Client(base_url=url, timeout=60) as c:
                barreira.wait()
                respostas[i] = c.post(f'{LOJA}/agendar', data=formularios[i])
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=postar, args=(i,)) for i in range(len(formularios))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if erros:
        raise erros[0]
    return [r for r in respostas if r is not None]


def test_pedidos_simultaneos_no_mesmo_horario_so_um_passa(clinica, engine_dono, servidor):
    telefones = ['(11) 91111-0001', '(11) 91111-0002', '(11) 91111-0003', '(11) 91111-0004']
    respostas = _postar_ao_mesmo_tempo(
        servidor, [formulario_direto(clinica, '11:00', telefone=t) for t in telefones]
    )
    destinos = sorted(urlsplit(r.headers['location']).path for r in respostas)
    assert [r.status_code for r in respostas] == [303] * 4
    assert destinos == [f'{LOJA}/agendar'] * 3 + [f'{LOJA}/agendar/pronto']
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1
    assert contar(engine_dono, "SELECT count(*) FROM clientes WHERE telefone LIKE '(11) 91111-%'") == 1


def test_envios_simultaneos_do_mesmo_formulario_no_limite_de_pendentes(
    clinica, engine_dono, servidor, monkeypatch
):
    """LOG-07: com o telefone no limite de pendentes, o segundo envio simultâneo do mesmo formulário
    leva à confirmação do pedido gravado pelo primeiro, e não ao aviso de pedidos pendentes."""
    monkeypatch.setattr(get_settings(), 'site_pendentes_por_telefone', 1)
    monkeypatch.setattr(get_settings(), 'limite_site_pedidos_por_ip', 100)  # todos saem do mesmo IP
    for rodada, hora in enumerate(('08:00', '13:00', '15:00', '17:00')):
        formulario = formulario_direto(clinica, hora, telefone=f'(11) 93333-000{rodada}')
        respostas = _postar_ao_mesmo_tempo(servidor, [formulario, formulario, formulario])
        assert [r.status_code for r in respostas] == [303] * 3, rodada
        assert [_destino(r) for r in respostas] == [f'{LOJA}/agendar/pronto'] * 3, rodada
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 4


# --- Validação, armadilha e origem ----------------------------------------------------------------


def test_erro_de_validacao_volta_ao_formulario_com_os_valores(cliente, clinica, engine_dono):
    dados = formulario_direto(
        clinica,
        nome='   ',
        sobrenome='Souza <b>',
        telefone='1234',
        email='nao-e-email',
        observacoes='x' * 501,
    )
    texto = pagina_html(enviar(cliente, dados), 200)
    assert 'id="resumo-erros" role="alert" tabindex="-1"' in texto
    assert '<a href="#campo-nome">Nome: Campo obrigatório.</a>' in texto
    assert 'Informe o telefone com DDD (ex.: (11) 99999-9999).' in texto
    assert 'E-mail inválido.' in texto
    assert 'Texto muito longo (máximo de 500 caracteres).' in texto
    # Valores preservados (escapados) e mensagens ligadas aos campos
    assert 'value="Souza &lt;b&gt;"' in texto
    assert 'value="1234"' in texto
    assert 'value="nao-e-email"' in texto
    assert 'aria-invalid="true" aria-describedby="erro-telefone"' in texto
    assert '<p class="erro-campo" id="erro-telefone">' in texto
    assert 'id="erro-sobrenome"' not in texto
    # A escolha continua no formulário
    assert ocultos(texto)['inicio'] == f'{SEGUNDA}T08:00-03:00'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0


def test_campo_armadilha_parece_sucesso_e_nao_grava_nada(cliente, clinica, engine_dono):
    clientes_antes = contar(engine_dono, 'SELECT count(*) FROM clientes')
    resposta = enviar(cliente, formulario_direto(clinica, zx_conferencia='http://spam.example'))
    assert resposta.status_code == 303
    assert resposta.headers['location'].startswith(f'{LOJA}/agendar/pronto?c=')
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    assert 'Pedido enviado!' in pronto
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0
    assert contar(engine_dono, 'SELECT count(*) FROM clientes') == clientes_antes
    # O campo existe na página, escondido e fora da navegação por teclado
    passo3 = pagina_html(
        cliente.get(
            f'{LOJA}/agendar/dados',
            params={
                k: v
                for k, v in formulario_direto(clinica).items()
                if k in ('servico', 'profissional', 'inicio')
            },
        )
    )
    assert '<div class="armadilha" aria-hidden="true">' in passo3
    assert 'name="zx_conferencia" type="text" tabindex="-1" autocomplete="off"' in passo3
    # Escondido com display: none (o navegador não preenche o que não aparece), por classe (CSP)
    assert re.search(r'\.armadilha \{\s*display: none;\s*\}', cliente.get('/static/site/site.css').text)
    # Nome neutro: nada que lembre endereço, site ou e-mail (autopreenchimento)
    assert not re.search(r'endereco|address|web|url|site|mail|tel|nome|name', 'zx_conferencia')


@pytest.mark.parametrize(
    'cabecalhos',
    [
        {'Origin': 'https://outro-site.example'},
        {'Origin': 'null'},
        {'Referer': 'https://outro-site.example/pagina'},
        {'Origin': 'http://testserver', 'Referer': 'https://outro-site.example/'},
    ],
)
def test_envio_vindo_de_outro_site_e_recusado(cliente, clinica, engine_dono, cabecalhos):
    resposta = enviar(cliente, formulario_direto(clinica), headers=cabecalhos)
    texto = pagina_html(resposta, 403)
    assert 'Não foi possível enviar o pedido' in texto
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0


def test_envio_da_propria_origem_e_aceito(cliente, clinica):
    cabecalhos = {'Origin': 'http://testserver', 'Referer': 'http://testserver/loja-a/agendar/dados?x=1'}
    assert enviar(cliente, formulario_direto(clinica), headers=cabecalhos).status_code == 303


def test_envio_mal_formado_volta_ao_passo_certo(cliente, clinica, engine_dono):
    vazio = enviar(cliente, {})
    assert (vazio.status_code, vazio.headers['location']) == (303, LOJA)
    sem_horario = enviar(cliente, {'servico': clinica.limpeza, **CLIENTE})
    assert sem_horario.status_code == 303
    assert parametros(sem_horario.headers['location'])['aviso'] == 'horario'
    json = cliente.post(f'{LOJA}/agendar', json=formulario_direto(clinica), follow_redirects=False)
    assert json.status_code == 303
    arquivo = cliente.post(
        f'{LOJA}/agendar',
        data=formulario_direto(clinica),
        files={'x': ('a.txt', b'oi')},
        follow_redirects=False,
    )
    assert arquivo.status_code == 303
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0


# --- Passo 4: código assinado ---------------------------------------------------------------------


def test_codigo_da_confirmacao_adulterado_expirado_ou_de_outra_loja(cliente, clinica, engine_dono, lojas):
    resposta = enviar(cliente, formulario_direto(clinica))
    codigo = parametros(resposta.headers['location'])['c']
    assert (
        pagina_html(cliente.get(f'{LOJA}/agendar/pronto', params={'c': codigo})).count('Pedido enviado!') == 1
    )

    trocado = codigo[:-1] + ('A' if codigo[-1] != 'A' else 'B')
    outro_id = f'{uuid4().hex}{codigo[32:]}'
    agendamento_id = contar(engine_dono, 'SELECT id FROM agendamentos')
    expirado = codigo_do_pedido(
        clinica.lt.loja.id, agendamento_id, agora=datetime.now(UTC) - timedelta(hours=25)
    )
    for invalido in (trocado, outro_id, expirado, codigo.upper(), codigo + 'x', ''):
        pagina_html(cliente.get(f'{LOJA}/agendar/pronto', params={'c': invalido}), 404)
    # O código da loja A não abre nada na loja B
    texto = pagina_html(cliente.get('/loja-b/agendar/pronto', params={'c': codigo}), 404)
    assert 'Limpeza' not in texto
    # Código válido de um pedido excluído depois: 404
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE agendamentos SET excluido_em = now()'))
    pagina_html(cliente.get(f'{LOJA}/agendar/pronto', params={'c': codigo}), 404)


def test_confirmacao_nao_revela_o_nome_cadastrado_do_cliente(cliente, clinica):
    """SIT-07: o telefone já é da Maria; quem pediu escreveu outro nome. Nada do cadastro aparece."""
    resposta = enviar(cliente, formulario_direto(clinica, nome='Outra', telefone='(11) 98888-1111'))
    pronto = pagina_html(cliente.get(resposta.headers['location']))
    for proibido in ('Maria', 'Oliveira', '98888', 'Outra'):
        assert proibido not in pronto


# --- Limites (SIT-10) -----------------------------------------------------------------------------


@pytest.fixture
def com_ip():
    from app.main import app

    clientes = []

    def criar(ip: str) -> TestClient:
        c = TestClient(app, client=(ip, 50000))
        clientes.append(c)
        return c

    yield criar
    for c in clientes:
        c.close()


def test_paginas_do_fluxo_contam_no_limite_do_site(clinica, com_ip, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_site_por_ip', 4)
    c = com_ip('198.51.100.30')
    assert c.get(LOJA).status_code == 200
    assert c.get(f'{LOJA}/agendar', params={'servico': clinica.limpeza}).status_code == 200
    assert c.get(f'{LOJA}/agendar/pronto', params={'c': 'x'}).status_code == 404
    assert c.get('/api/site/loja-a').status_code == 200  # mesmo contador da API do site
    excesso = c.get(f'{LOJA}/agendar/dados')
    texto = pagina_html(excesso, 429)
    assert 'Muitas requisições' in texto
    assert 1 <= int(excesso.headers['retry-after']) <= 60
    assert enviar(c, formulario_direto(clinica)).status_code == 429
    assert com_ip('198.51.100.31').get(LOJA).status_code == 200


def test_envio_conta_no_limite_de_pedidos_e_preserva_o_formulario(clinica, com_ip, monkeypatch, engine_dono):
    monkeypatch.setattr(get_settings(), 'limite_site_pedidos_por_ip', 1)
    c = com_ip('198.51.100.40')
    assert enviar(c, formulario_direto(clinica, '08:00')).status_code == 303
    excesso = enviar(c, formulario_direto(clinica, '09:00', telefone='(11) 92222-3333', nome='Bia'))
    texto = pagina_html(excesso, 429)
    eh_do_site(excesso)
    assert 'Muitas requisições. Aguarde um pouco e tente novamente.' in texto
    assert 'value="Bia"' in texto
    assert 'value="(11) 92222-3333"' in texto
    assert int(excesso.headers['retry-after']) >= 1
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1
    # As páginas de leitura não contam no limite de pedidos
    assert c.get(LOJA).status_code == 200


def test_limite_de_pendentes_por_telefone_volta_ao_formulario(cliente, clinica, monkeypatch, engine_dono):
    monkeypatch.setattr(get_settings(), 'site_pendentes_por_telefone', 1)
    assert enviar(cliente, formulario_direto(clinica, '08:00')).status_code == 303
    resposta = enviar(cliente, formulario_direto(clinica, '09:00', observacoes='Pode ser à tarde'))
    texto = pagina_html(resposta, 409)
    assert MSG_PENDENTES in texto
    assert 'Pode ser à tarde</textarea>' in texto
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


# --- DIR-003, escapamento, cabeçalhos e arquivos ---------------------------------------------------


def test_nenhuma_pagina_do_fluxo_leva_ao_painel(cliente, site, engine_dono):
    alterar_loja(
        engine_dono, 'loja-a', telefone='(11) 3333-4444', logradouro='Rua A', cidade='Campinas', uf='SP'
    )
    passo1 = cliente.get(LOJA).text
    passo2 = passo_horarios(cliente, site)
    passo3 = cliente.get(primeiro_horario(passo2)).text
    erro = enviar(cliente, {**ocultos(passo3), 'nome': ''}).text
    pronto = cliente.get(enviar(cliente, {**ocultos(passo3), **CLIENTE}).headers['location']).text
    vazio = cliente.get('/loja-b').text
    arquivos = [cliente.get(f'/static/site/{nome}').text for nome in ('site.css', 'site.js')]
    for texto in (passo1, passo2, passo3, erro, pronto, vazio, *arquivos):
        minusculo = texto.lower()
        for proibido in ('/painel', 'painel', 'superadmin', 'login'):
            assert proibido not in minusculo, proibido


def test_nome_da_loja_e_do_servico_saem_escapados(cliente, clinica, engine_dono):
    alterar_loja(engine_dono, 'loja-a', nome_fantasia='<script>alert(1)</script>')
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE servicos SET nome = :nome, descricao = :descricao WHERE id = :id'),
            {
                'nome': '<script>alert(2)</script>',
                'descricao': '<img src=x onerror=alert(3)>',
                'id': clinica.limpeza,
            },
        )
    passo1 = cliente.get(LOJA).text
    passo2 = passo_horarios(cliente, clinica, dia=SEGUNDA)
    passo3 = pagina_html(
        cliente.get(
            f'{LOJA}/agendar/dados',
            params={
                'servico': clinica.limpeza,
                'profissional': str(clinica.lt.prof.id),
                'inicio': f'{SEGUNDA}T08:00',
            },
        )
    )
    for texto in (passo1, passo2, passo3):
        assert '<script>' not in texto
        assert '<img src=x' not in texto
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in texto
    assert '&lt;script&gt;alert(2)&lt;/script&gt;' in passo1
    assert '&lt;img src=x onerror=alert(3)&gt;' in passo1


def test_cabecalhos_e_indexacao(cliente, site):
    inicio = cliente.get(LOJA)
    eh_do_site(inicio)
    assert 'noindex' not in inicio.text
    passo2 = cliente.get(f'{LOJA}/agendar', params={'servico': site.limpeza})
    eh_do_site(passo2)
    passo3 = cliente.get(primeiro_horario(passo2.text))
    eh_do_site(passo3)
    for texto in (passo2.text, passo3.text):
        assert '<meta name="robots" content="noindex">' in texto
        assert '<html lang="pt-BR">' in texto
    css = re.search(r'<link rel="stylesheet" href="(/static/site/site\.css\?v=[0-9a-f]{12})">', inicio.text)
    js = re.search(r'<script src="(/static/site/site\.js\?v=[0-9a-f]{12})" defer></script>', inicio.text)
    assert css is not None
    assert js is not None
    assert 'style=' not in inicio.text  # CSP sem estilo embutido
    assert '<script>' not in inicio.text


def test_head_nas_paginas_do_site(cliente, site):
    for caminho in (LOJA, f'{LOJA}/agendar?servico={site.limpeza}'):
        get, head = cliente.get(caminho), cliente.head(caminho)
        assert (head.status_code, head.headers['content-type']) == (
            get.status_code,
            get.headers['content-type'],
        )


def test_arquivos_do_site(cliente, clinica):
    inicio = cliente.get(LOJA).text
    css_url = re.search(r'href="(/static/site/site\.css\?v=\w+)"', inicio).group(1)
    css = cliente.get(css_url)
    assert css.status_code == 200
    assert css.headers['content-type'] == 'text/css; charset=utf-8'
    assert css.headers['cache-control'] == 'public, max-age=31536000, immutable'
    assert css.headers['x-content-type-options'] == 'nosniff'
    assert '.tipo-barbearia' in css.text
    assert '.tipo-escola' in css.text
    js = cliente.get('/static/site/site.js')
    assert js.headers['content-type'] == 'text/javascript; charset=utf-8'
    assert js.headers['cache-control'] == 'no-cache'  # sem a versão certa, não guarda
    for caminho in ('/static/site/outro.css', '/static/site/..%2F..%2Fconfig.py', '/static/x', '/static'):
        assert cliente.get(caminho).status_code == 404


@pytest.mark.parametrize('tipo', ['clinica', 'barbearia', 'escola'])
def test_cada_tipo_de_loja_tem_identidade_e_frase(cliente, clinica, engine_dono, tipo):
    alterar_loja(engine_dono, 'loja-a', tipo=tipo)
    texto = cliente.get(LOJA).text
    frases = {
        'clinica': 'Agende sua consulta online, em poucos passos.',
        'barbearia': 'Marque seu horário online, em poucos passos.',
        'escola': 'Agende sua aula online, em poucos passos.',
    }
    assert f'<body class="tipo-{tipo}">' in texto
    assert frases[tipo] in texto


# --- Isolamento e estados vazios -----------------------------------------------------------------


def test_ids_de_outra_loja_nao_valem(cliente, clinica, engine_dono):
    resposta = cliente.get('/loja-b/agendar', params={'servico': clinica.limpeza}, follow_redirects=False)
    assert (resposta.status_code, resposta.headers['location']) == (303, '/loja-b?aviso=servico')
    dados = cliente.get(
        '/loja-b/agendar/dados',
        params={
            'servico': clinica.limpeza,
            'profissional': str(clinica.lt.prof.id),
            'inicio': f'{SEGUNDA}T08:00',
        },
        follow_redirects=False,
    )
    assert dados.status_code == 303
    assert urlsplit(dados.headers['location']).path == '/loja-b'
    envio = enviar(cliente, formulario_direto(clinica), slug='loja-b')
    assert envio.status_code == 303
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0


def test_loja_sem_servicos_disponiveis_mostra_o_telefone(cliente, lojas, engine_dono):
    alterar_loja(engine_dono, 'loja-b', telefone='(21) 2222-3333')
    texto = pagina_html(cliente.get('/loja-b'))
    assert 'No momento não há horários para agendar online.' in texto
    assert '<a href="tel:2122223333">(21) 2222-3333</a>' in texto
    assert 'class="servico"' not in texto


def test_cabecalho_com_logo_endereco_e_nome_longo(cliente, clinica, engine_dono):
    nome = 'Clínica ' + 'Muito ' * 20 + 'Comprida'
    alterar_loja(
        engine_dono,
        'loja-a',
        nome_fantasia=nome[:150],
        telefone='(11) 98888-1111',
        logradouro='Rua das Flores',
        numero='120',
        complemento='Sala 3',
        bairro='Centro',
        cidade='Campinas',
        uf='SP',
        logo_url='/api/arquivos/logos/x/logo.png',
        cnpj='11.222.333/0001-81',
    )
    texto = cliente.get(LOJA).text
    assert f'<h1 class="nome">{nome[:150]}</h1>' in texto
    assert '<img class="logo" src="/api/arquivos/logos/x/logo.png"' in texto
    assert 'Rua das Flores, 120 - Sala 3 · Centro · Campinas/SP' in texto
    assert '<a href="tel:11988881111">(11) 98888-1111</a>' in texto
    assert '<p class="tipo">Clínica</p>' in texto
    assert '11.222.333' not in texto
