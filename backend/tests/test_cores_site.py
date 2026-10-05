"""Cores do site escolhidas pela loja (SIT-13 a SIT-15, PLA-20): API da loja e do SUPERADMIN, banco e site.

Especificação: docs/funcionalidades/cores-site.md.
"""

import re
from datetime import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import PerfilHorario
from app.models.enums import TipoLoja
from app.routers.html import CSP_SITE
from app.services.cores_site import (
    BRANCO,
    CONTRASTE_MINIMO,
    MSG_CONTRASTE_COR,
    MSG_FORMATO_COR,
    PALETAS,
    contraste,
    css_da_loja,
    legivel_com_branco,
    ler_cor,
)
from tests.fabricas import cabecalho_superadmin, criar_loja, criar_superadmin, inserir, usuario_com
from tests.test_site_paginas import CLIENTE, enviar, link, ocultos, pagina_html, primeiro_horario

URL = '/api/loja/configuracoes/site'
URL_SA = '/api/superadmin/lojas/{}/site'
TOPO, DESTAQUE = '#7a1f3d', '#1f5f8b'
PADRAO_CLINICA = {'cor_topo': '#0d4b4f', 'cor_destaque': '#0b6767'}
SITE_CSS = Path(__file__).resolve().parent.parent / 'app' / 'static' / 'site' / 'site.css'


@pytest.fixture
def sa(engine_dono):
    superadmin = criar_superadmin(engine_dono)
    return superadmin, cabecalho_superadmin(superadmin)


def salvar(cliente, h, topo=TOPO, destaque=DESTAQUE, url=URL):
    return cliente.put(url, json={'cor_topo': topo, 'cor_destaque': destaque}, headers=h)


def cores_no_banco(engine, loja_id) -> tuple[str | None, str | None]:
    with engine.connect() as conexao:
        return tuple(
            conexao.execute(
                text('SELECT cor_site_topo, cor_site_destaque FROM loja_configuracoes WHERE loja_id = :l'),
                {'l': loja_id},
            ).one()
        )


def auditoria_das_cores(engine, loja_id) -> list[dict]:
    with engine.connect() as conexao:
        return [
            dict(linha)
            for linha in conexao.execute(
                text(
                    'SELECT loja_id, funcionario_id, superadmin_id, origem::text AS origem, campos_alterados'
                    " FROM auditoria WHERE tabela = 'loja_configuracoes' AND operacao = 'alterar'"
                    ' AND loja_id = :l ORDER BY id'
                ),
                {'l': loja_id},
            ).mappings()
        ]


# --- API da loja ---------------------------------------------------------------------------------


def test_sem_cores_escolhidas_mostra_o_padrao_do_tipo(cliente, lojas):
    a, _ = lojas
    resposta = cliente.get(URL, headers=a.h_admin)
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert set(corpo) == {
        'cor_topo',
        'cor_destaque',
        'padrao',
        'tipo',
        'criado_em',
        'atualizado_em',
        'atualizado_por',
        'atualizado_por_nome',
    }
    assert (corpo['cor_topo'], corpo['cor_destaque']) == (None, None)
    assert corpo['padrao'] == PADRAO_CLINICA
    assert corpo['tipo'] == 'clinica'
    assert corpo['criado_em'].endswith('-03:00')
    assert corpo['atualizado_em'].endswith('-03:00')
    assert (corpo['atualizado_por'], corpo['atualizado_por_nome']) == (None, None)


def test_salvar_normaliza_e_null_volta_ao_padrao(cliente, lojas, engine_dono):
    a, _ = lojas
    resposta = salvar(cliente, a.h_admin, '  #7A1F3D ', '#1F5f8B')
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert (corpo['cor_topo'], corpo['cor_destaque']) == (TOPO, DESTAQUE)
    assert corpo['padrao'] == PADRAO_CLINICA
    assert (corpo['atualizado_por'], corpo['atualizado_por_nome']) == (str(a.admin.id), 'Admin')
    assert corpo['atualizado_em'].endswith('-03:00')
    assert cores_no_banco(engine_dono, a.loja.id) == (TOPO, DESTAQUE)
    assert cliente.get(URL, headers=a.h_admin).json() == corpo

    # "Voltar ao padrão" numa cor só (null; texto vazio vale o mesmo, como nos outros campos opcionais)
    so_destaque = salvar(cliente, a.h_admin, None, DESTAQUE).json()
    assert (so_destaque['cor_topo'], so_destaque['cor_destaque']) == (None, DESTAQUE)
    assert salvar(cliente, a.h_admin, TOPO, '  ').json()['cor_destaque'] is None
    assert cores_no_banco(engine_dono, a.loja.id) == (TOPO, None)
    assert salvar(cliente, a.h_admin, None, None).status_code == 200
    assert cores_no_banco(engine_dono, a.loja.id) == (None, None)


def test_campos_fora_do_contrato_sao_ignorados(cliente, lojas, engine_dono):
    a, b = lojas
    corpo = {'cor_topo': TOPO, 'cor_destaque': None, 'loja_id': str(b.loja.id), 'tipo': 'escola'}
    resposta = cliente.put(URL, json=corpo, headers=a.h_admin)
    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()['tipo'] == 'clinica'
    assert cores_no_banco(engine_dono, a.loja.id) == (TOPO, None)
    assert cores_no_banco(engine_dono, b.loja.id) == (None, None)


@pytest.mark.parametrize(
    'valor',
    [
        '#fff',
        'red',
        '#12345g',
        '#1234567',
        '1f5f8b',
        '##1f5f8b',
        '# 1f5f8b',
        'url(javascript:alert(1))',
        '#1f5f8b;}',
        ';}body{display:none}',
        '#1f5f8b</style>',
        'rgb(0,0,0)',
        123,
        ['#1f5f8b'],
        {'cor': '#1f5f8b'},
        True,
    ],
)
@pytest.mark.parametrize('campo', ['cor_topo', 'cor_destaque'])
def test_formato_invalido_e_recusado_no_campo_certo(cliente, lojas, engine_dono, campo, valor):
    a, _ = lojas
    corpo = {'cor_topo': TOPO, 'cor_destaque': DESTAQUE, campo: valor}
    resposta = cliente.put(URL, json=corpo, headers=a.h_admin)
    assert resposta.status_code == 422
    assert resposta.json() == {
        'detail': 'Verifique os dados informados.',
        'erros': [{'campo': campo, 'mensagem': MSG_FORMATO_COR}],
    }
    assert cores_no_banco(engine_dono, a.loja.id) == (None, None)


def test_as_duas_cores_sao_obrigatorias_no_corpo(cliente, lojas):
    a, _ = lojas
    resposta = cliente.put(URL, json={'cor_topo': TOPO}, headers=a.h_admin)
    assert resposta.status_code == 422
    assert resposta.json()['erros'] == [{'campo': 'cor_destaque', 'mensagem': 'Campo obrigatório.'}]


def test_cor_clara_demais_e_recusada(cliente, lojas, engine_dono):
    a, _ = lojas
    resposta = salvar(cliente, a.h_admin, '#ffeb3b', '#FFFFFF')
    assert resposta.status_code == 422
    assert resposta.json()['erros'] == [
        {'campo': 'cor_topo', 'mensagem': MSG_CONTRASTE_COR},
        {'campo': 'cor_destaque', 'mensagem': MSG_CONTRASTE_COR},
    ]
    # Erros diferentes em cada campo, de uma vez
    misto = salvar(cliente, a.h_admin, 'red', '#ffeb3b')
    assert misto.json()['erros'] == [
        {'campo': 'cor_topo', 'mensagem': MSG_FORMATO_COR},
        {'campo': 'cor_destaque', 'mensagem': MSG_CONTRASTE_COR},
    ]
    assert cores_no_banco(engine_dono, a.loja.id) == (None, None)


def test_contraste_no_limite(cliente, lojas):
    """#767676 tem 4,54:1 com o branco (passa); #777777, 4,48:1 (não passa)."""
    a, _ = lojas
    assert contraste(ler_cor('#767676'), BRANCO) >= CONTRASTE_MINIMO > contraste(ler_cor('#777777'), BRANCO)
    assert salvar(cliente, a.h_admin, '#767676', '#000000').status_code == 200
    recusada = salvar(cliente, a.h_admin, '#777777', None)
    assert recusada.status_code == 422
    assert recusada.json()['erros'] == [{'campo': 'cor_topo', 'mensagem': MSG_CONTRASTE_COR}]


def test_banco_recusa_cor_fora_do_formato(engine_dono, lojas):
    a, _ = lojas
    for coluna in ('cor_site_topo', 'cor_site_destaque'):
        for valor in ('#FFFFFF', '#fff', 'red', '#12345g', '#12345 ', 'url(x)'):
            with (
                pytest.raises(IntegrityError, match=f'ck_loja_configuracoes_{coluna}'),
                engine_dono.begin() as c,
            ):
                c.execute(
                    text(f'UPDATE loja_configuracoes SET {coluna} = :v WHERE loja_id = :l'),
                    {'v': valor, 'l': a.loja.id},
                )
    assert cores_no_banco(engine_dono, a.loja.id) == (None, None)


def test_salvar_as_mesmas_cores_de_novo_nao_gera_alteracao(cliente, lojas, engine_dono):
    a, _ = lojas
    primeira = salvar(cliente, a.h_admin).json()
    segunda = salvar(cliente, a.h_admin, TOPO.upper(), DESTAQUE)
    assert segunda.status_code == 200
    assert segunda.json()['atualizado_em'] == primeira['atualizado_em']
    assert len(auditoria_das_cores(engine_dono, a.loja.id)) == 1


# --- Permissões e isolamento ---------------------------------------------------------------------


def test_permissoes_da_loja(cliente, lojas, engine_dono, sa):
    a, _ = lojas
    leitura = usuario_com(engine_dono, a.loja, {'config_loja': 'leitura'})
    assert cliente.get(URL, headers=leitura).status_code == 200
    so_leitura = salvar(cliente, leitura)
    assert so_leitura.status_code == 403
    assert so_leitura.json() == {'detail': 'Você só tem permissão de leitura aqui.'}

    # Profissional (e Recepção) não têm acesso a Configurações
    for h in (a.h_prof, a.h_recepcao):
        assert cliente.get(URL, headers=h).status_code == 403
        assert salvar(cliente, h).status_code == 403

    for metodo in ('get', 'put'):
        sem_login = cliente.request(metodo, URL, json={'cor_topo': None, 'cor_destaque': None})
        assert sem_login.status_code == 401
        assert sem_login.json() == {'detail': 'Faça login para continuar.'}
        # Token de superadmin não vale na área da loja
        assert (
            cliente.request(
                metodo, URL, json={'cor_topo': None, 'cor_destaque': None}, headers=sa[1]
            ).status_code
            == 401
        )
    assert cores_no_banco(engine_dono, a.loja.id) == (None, None)


def test_loja_so_le_e_altera_as_proprias_cores(cliente, lojas, engine_dono):
    a, b = lojas
    assert salvar(cliente, a.h_admin).status_code == 200
    assert cliente.get(URL, headers=b.h_admin).json()['cor_topo'] is None
    assert salvar(cliente, b.h_admin, '#000000', None).status_code == 200
    assert cores_no_banco(engine_dono, a.loja.id) == (TOPO, DESTAQUE)
    assert cores_no_banco(engine_dono, b.loja.id) == ('#000000', None)


# --- SUPERADMIN ----------------------------------------------------------------------------------


def test_superadmin_le_e_altera_as_cores(cliente, lojas, engine_dono, sa):
    a, b = lojas
    superadmin, h = sa
    url = URL_SA.format(a.loja.id)
    antes = cliente.get(url, headers=h)
    assert antes.status_code == 200, antes.json()
    assert antes.json()['padrao'] == PADRAO_CLINICA

    resposta = salvar(cliente, h, '#7A1F3D', None, url=url)
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert (corpo['cor_topo'], corpo['cor_destaque']) == (TOPO, None)
    assert corpo['tipo'] == 'clinica'
    assert corpo['atualizado_em'].endswith('-03:00')  # no fuso da loja, como no painel
    # GER-13: alteração do superadmin fica sem autor na tabela; quem foi fica na auditoria
    assert (corpo['atualizado_por'], corpo['atualizado_por_nome']) == (None, None)
    assert cliente.get(url, headers=h).json() == corpo

    # A loja vê a mudança; a outra loja não é afetada
    assert cliente.get(URL, headers=a.h_admin).json()['cor_topo'] == TOPO
    assert cores_no_banco(engine_dono, b.loja.id) == (None, None)
    [linha] = auditoria_das_cores(engine_dono, a.loja.id)
    assert linha['superadmin_id'] == superadmin.id
    assert linha['funcionario_id'] is None
    assert linha['origem'] == 'superadmin'
    assert linha['campos_alterados'] == ['cor_site_topo']


def test_superadmin_mesmas_validacoes(cliente, lojas, sa):
    a, _ = lojas
    url = URL_SA.format(a.loja.id)
    formato = salvar(cliente, sa[1], '#fff', None, url=url)
    assert formato.status_code == 422
    assert formato.json()['erros'] == [{'campo': 'cor_topo', 'mensagem': MSG_FORMATO_COR}]
    clara = salvar(cliente, sa[1], None, '#ffeb3b', url=url)
    assert clara.json()['erros'] == [{'campo': 'cor_destaque', 'mensagem': MSG_CONTRASTE_COR}]


def test_superadmin_loja_inexistente_ou_excluida(cliente, engine_dono, sa):
    h = sa[1]
    for metodo in ('get', 'put'):
        resposta = cliente.request(
            metodo, URL_SA.format(uuid4()), json={'cor_topo': None, 'cor_destaque': None}, headers=h
        )
        assert resposta.status_code == 404
        assert resposta.json() == {'detail': 'Loja não encontrada.'}
    loja, _ = criar_loja(engine_dono, 'loja-excluida')
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET excluido_em = now() WHERE id = :l'), {'l': loja.id})
    assert cliente.get(URL_SA.format(loja.id), headers=h).status_code == 404
    assert salvar(cliente, h, url=URL_SA.format(loja.id)).status_code == 404
    assert cliente.get(URL_SA.format('nao-e-uuid'), headers=h).status_code == 422


def test_superadmin_rotas_exigem_token_de_superadmin(cliente, lojas):
    a, _ = lojas
    url = URL_SA.format(a.loja.id)
    for h in ({}, a.h_admin):
        assert cliente.get(url, headers=h).status_code == 401
        assert salvar(cliente, h, url=url).status_code == 401


def test_padrao_segue_o_tipo_da_loja(cliente, lojas, engine_dono, sa):
    a, _ = lojas
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET tipo = 'barbearia' WHERE id = :l"), {'l': a.loja.id})
    corpo = cliente.get(URL_SA.format(a.loja.id), headers=sa[1]).json()
    assert corpo['tipo'] == 'barbearia'
    assert corpo['padrao'] == {'cor_topo': '#1f2230', 'cor_destaque': '#8f4a1c'}


def test_auditoria_da_alteracao_pela_loja(cliente, lojas, engine_dono):
    a, _ = lojas
    salvar(cliente, a.h_admin)
    [linha] = auditoria_das_cores(engine_dono, a.loja.id)
    assert linha['funcionario_id'] == a.admin.id
    assert linha['superadmin_id'] is None
    assert linha['origem'] == 'painel'
    assert sorted(linha['campos_alterados']) == ['cor_site_destaque', 'cor_site_topo']


# --- Paleta, contraste e CSS gerado ----------------------------------------------------------------


def _blocos(css: str) -> dict[str, dict[str, str]]:
    """Variáveis de cada seletor ``.tipo-*`` (``:root, .tipo-clinica`` conta como clínica)."""
    blocos: dict[str, dict[str, str]] = {}
    for seletores, corpo in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        for tipo in re.findall(r'\.tipo-(\w+)', seletores):
            blocos.setdefault(tipo, {}).update(re.findall(r'(--[\w-]+):\s*(#[0-9a-f]{6})', corpo))
    return blocos


def test_paleta_do_back_end_e_a_mesma_do_site_css():
    css = SITE_CSS.read_text(encoding='utf-8')
    claro, escuro = css.split('@media (prefers-color-scheme: dark)', 1)
    claros, escuros = _blocos(claro), _blocos(escuro.split('/* --- Base', 1)[0])
    assert set(claros) == set(escuros) == {t.value for t in TipoLoja}
    for tipo, paleta in PALETAS.items():
        assert claros[tipo.value]['--cor-topo'] == paleta.topo, tipo
        assert claros[tipo.value]['--cor-destaque'] == paleta.destaque, tipo
        assert escuros[tipo.value]['--cor-fundo'] == paleta.fundo_escuro, tipo
        assert escuros[tipo.value]['--cor-superficie'] == paleta.superficie_escura, tipo
        # A cor padrão também passaria na regra de contraste (dá para escolher a mesma cor de volta)
        assert legivel_com_branco(paleta.topo), tipo
        assert legivel_com_branco(paleta.destaque), tipo


def _variaveis(trecho: str) -> dict[str, str]:
    return dict(re.findall(r'(--[\w-]+):(#[0-9a-f]{6})', trecho))


@pytest.mark.parametrize('tipo', list(TipoLoja))
@pytest.mark.parametrize('destaque', ['#000000', '#1f5f8b', '#767676', '#b3261e', '#0b6767', '#3a45a6'])
def test_modo_escuro_clareia_o_destaque_ate_ficar_legivel(tipo, destaque):
    paleta = PALETAS[tipo]
    css = css_da_loja(tipo, None, destaque)
    claro, escuro = css.split('@media (prefers-color-scheme: dark)')
    claras = _variaveis(claro)
    assert set(claras) == {'--cor-destaque', '--cor-destaque-texto', '--cor-destaque-suave'}
    assert (claras['--cor-destaque'], claras['--cor-destaque-texto']) == (destaque, '#ffffff')
    escuras = _variaveis(escuro)
    clareado = ler_cor(escuras['--cor-destaque'])
    for fundo in (paleta.fundo_escuro, paleta.superficie_escura):
        assert contraste(clareado, ler_cor(fundo)) >= CONTRASTE_MINIMO
    assert contraste(clareado, ler_cor(escuras['--cor-destaque-texto'])) >= CONTRASTE_MINIMO
    # Fundo suave do resumo: claro no modo claro, escuro no modo escuro (texto do site legível sobre ele)
    assert contraste(ler_cor(claras['--cor-destaque-suave']), ler_cor('#16292b')) >= 7
    assert contraste(ler_cor(escuras['--cor-destaque-suave']), ler_cor('#e5eeed')) >= 7


def test_css_so_com_o_que_foi_escolhido():
    assert css_da_loja('clinica', None, None) is None
    so_topo = css_da_loja('clinica', TOPO, None)
    assert so_topo == 'body.cores-da-loja{--cor-topo:#7a1f3d}'  # vale também no modo escuro (SIT-15)
    ambos = css_da_loja('escola', TOPO, DESTAQUE)
    assert ambos.startswith('body.cores-da-loja{--cor-topo:#7a1f3d;--cor-destaque:#1f5f8b;')
    assert '@media (prefers-color-scheme: dark){body.cores-da-loja{--cor-destaque:#' in ambos


@pytest.mark.parametrize('valor', ['red', '#FFFFFF', '#fff;}', '</style><script>', 'url(x)', ''])
def test_css_ignora_valor_fora_do_formato(valor):
    """Nunca texto livre no CSS: só cores reescritas a partir do hex validado."""
    assert css_da_loja('clinica', valor, valor) is None
    assert css_da_loja('clinica', valor, DESTAQUE).startswith('body.cores-da-loja{--cor-destaque:#1f5f8b;')


# --- Site do consumidor ----------------------------------------------------------------------------


@pytest.fixture
def site(clinica, engine_dono):
    """A clínica com jornada em todos os dias, para haver horários na faixa de 31 dias."""
    lt = clinica.lt
    inserir(
        engine_dono,
        *[
            PerfilHorario(
                loja_id=lt.loja.id, perfil_id=perfil.id, dia_semana=dia, hora_inicio=ini, hora_fim=fim
            )
            for perfil in lt.perfis.values()
            for dia in range(7)
            for ini, fim in ((time(8), time(12)), (time(13), time(18)))
            if dia != 1  # a clínica já tem jornada na terça
        ],
    )
    return clinica


def _estilo(resposta) -> str | None:
    """CSS do ``<style>`` da página, conferindo o nonce com a CSP (que nunca tem unsafe-inline)."""
    csp = resposta.headers['content-security-policy']
    assert 'unsafe-inline' not in csp
    estilos = re.findall(r'<style nonce="([^"]+)">([^<]*)</style>', resposta.text)
    assert len(estilos) == resposta.text.count('<style')
    if not estilos:
        assert csp == CSP_SITE
        return None
    [(nonce, css)] = estilos
    assert csp == CSP_SITE.replace("style-src 'self'", f"style-src 'self' 'nonce-{nonce}'")
    assert len(nonce) >= 22
    return css


def _paginas_do_fluxo(cliente) -> list:
    """As quatro páginas do fluxo (serviço, horário, dados e pronto), passando por todas."""
    passo1 = cliente.get('/loja-a')
    passo2 = cliente.get(link(pagina_html(passo1), '/loja-a/agendar?servico='))
    passo3 = cliente.get(primeiro_horario(pagina_html(passo2)))
    envio = enviar(cliente, {**ocultos(pagina_html(passo3)), **CLIENTE})
    assert envio.status_code == 303
    pronto = cliente.get(envio.headers['location'])
    pagina_html(pronto)
    return [passo1, passo2, passo3, pronto]


def test_site_com_cores_usa_as_cores_em_todos_os_passos(cliente, site):
    assert salvar(cliente, site.lt.h_admin).status_code == 200
    esperado = css_da_loja('clinica', TOPO, DESTAQUE)
    nonces = set()
    for resposta in _paginas_do_fluxo(cliente):
        assert _estilo(resposta) == esperado
        assert '<body class="tipo-clinica cores-da-loja">' in resposta.text
        nonces.add(re.search(r'nonce="([^"]+)"', resposta.text).group(1))
        assert '/painel' not in resposta.text  # DIR-003
    assert len(nonces) == 4  # um nonce novo a cada resposta
    # Com uma cor só, só ela entra
    assert salvar(cliente, site.lt.h_admin, TOPO, None).status_code == 200
    assert _estilo(cliente.get('/loja-a')) == 'body.cores-da-loja{--cor-topo:#7a1f3d}'


def test_site_sem_cores_fica_como_antes(cliente, site):
    for resposta in _paginas_do_fluxo(cliente):
        assert _estilo(resposta) is None
        assert '<body class="tipo-clinica">' in resposta.text
    # Voltar ao padrão nas duas cores = igual a nunca ter escolhido
    salvar(cliente, site.lt.h_admin)
    salvar(cliente, site.lt.h_admin, None, None)
    assert _estilo(cliente.get('/loja-a')) is None


def test_cores_de_uma_loja_nao_mudam_o_site_da_outra(cliente, lojas):
    a, _ = lojas
    assert salvar(cliente, a.h_admin).status_code == 200
    outra = cliente.get('/loja-b')
    assert outra.status_code == 200
    assert _estilo(outra) is None
    assert TOPO not in outra.text
    assert _estilo(cliente.get('/loja-a')) == css_da_loja('clinica', TOPO, DESTAQUE)


def test_paginas_de_erro_do_site_nao_levam_o_estilo(cliente, lojas):
    a, _ = lojas
    salvar(cliente, a.h_admin)
    resposta = cliente.get('/loja-a/agendar/pronto', params={'c': 'adulterado'})
    assert resposta.status_code == 404
    assert '<style nonce' not in resposta.text
    assert 'nonce-' not in resposta.headers['content-security-policy']


def test_api_publica_do_site_nao_muda(cliente, lojas):
    """As cores só mudam o HTML: o JSON público (/api/site/{slug}) continua com os mesmos campos."""
    a, _ = lojas
    salvar(cliente, a.h_admin)
    corpo = cliente.get('/api/site/loja-a').json()
    assert not any('cor' in campo for campo in corpo)
