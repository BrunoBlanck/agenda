"""Conta do cliente no site, Fase A (SIT-16 a SIT-22, DIR-003): criar conta, código, senha, entrar, sair,
Minha conta e o passo 3 do agendamento com sessão.

Usa a loja de tests/clinica.py: Maria (11) 98888-1111 e João (11) 98888-2222; Limpeza (60 min, R$ 200,
Admin e Profissional, locais Sala 1 e Online com link); jornada às segundas (2030-01-07 é segunda).
Os navegadores (fixture ``navegador`` em tests/conftest.py) usam ``https://testserver``: o cookie da sessão
tem ``Secure`` fora de desenvolvimento.
"""

import html
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from sqlalchemy import text

from app.auth.tokens import (
    AUDIENCIA_CLIENTE,
    TokenInvalido,
    criar_token,
    criar_token_cliente,
    ler_token,
    ler_token_cliente,
)
from app.config import get_settings
from app.models import Agendamento, Cliente
from app.models.enums import CanalCliente, StatusAgendamento
from app.routers.site.sessao import validar_voltar
from app.services.assinatura import assinar_id
from app.services.conta_cliente import DOMINIO_TELEFONE, DOMINIO_VERIFICADO, VALIDADE_PASSO
from tests.clinica import SEGUNDA
from tests.fabricas import inserir, sessao

LOJA = '/loja-a'
MARIA_TEL, MARIA = '(11) 98888-1111', '11988881111'
NOVO_TEL, NOVO = '(21) 97777-5555', '21977775555'
SENHA = 'senha-forte-1'
MSG_ENTRAR = 'Telefone ou senha incorretos.'
MSG_TENTATIVAS_IP = 'Muitas tentativas. Peça um novo código mais tarde.'
PASTA_TEMPLATES = Path(__file__).resolve().parent.parent / 'app' / 'templates'


# --- Ajudantes ------------------------------------------------------------------------------------


def parametros(url: str) -> dict[str, str]:
    return {chave: valores[0] for chave, valores in parse_qs(urlsplit(url).query).items()}


def destino(resposta) -> str:
    assert resposta.status_code == 303, resposta.text[:500]
    return resposta.headers['location']


def hrefs(texto: str) -> list[str]:
    return [html.unescape(h) for h in re.findall(r'href="([^"]*)"', texto)]


def contar(engine, sql: str, **params) -> int:
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).scalar_one()


def zerar_limites(engine) -> None:
    with engine.begin() as conexao:
        conexao.execute(text('DELETE FROM limites.contadores'))


def ultimo_codigo(engine, digitos: str) -> tuple[str, UUID]:
    with engine.connect() as conexao:
        codigo, id_ = conexao.execute(
            text(
                'SELECT codigo, id FROM cliente_codigos WHERE telefone_digitos = :d'
                ' ORDER BY criado_em DESC, id LIMIT 1'
            ),
            {'d': digitos},
        ).one()
    return codigo, id_


def pedir_codigo(nav, telefone: str, slug: str = 'loja-a', **extra) -> str:
    resposta = nav.post(f'/{slug}/conta/criar', data={'telefone': telefone, **extra}, follow_redirects=False)
    local = destino(resposta)
    assert urlsplit(local).path == f'/{slug}/conta/codigo'
    return parametros(local)['t']


def confirmar(nav, t: str, codigo: str, **extra) -> str:
    local = destino(
        nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': codigo, **extra}, follow_redirects=False)
    )
    assert urlsplit(local).path == f'{LOJA}/conta/senha'
    return parametros(local)['v']


def definir(nav, v: str, senha: str = SENHA, repetir: str | None = None, **extra):
    dados = {'v': v, 'senha': senha, 'repetir': senha if repetir is None else repetir, **extra}
    return nav.post(f'{LOJA}/conta/senha', data=dados, follow_redirects=False)


def criar_conta(nav, engine, telefone: str = MARIA_TEL, senha: str = SENHA, **extra):
    t = pedir_codigo(nav, telefone)
    codigo, _ = ultimo_codigo(engine, re.sub(r'\D', '', telefone))
    resposta = definir(nav, confirmar(nav, t, codigo), senha, **extra)
    assert destino(resposta) == f'{LOJA}/conta'
    return resposta


def entrar(nav, telefone: str = MARIA_TEL, senha: str = SENHA, **extra):
    return nav.post(
        f'{LOJA}/conta/entrar', data={'telefone': telefone, 'senha': senha, **extra}, follow_redirects=False
    )


def minha_conta(nav, **params) -> str:
    resposta = nav.get(f'{LOJA}/conta', params=params, follow_redirects=False)
    assert resposta.status_code == 200, resposta.headers.get('location')
    return resposta.text


def agendar(
    engine, clinica, cliente_id, inicio: datetime, status=StatusAgendamento.agendado, **extra
) -> UUID:
    lt = clinica.lt
    ag = Agendamento(
        loja_id=lt.loja.id,
        cliente_id=cliente_id,
        servico_id=clinica.limpeza,
        funcionario_id=lt.prof.id,
        inicio=inicio,
        fim=inicio + timedelta(hours=1),
        status=status,
        preco=200,
        **extra,
    )
    inserir(engine, ag)
    return ag.id


def dia(dias: int, hora: int = 10) -> datetime:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return base.replace(hour=hora) + timedelta(days=dias)


# --- Criar conta (SIT-17, SIT-18) -----------------------------------------------------------------


def test_criar_conta_com_telefone_ja_cadastrado(navegador, clinica, engine_dono):
    nav = navegador()
    agendar(engine_dono, clinica, clinica.maria, dia(3))
    with engine_dono.connect() as conexao:
        antes = conexao.execute(
            text('SELECT canais, atualizado_em FROM clientes WHERE id = :id'), {'id': clinica.maria}
        ).one()

    t = pedir_codigo(nav, '11988881111')  # sem máscara
    pagina = nav.get(f'{LOJA}/conta/codigo', params={'t': t}).text
    assert 'Digite o código de 6 dígitos' in pagina
    assert 'Por enquanto, peça o código à Loja loja-a pelo telefone ou WhatsApp.' in pagina
    assert 'autocomplete="one-time-code"' in pagina
    assert 'inputmode="numeric"' in pagina
    codigo, _ = ultimo_codigo(engine_dono, MARIA)
    assert codigo not in pagina  # o código nunca aparece no site

    v = confirmar(nav, t, codigo)
    pagina = nav.get(f'{LOJA}/conta/senha', params={'v': v}).text
    assert 'Crie sua senha' in pagina
    assert 'campo-nome' not in pagina  # já tem cadastro: não pede nome
    assert 'autocomplete="new-password"' in pagina

    resposta = definir(nav, v)
    assert destino(resposta) == f'{LOJA}/conta'
    assert 'sessao_cliente=' in resposta.headers['set-cookie']
    conta = minha_conta(nav)
    assert 'Olá, Maria' in conta
    assert 'Limpeza' in conta
    assert 'Agendado' in conta
    assert contar(engine_dono, 'SELECT count(*) FROM clientes') == 2  # ninguém cadastrado
    with engine_dono.connect() as conexao:
        depois = conexao.execute(
            text('SELECT canais, atualizado_em FROM clientes WHERE id = :id'), {'id': clinica.maria}
        ).one()
    assert depois == antes  # o cadastro da loja não muda (SIT-07)
    assert (
        contar(engine_dono, 'SELECT count(*) FROM cliente_contas WHERE telefone_digitos = :d', d=MARIA) == 1
    )


def test_criar_conta_com_telefone_novo_pede_nome_e_cadastra_cliente(navegador, clinica, engine_dono):
    nav = navegador()
    t = pedir_codigo(nav, NOVO_TEL)
    v = confirmar(nav, t, ultimo_codigo(engine_dono, NOVO)[0])
    pagina = nav.get(f'{LOJA}/conta/senha', params={'v': v}).text
    assert 'campo-nome' in pagina
    assert 'campo-sobrenome' in pagina

    sem_nome = definir(nav, v)
    assert sem_nome.status_code == 200
    assert 'Campo obrigatório.' in sem_nome.text
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas') == 0

    assert destino(definir(nav, v, nome=' Carla ', sobrenome='Dias')) == f'{LOJA}/conta'
    with engine_dono.connect() as conexao:
        nome, sobrenome, telefone, canais = conexao.execute(
            text(
                "SELECT nome, sobrenome, telefone, canais::text FROM clientes WHERE telefone = '(21) 97777-5555'"
            )
        ).one()
    assert (nome, sobrenome, telefone, canais) == ('Carla', 'Dias', NOVO_TEL, '{site}')
    assert 'Olá, Carla' in minha_conta(nav)


def test_antes_do_codigo_nada_revela_se_o_telefone_tem_cadastro_ou_conta(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)  # Maria já tem conta
    zerar_limites(engine_dono)
    nav = navegador()
    paginas = []
    for telefone, digitos in ((MARIA_TEL, MARIA), (NOVO_TEL, NOVO)):
        t = pedir_codigo(nav, telefone)
        texto = nav.get(f'{LOJA}/conta/codigo', params={'t': t}).text
        paginas.append(texto.replace(t, 'T').replace(telefone, 'TEL'))
        assert (
            contar(engine_dono, 'SELECT count(*) FROM cliente_codigos WHERE telefone_digitos = :d', d=digitos)
            >= 1
        )
    assert paginas[0] == paginas[1]


def test_cinco_erros_do_mesmo_ip_param_so_esse_ip(navegador, clinica, engine_dono):
    """SIT-17: no máximo 5 erros por (código, IP); o código continua valendo para os outros IPs."""
    nav = navegador('203.0.113.70')
    t = pedir_codigo(nav, MARIA_TEL)
    certo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    errado = '000000' if certo != '000000' else '111111'
    for tentativa in range(1, 5):
        resposta = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': errado})
        assert resposta.status_code == 200
        assert 'Código incorreto ou vencido.' in resposta.text
        assert (
            contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id)
            == tentativa
        )
    quinta = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': errado})
    assert quinta.status_code == 429
    assert MSG_TENTATIVAS_IP in quinta.text
    assert 'name="codigo"' not in quinta.text
    # Desse IP, nem o código certo vale mais
    depois = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': certo}, follow_redirects=False)
    assert depois.status_code == 429
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos WHERE usado_em IS NOT NULL') == 0
    # De outro IP, o código certo ainda confirma o telefone
    outro = navegador('203.0.113.71')
    confirmar(outro, t, certo)
    assert contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id) == 5


def test_vinte_erros_no_total_esgotam_o_codigo(navegador, clinica, engine_dono):
    t = pedir_codigo(navegador('203.0.113.80'), MARIA_TEL)
    certo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    errado = '000000' if certo != '000000' else '111111'
    ultima = None
    for i in range(4):  # 4 IPs x 5 erros = 20
        nav = navegador(f'203.0.113.{81 + i}')
        for _ in range(5):
            ultima = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': errado})
    assert ultima is not None
    assert 'Peça um novo código.' in ultima.text
    assert contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id) == 20
    quinto_ip = navegador('203.0.113.90')
    esgotado = quinto_ip.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': certo}, follow_redirects=False)
    assert esgotado.status_code == 200
    assert 'Peça um novo código.' in esgotado.text
    # Esgotado não é pendente: pedir de novo gera outro código (e invalida o esgotado)
    pedir_codigo(quinto_ip, MARIA_TEL)
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 2
    assert (
        contar(
            engine_dono,
            'SELECT count(*) FROM cliente_codigos WHERE id = :id AND invalidado_em IS NOT NULL',
            id=codigo_id,
        )
        == 1
    )


def test_pedir_codigo_com_um_pendente_devolve_o_mesmo(navegador, clinica, engine_dono):
    """SIT-17: com um código pendente válido, pedir de novo não gera outro nem invalida o atual."""
    nav = navegador()
    t1 = pedir_codigo(nav, MARIA_TEL)
    codigo1, id1 = ultimo_codigo(engine_dono, MARIA)
    zerar_limites(engine_dono)
    t2 = pedir_codigo(nav, MARIA_TEL)
    assert ultimo_codigo(engine_dono, MARIA) == (codigo1, id1)
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 1
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos WHERE invalidado_em IS NOT NULL') == 0
    assert nav.get(f'{LOJA}/conta/codigo', params={'t': t2}).status_code == 200
    confirmar(nav, t1, codigo1)  # o primeiro passo continua valendo


def test_limite_por_telefone_conta_so_codigos_gerados(navegador, clinica, engine_dono, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_codigos_por_telefone', 2)
    monkeypatch.setattr(get_settings(), 'limite_codigo_intervalo', 1)

    def pedir(ip: str):
        return navegador(ip).post(f'{LOJA}/conta/criar', data={'telefone': MARIA_TEL}, follow_redirects=False)

    def esgotar_o_pendente() -> None:
        with engine_dono.begin() as conexao:
            conexao.execute(text('UPDATE cliente_codigos SET tentativas = 20 WHERE invalidado_em IS NULL'))

    for i in range(5):  # com um pendente, os pedidos não geram código nem contam no limite do telefone
        assert pedir(f'203.0.113.{100 + i}').status_code == 303
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 1
    esgotar_o_pendente()
    assert pedir('203.0.113.110').status_code == 303  # o segundo gerado
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 2
    esgotar_o_pendente()
    excesso = pedir('203.0.113.111')
    assert excesso.status_code == 429
    assert 'Muitos pedidos de código para este telefone.' in excesso.text
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 2


def test_codigo_mal_formado_nao_conta_tentativa(navegador, clinica, engine_dono):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    _, codigo_id = ultimo_codigo(engine_dono, MARIA)
    for digitado in ('', '12345', 'abcdef', '1234567', '9' * 50):
        resposta = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': digitado})
        assert resposta.status_code == 200
        assert 'Digite os 6 dígitos do código.' in resposta.text
    assert contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id) == 0


def test_codigo_vencido_pede_outro(navegador, clinica, engine_dono):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    codigo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    with engine_dono.begin() as conexao:
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text(
                "UPDATE cliente_codigos SET criado_em = now() - interval '1 hour',"
                " expira_em = now() - interval '1 minute' WHERE id = :id"
            ),
            {'id': codigo_id},
        )
    assert 'Peça um novo código.' in nav.get(f'{LOJA}/conta/codigo', params={'t': t}).text
    resposta = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': codigo}, follow_redirects=False)
    assert resposta.status_code == 200
    assert 'Peça um novo código.' in resposta.text


def test_pedir_novo_codigo_invalida_o_telefone_ja_confirmado(navegador, clinica, engine_dono):
    """Código confirmado e senha ainda não definida: um novo pedido derruba o passo da senha."""
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    v = confirmar(nav, t, ultimo_codigo(engine_dono, MARIA)[0])
    zerar_limites(engine_dono)
    pedir_codigo(nav, MARIA_TEL)
    assert destino(definir(nav, v)) == f'{LOJA}/conta/criar'
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas') == 0


def test_limite_de_um_codigo_por_minuto_por_telefone(navegador, clinica, engine_dono):
    nav = navegador()
    pedir_codigo(nav, MARIA_TEL)
    resposta = nav.post(f'{LOJA}/conta/criar', data={'telefone': MARIA_TEL}, follow_redirects=False)
    assert resposta.status_code == 429
    assert 'Muitos pedidos de código para este telefone.' in resposta.text
    assert 'value="(11) 98888-1111"' in resposta.text  # o formulário volta preenchido
    assert int(resposta.headers['retry-after']) > 0
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 1
    pedir_codigo(nav, NOVO_TEL)  # outro telefone continua podendo


def test_limite_de_codigos_por_ip(navegador, clinica, engine_dono, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_codigos_por_ip', 2)
    nav = navegador('203.0.113.20')
    pedir_codigo(nav, '(11) 91111-0001')
    pedir_codigo(nav, '(11) 91111-0002')
    assert nav.post(f'{LOJA}/conta/criar', data={'telefone': '(11) 91111-0003'}).status_code == 429
    pedir_codigo(navegador('203.0.113.21'), '(11) 91111-0003')  # outro IP não é afetado


def test_telefone_invalido_no_passo_1(navegador, clinica, engine_dono):
    nav = navegador()
    for telefone in ('', '123', '(01) 98888-1111', 'abc', '1' * 40):
        resposta = nav.post(f'{LOJA}/conta/criar', data={'telefone': telefone})
        assert resposta.status_code == 200
        assert 'Informe o telefone com DDD' in resposta.text
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 0


# --- Identificadores dos passos (t e v) -----------------------------------------------------------


def test_t_adulterado_vencido_de_outro_dominio_ou_de_outra_loja_volta_ao_passo_1(
    navegador, clinica, lojas, engine_dono
):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    codigo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    loja_a, loja_b = lojas[0].loja.id, lojas[1].loja.id
    adulterado = t[:-1] + ('A' if t[-1] != 'A' else 'B')
    vencido = assinar_id(
        DOMINIO_TELEFONE, loja_a, codigo_id, VALIDADE_PASSO, agora=datetime.now(UTC) - timedelta(hours=1)
    )
    outra_loja = assinar_id(DOMINIO_TELEFONE, loja_b, codigo_id, VALIDADE_PASSO)
    outro_dominio = assinar_id(DOMINIO_VERIFICADO, loja_a, codigo_id, VALIDADE_PASSO)
    for invalido in (
        adulterado,
        vencido,
        outra_loja,
        outro_dominio,
        '',
        'x' * 500,
        f'{uuid4().hex}ffffffff.abc',
    ):
        assert destino(nav.get(f'{LOJA}/conta/codigo', params={'t': invalido}, follow_redirects=False)) == (
            f'{LOJA}/conta/criar'
        )
        resposta = nav.post(
            f'{LOJA}/conta/codigo', data={'t': invalido, 'codigo': codigo}, follow_redirects=False
        )
        assert destino(resposta) == f'{LOJA}/conta/criar'
    # O t certo, mas noutra loja
    assert (
        destino(nav.get('/loja-b/conta/codigo', params={'t': t}, follow_redirects=False))
        == '/loja-b/conta/criar'
    )
    assert contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id) == 0


def test_v_adulterado_vencido_reusado_ou_sem_codigo_confirmado(navegador, clinica, lojas, engine_dono):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    codigo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    loja_a = lojas[0].loja.id
    # Assinado certo, mas o código ainda não foi confirmado: não vale
    antes = assinar_id(DOMINIO_VERIFICADO, loja_a, codigo_id, VALIDADE_PASSO)
    assert destino(definir(nav, antes)) == f'{LOJA}/conta/criar'
    v = confirmar(nav, t, codigo)
    vencido = assinar_id(
        DOMINIO_VERIFICADO, loja_a, codigo_id, VALIDADE_PASSO, agora=datetime.now(UTC) - timedelta(hours=1)
    )
    for invalido in (v[:-1] + ('A' if v[-1] != 'A' else 'B'), vencido, t, ''):
        assert destino(nav.get(f'{LOJA}/conta/senha', params={'v': invalido}, follow_redirects=False)) == (
            f'{LOJA}/conta/criar'
        )
        assert destino(definir(nav, invalido)) == f'{LOJA}/conta/criar'
    assert destino(definir(nav, v)) == f'{LOJA}/conta'
    # Uso único
    assert destino(definir(navegador(), v, 'outra-senha-2')) == f'{LOJA}/conta/criar'
    assert (
        destino(nav.get(f'{LOJA}/conta/senha', params={'v': v}, follow_redirects=False))
        == f'{LOJA}/conta/criar'
    )
    assert contar(engine_dono, 'SELECT sessao_versao FROM cliente_contas') == 1


def test_regras_da_senha(navegador, clinica, engine_dono):
    nav = navegador()
    v = confirmar(nav, pedir_codigo(nav, MARIA_TEL), ultimo_codigo(engine_dono, MARIA)[0])
    for senha, repetir, mensagem in (
        ('curta', 'curta', 'A senha precisa ter de 8 a 128 caracteres.'),
        ('x' * 129, 'x' * 129, 'A senha precisa ter de 8 a 128 caracteres.'),
        ('11988881111', '11988881111', 'A senha não pode ser o seu telefone.'),
        ('988881111', '988881111', 'A senha não pode ser o seu telefone.'),
        ('(11) 98888-1111', '(11) 98888-1111', 'A senha não pode ser o seu telefone.'),
        ('senha-forte-1', 'senha-forte-2', 'As senhas não são iguais.'),
    ):
        resposta = definir(nav, v, senha, repetir)
        assert resposta.status_code == 200
        assert mensagem in resposta.text
        assert f'value="{senha}"' not in resposta.text  # a senha nunca volta na página
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas') == 0
    assert destino(definir(nav, v, 'x' * 128)) == f'{LOJA}/conta'


# --- Entrar e sair (SIT-19, SIT-20) ---------------------------------------------------------------


def test_entrar_com_ou_sem_mascara_cookie_com_as_flags_e_sair(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    for telefone in ('11988881111', '(11) 98888-1111', '11 98888 1111'):
        nav = navegador()
        resposta = entrar(nav, telefone)
        assert destino(resposta) == f'{LOJA}/conta'
        cookie = resposta.headers['set-cookie']
        assert cookie.startswith('sessao_cliente=')
        for atributo in ('HttpOnly', 'Path=/loja-a', 'SameSite=lax', 'Secure', f'Max-Age={30 * 24 * 3600}'):
            assert atributo in cookie, atributo
        assert 'Olá, Maria' in minha_conta(nav)

    saida = nav.post(f'{LOJA}/conta/sair', follow_redirects=False)
    assert destino(saida) == LOJA
    assert 'sessao_cliente=""' in saida.headers['set-cookie'] or 'Max-Age=0' in saida.headers['set-cookie']
    assert urlsplit(destino(nav.get(f'{LOJA}/conta', follow_redirects=False))).path == f'{LOJA}/conta/entrar'


def test_cookie_sem_secure_em_desenvolvimento(navegador, clinica, engine_dono, monkeypatch):
    criar_conta(navegador(), engine_dono)
    monkeypatch.setattr(get_settings(), 'ambiente', 'desenvolvimento')
    cookie = entrar(navegador()).headers['set-cookie']
    assert 'HttpOnly' in cookie
    assert 'Secure' not in cookie


def test_senha_errada_e_telefone_sem_conta_tem_a_mesma_resposta(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    nav = navegador()
    errada = entrar(nav, MARIA_TEL, 'senha-errada')
    sem_conta = entrar(nav, '(11) 98888-2222', 'senha-errada')  # João: cliente sem conta
    desconhecido = entrar(nav, NOVO_TEL, 'senha-errada')
    for resposta in (errada, sem_conta, desconhecido):
        assert resposta.status_code == 200
        assert MSG_ENTRAR in resposta.text
        assert 'set-cookie' not in resposta.headers
        assert 'senha-errada' not in resposta.text
    assert errada.text.replace(MARIA_TEL, 'T') == desconhecido.text.replace(NOVO_TEL, 'T')


def test_entrar_com_campos_vazios_ou_telefone_invalido(navegador, clinica):
    nav = navegador()
    resposta = nav.post(f'{LOJA}/conta/entrar', data={})
    assert resposta.status_code == 200
    assert 'Informe o telefone com DDD' in resposta.text
    assert 'Informe a senha.' in resposta.text


def test_bloqueio_progressivo_por_telefone_e_ip(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    nav = navegador('203.0.113.30')
    for _ in range(get_settings().login_falhas_para_bloquear):
        assert MSG_ENTRAR in entrar(nav, MARIA_TEL, 'senha-errada').text
    bloqueado = entrar(nav, MARIA_TEL, SENHA)  # nem a senha certa entra por este IP
    assert bloqueado.status_code == 429
    assert 'Muitas tentativas. Aguarde' in bloqueado.text
    assert int(bloqueado.headers['retry-after']) > 0
    assert 'login' not in bloqueado.text.lower()
    # Outro IP (o dono, em outro lugar) entra normalmente
    assert destino(entrar(navegador('203.0.113.31'))) == f'{LOJA}/conta'


def test_limite_de_tentativas_por_ip(navegador, clinica, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_login_por_ip', 2)
    nav = navegador('203.0.113.40')
    entrar(nav, '(11) 91111-0001', 'x' * 8)
    entrar(nav, '(11) 91111-0002', 'x' * 8)
    resposta = entrar(nav, '(11) 91111-0003', 'x' * 8)
    assert resposta.status_code == 429
    assert 'value="(11) 91111-0003"' in resposta.text


def test_ja_na_conta_entrar_leva_a_minha_conta(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    assert destino(nav.get(f'{LOJA}/conta/entrar', follow_redirects=False)) == f'{LOJA}/conta'


def test_trocar_a_senha_derruba_as_outras_sessoes(navegador, clinica, engine_dono):
    celular = navegador()
    criar_conta(celular, engine_dono)
    assert 'Olá, Maria' in minha_conta(celular)
    zerar_limites(engine_dono)
    computador = navegador()  # "Esqueci minha senha"
    t = pedir_codigo(computador, MARIA_TEL)
    v = confirmar(computador, t, ultimo_codigo(engine_dono, MARIA)[0])
    assert 'Nova senha' in computador.get(f'{LOJA}/conta/senha', params={'v': v}).text
    assert destino(definir(computador, v, 'senha-nova-22')) == f'{LOJA}/conta'
    assert contar(engine_dono, 'SELECT sessao_versao FROM cliente_contas') == 2

    resposta = celular.get(f'{LOJA}/conta', follow_redirects=False)
    assert parametros(destino(resposta)) == {'voltar': f'{LOJA}/conta', 'aviso': 'sessao'}
    assert (
        'sessao_cliente=""' in resposta.headers['set-cookie'] or 'Max-Age=0' in resposta.headers['set-cookie']
    )
    assert 'Olá, Maria' in minha_conta(computador)
    assert MSG_ENTRAR in entrar(navegador(), MARIA_TEL, SENHA).text
    assert destino(entrar(navegador(), MARIA_TEL, 'senha-nova-22')) == f'{LOJA}/conta'


def test_remover_acesso_pelo_painel_derruba_a_sessao(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    resposta = nav.delete(f'/api/loja/clientes/{clinica.maria}/conta-site', headers=clinica.lt.h_admin)
    assert resposta.status_code == 204
    assert urlsplit(destino(nav.get(f'{LOJA}/conta', follow_redirects=False))).path == f'{LOJA}/conta/entrar'
    assert MSG_ENTRAR in entrar(navegador()).text
    # Pode criar a conta de novo: é outra linha
    zerar_limites(engine_dono)
    criar_conta(navegador(), engine_dono)
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas') == 2
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas WHERE excluido_em IS NULL') == 1


def test_cookie_de_uma_loja_nao_vale_em_outra(navegador, clinica, lojas, engine_dono):
    nav = navegador()
    token = criar_conta(nav, engine_dono).headers['set-cookie'].split(';')[0].split('=', 1)[1]
    outra = navegador()
    resposta = outra.get(
        '/loja-b/conta', headers={'Cookie': f'sessao_cliente={token}'}, follow_redirects=False
    )
    assert urlsplit(destino(resposta)).path == '/loja-b/conta/entrar'
    pagina = outra.get('/loja-b', headers={'Cookie': f'sessao_cliente={token}'}).text
    assert '>Entrar</a>' in pagina.replace('\n', '') or 'Entrar</a>' in pagina
    assert 'Minha conta' not in pagina


def test_token_do_cliente_nunca_vale_no_painel_nem_no_superadmin(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    token = nav.cookies.get('sessao_cliente')
    assert token
    for caminho in ('/api/loja/clientes', '/api/loja/eu', '/api/superadmin/lojas'):
        resposta = nav.get(caminho, headers={'Authorization': f'Bearer {token}'})
        assert resposta.status_code == 401, caminho
    with pytest.raises(TokenInvalido):
        ler_token(token)


def test_token_do_painel_nunca_vale_como_sessao_do_site(navegador, clinica, engine_dono):
    lt = clinica.lt
    token_painel, _ = criar_token(lt.admin.id, 'funcionario', lt.loja.id)
    token_superadmin, _ = criar_token(uuid4(), 'superadmin')
    nav = navegador()
    for token in (token_painel, token_superadmin):
        with pytest.raises(TokenInvalido):
            ler_token_cliente(token)
        resposta = nav.get(
            f'{LOJA}/conta', headers={'Cookie': f'sessao_cliente={token}'}, follow_redirects=False
        )
        assert parametros(destino(resposta))['aviso'] == 'sessao'


def test_token_do_cliente_forjado_com_o_segredo_do_painel_nao_vale(clinica, engine_dono):
    agora = datetime.now(UTC)
    dados = {
        'sub': str(uuid4()),
        'tipo': 'cliente',
        'loja_id': str(clinica.lt.loja.id),
        'ver': 1,
        'aud': AUDIENCIA_CLIENTE,
        'iat': agora,
        'exp': agora + timedelta(days=1),
    }
    forjado = jwt.encode(dados, get_settings().jwt_secret.get_secret_value(), algorithm='HS256')
    with pytest.raises(TokenInvalido):
        ler_token_cliente(forjado)
    sem_assinatura = jwt.encode(dados, None, algorithm='none')
    with pytest.raises(TokenInvalido):
        ler_token_cliente(sem_assinatura)
    valido, _ = criar_token_cliente(uuid4(), clinica.lt.loja.id, 1)
    assert ler_token_cliente(valido).versao == 1


# --- SIT-16: a conta segue o telefone -------------------------------------------------------------


def test_dois_clientes_com_o_mesmo_telefone_aparecem_na_mesma_conta(navegador, clinica, engine_dono):
    lt = clinica.lt
    outra = inserir(
        engine_dono, Cliente(loja_id=lt.loja.id, nome='Mariana', sobrenome='Souza', telefone=MARIA_TEL)
    )
    agendar(engine_dono, clinica, clinica.maria, dia(2))
    agendar(engine_dono, clinica, outra.id, dia(4), status=StatusAgendamento.confirmado)
    agendar(engine_dono, clinica, clinica.joao, dia(6))  # outro telefone
    nav = navegador()
    criar_conta(nav, engine_dono)
    pagina = minha_conta(nav)
    assert 'Olá, Maria' in pagina  # o cadastro mais antigo
    assert pagina.count('class="meu-agendamento"') == 2
    assert 'Agendado' in pagina
    assert 'Confirmado' in pagina


def test_trocar_o_telefone_no_painel_tira_os_agendamentos_da_conta(navegador, clinica, engine_dono):
    agendar(engine_dono, clinica, clinica.maria, dia(2))
    nav = navegador()
    criar_conta(nav, engine_dono)
    assert minha_conta(nav).count('class="meu-agendamento"') == 1
    resposta = nav.put(
        f'/api/loja/clientes/{clinica.maria}',
        json={'nome': 'Maria', 'sobrenome': 'Oliveira', 'telefone': '(11) 97777-0000'},
        headers=clinica.lt.h_admin,
    )
    assert resposta.status_code == 200
    pagina = minha_conta(nav)  # a conta continua, mas sem cliente com o telefone
    assert 'class="meu-agendamento"' not in pagina
    assert 'Você não tem horários marcados.' in pagina
    assert 'Olá</h2>' in pagina


# --- SIT-21: Minha conta --------------------------------------------------------------------------


def test_proximos_e_historico(navegador, clinica, engine_dono):
    proximo = agendar(
        engine_dono,
        clinica,
        clinica.maria,
        dia(5),
        status=StatusAgendamento.pendente,
        local_id=clinica.online,
    )
    agendar(engine_dono, clinica, clinica.maria, dia(1), status=StatusAgendamento.confirmado)
    agendar(
        engine_dono,
        clinica,
        clinica.maria,
        dia(8),
        status=StatusAgendamento.cancelado,
        motivo_cancelamento='Anotação interna da recepção',
    )
    agendar(engine_dono, clinica, clinica.maria, dia(-3), status=StatusAgendamento.concluido)
    agendar(engine_dono, clinica, clinica.maria, dia(-2), status=StatusAgendamento.agendado)  # já passou
    excluido = agendar(engine_dono, clinica, clinica.maria, dia(9))
    with sessao(engine_dono) as db:
        db.get(Agendamento, excluido).excluido_em = datetime.now(UTC)
    nav = navegador()
    criar_conta(nav, engine_dono)
    pagina = minha_conta(nav)
    proximos, historico = pagina.split('id="historico"')
    assert proximos.count('class="meu-agendamento"') == 2
    assert historico.count('class="meu-agendamento"') == 3
    assert proximos.index('Confirmado') < proximos.index('Aguardando confirmação')  # início crescente
    assert 'Cancelado' in historico
    assert 'Concluído' in historico
    assert historico.index('Cancelado') < historico.index('Concluído')  # início decrescente
    assert 'Anotação interna' not in pagina  # o motivo da loja não aparece
    assert 'Online' in proximos  # nome do local
    assert 'meet.example.com' not in pagina  # nunca o link
    assert 'R$ 200,00' in pagina
    assert 'Profissional' in pagina
    assert f'{LOJA}/conta/agendamentos/{proximo}/remarcar' in hrefs(proximos)  # Fase B: SIT-23/24
    assert f'{LOJA}/conta/agendamentos/' not in historico


def test_minha_conta_vazia(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono, NOVO_TEL, nome='Carla', sobrenome='Dias')
    pagina = minha_conta(nav)
    assert 'Você não tem horários marcados.' in pagina
    assert 'Nenhum agendamento anterior.' in pagina
    assert f'href="{LOJA}"' in pagina  # Agendar novo horário
    assert f'action="{LOJA}/conta/sair"' in pagina


def test_historico_paginado(navegador, clinica, engine_dono):
    for i in range(25):
        agendar(engine_dono, clinica, clinica.maria, dia(-1 - i), status=StatusAgendamento.concluido)
    nav = navegador()
    criar_conta(nav, engine_dono)
    primeira = minha_conta(nav)
    assert primeira.count('class="meu-agendamento"') == 20
    assert 'Página 1 de 2' in primeira
    assert f'{LOJA}/conta?pagina=2#historico' in hrefs(primeira)
    segunda = minha_conta(nav, pagina='2')
    assert segunda.count('class="meu-agendamento"') == 5
    assert f'{LOJA}/conta?pagina=1#historico' in hrefs(segunda)
    for estranho in ('abc', '-1', '0', '99999999999', ''):
        assert minha_conta(nav, pagina=estranho).count('class="meu-agendamento"') == 20
    alem = minha_conta(nav, pagina='7')
    assert 'Não há agendamentos nesta página.' in alem


def test_minha_conta_sem_sessao_vai_para_entrar(navegador, clinica):
    resposta = navegador().get(f'{LOJA}/conta', follow_redirects=False)
    assert destino(resposta) == f'{LOJA}/conta/entrar?voltar=%2Floja-a%2Fconta'


# --- SIT-22: agendar com a conta ------------------------------------------------------------------


def _escolha(clinica, hora: str = '08:00') -> dict[str, str]:
    return {
        'servico': clinica.limpeza,
        'profissional': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T{hora}-03:00',
        'local': '',
    }


def test_pedido_na_conta_so_pede_observacoes(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    escolha = _escolha(clinica)
    passo3 = nav.get(f'{LOJA}/agendar/dados', params={k: v for k, v in escolha.items() if v}).text
    assert 'Agendando como <strong>Maria</strong>' in passo3
    assert 'campo-nome' not in passo3
    assert 'campo-telefone' not in passo3
    assert 'campo-email' not in passo3
    assert 'campo-observacoes' in passo3
    assert '<input type="hidden" name="conta" value="1">' in passo3
    assert 'Já tem conta?' not in passo3

    formulario = {**escolha, 'conta': '1', 'observacoes': 'Pelo site, logada'}
    resposta = nav.post(f'{LOJA}/agendar', data=formulario, follow_redirects=False)
    assert urlsplit(destino(resposta)).path == f'{LOJA}/agendar/pronto'
    with engine_dono.connect() as conexao:
        cliente_id, observacoes, origem, situacao = conexao.execute(
            text('SELECT cliente_id, observacoes, origem::text, status::text FROM agendamentos')
        ).one()
    assert (str(cliente_id), observacoes, origem, situacao) == (
        clinica.maria,
        'Pelo site, logada',
        'site',
        'pendente',
    )
    assert contar(engine_dono, 'SELECT count(*) FROM clientes') == 2
    pronto = nav.get(destino(resposta)).text
    assert 'Ver meus agendamentos' in pronto
    assert f'{LOJA}/conta' in hrefs(pronto)
    assert 'Crie sua senha' not in pronto

    # O mesmo envio de novo (duplo clique): a confirmação do mesmo pedido (LOG-07)
    repetido = nav.post(f'{LOJA}/agendar', data=formulario, follow_redirects=False)
    assert urlsplit(destino(repetido)).path == f'{LOJA}/agendar/pronto'
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1
    assert 'Aguardando confirmação' in minha_conta(nav)


def test_pedido_na_conta_ignora_nome_e_telefone_enviados(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono)
    formulario = {
        **_escolha(clinica),
        'conta': '1',
        'nome': 'Outra',
        'sobrenome': 'Pessoa',
        'telefone': NOVO_TEL,
    }
    assert urlsplit(destino(nav.post(f'{LOJA}/agendar', data=formulario, follow_redirects=False))).path == (
        f'{LOJA}/agendar/pronto'
    )
    assert contar(engine_dono, 'SELECT count(*) FROM clientes') == 2
    assert (
        contar(engine_dono, 'SELECT count(*) FROM agendamentos WHERE cliente_id = :id', id=clinica.maria) == 1
    )


def test_pedido_na_conta_respeita_o_limite_de_pendentes(navegador, clinica, engine_dono, monkeypatch):
    monkeypatch.setattr(get_settings(), 'site_pendentes_por_telefone', 1)
    agendar(engine_dono, clinica, clinica.maria, dia(3), status=StatusAgendamento.pendente)
    nav = navegador()
    criar_conta(nav, engine_dono)
    resposta = nav.post(f'{LOJA}/agendar', data={**_escolha(clinica), 'conta': '1'}, follow_redirects=False)
    assert resposta.status_code == 409
    assert 'Já há pedidos deste telefone aguardando a confirmação da loja.' in resposta.text
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def test_pedido_na_conta_respeita_o_limite_de_pedidos_por_ip(navegador, clinica, engine_dono, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_site_pedidos_por_ip', 1)
    nav = navegador()
    criar_conta(nav, engine_dono)
    nav.post(f'{LOJA}/agendar', data={**_escolha(clinica), 'conta': '1'}, follow_redirects=False)
    excesso = nav.post(
        f'{LOJA}/agendar', data={**_escolha(clinica, '10:00'), 'conta': '1'}, follow_redirects=False
    )
    assert excesso.status_code == 429
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 1


def test_sessao_vencida_no_envio_volta_ao_passo_3_com_aviso(navegador, clinica, engine_dono):
    nav = navegador()  # sem sessão nenhuma
    resposta = nav.post(
        f'{LOJA}/agendar',
        data={**_escolha(clinica), 'conta': '1', 'observacoes': 'Quero manhã'},
        follow_redirects=False,
    )
    assert resposta.status_code == 200
    assert 'Sua sessão terminou.' in resposta.text
    assert 'campo-nome' in resposta.text
    assert 'campo-telefone' in resposta.text
    assert 'Quero manhã' in resposta.text
    assert 'name="conta"' not in resposta.text
    assert contar(engine_dono, 'SELECT count(*) FROM agendamentos') == 0


def test_conta_cujo_telefone_nao_tem_mais_cliente_pede_nome(navegador, clinica, engine_dono):
    nav = navegador()
    criar_conta(nav, engine_dono, NOVO_TEL, nome='Carla', sobrenome='Dias')
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE clientes SET excluido_em = now() WHERE telefone = '(21) 97777-5555'"))
    escolha = _escolha(clinica)
    passo3 = nav.get(f'{LOJA}/agendar/dados', params={k: v for k, v in escolha.items() if v}).text
    assert 'campo-nome' in passo3
    assert 'campo-telefone' not in passo3
    sem_nome = nav.post(f'{LOJA}/agendar', data={**escolha, 'conta': '1'}, follow_redirects=False)
    assert sem_nome.status_code == 200
    assert 'Campo obrigatório.' in sem_nome.text
    ok = nav.post(
        f'{LOJA}/agendar',
        data={**escolha, 'conta': '1', 'nome': 'Carla', 'sobrenome': 'Dias'},
        follow_redirects=False,
    )
    assert urlsplit(destino(ok)).path == f'{LOJA}/agendar/pronto'
    assert (
        contar(
            engine_dono,
            "SELECT count(*) FROM clientes WHERE telefone = '(21) 97777-5555' AND excluido_em IS NULL",
        )
        == 1
    )


def test_sem_conta_ja_tem_conta_volta_ao_mesmo_passo_3(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    nav = navegador()
    escolha = {k: v for k, v in _escolha(clinica).items() if v}
    passo3 = nav.get(f'{LOJA}/agendar/dados', params=escolha).text
    assert 'Já tem conta?' in passo3
    assert 'campo-telefone' in passo3  # o fluxo de hoje continua igual
    entrar_url = next(h for h in hrefs(passo3) if h.startswith(f'{LOJA}/conta/entrar?'))
    voltar = parametros(entrar_url)['voltar']
    assert urlsplit(voltar).path == f'{LOJA}/agendar/dados'
    assert parametros(voltar) == escolha
    pagina_entrar = nav.get(entrar_url).text
    assert f'name="voltar" value="{html.escape(voltar)}"' in pagina_entrar
    assert destino(entrar(nav, voltar=voltar)) == voltar
    assert 'Agendando como <strong>Maria</strong>' in nav.get(voltar).text


def test_pronto_sem_conta_convida_a_criar_a_senha(navegador, clinica, engine_dono):
    nav = navegador()
    dados = {**_escolha(clinica), 'nome': 'Ana', 'sobrenome': 'Souza', 'telefone': '(11) 97777-6666'}
    pronto = nav.get(destino(nav.post(f'{LOJA}/agendar', data=dados, follow_redirects=False))).text
    assert 'Crie sua senha para acompanhar seus agendamentos.' in pronto
    assert f'{LOJA}/conta/criar' in hrefs(pronto)


@pytest.mark.parametrize(
    ('voltar', 'esperado'),
    [
        ('/loja-a', '/loja-a'),
        ('/loja-a/agendar?servico=x&dia=2030-01-07', '/loja-a/agendar?servico=x&dia=2030-01-07'),
        (
            '/loja-a/agendar/dados?inicio=2030-01-07T08%3A00-03%3A00',
            '/loja-a/agendar/dados?inicio=2030-01-07T08%3A00-03%3A00',
        ),
        ('/loja-a/conta', '/loja-a/conta'),
        (f'/loja-a/conta/agendamentos/{uuid4()}/cancelar', None),
        ('//evil.example/loja-a', '/loja-a/conta'),
        ('https://evil.example/loja-a', '/loja-a/conta'),
        ('/loja-a/../evil', '/loja-a/conta'),
        ('/loja-a//evil.example', '/loja-a/conta'),
        ('/loja-a\\evil.example', '/loja-a/conta'),
        ('/loja-ab/conta', '/loja-a/conta'),
        ('/loja-b/conta', '/loja-a/conta'),
        ('/loja-a/conta/entrar', '/loja-a/conta'),
        ('/loja-a/conta/criar', '/loja-a/conta'),
        ('/loja-a/painel', '/loja-a/conta'),
        ('/loja-a/agendar#x', '/loja-a/conta'),
        ('/loja-a/agendar?x=<script>', '/loja-a/conta'),
        ('/loja-a/agendar?x=1\r\nSet-Cookie: a=b', '/loja-a/conta'),
        ('javascript:alert(1)', '/loja-a/conta'),
        ('/loja-a/agendar?' + 'a' * 600, '/loja-a/conta'),
        ('', '/loja-a/conta'),
    ],
)
def test_voltar_aceita_so_paginas_do_site(navegador, clinica, engine_dono, voltar, esperado):
    esperado = voltar if esperado is None else esperado
    assert validar_voltar('loja-a', voltar) == esperado
    criar_conta(navegador(), engine_dono)
    assert destino(entrar(navegador(), voltar=voltar)) == esperado


# --- Segurança das páginas: origem, DIR-003, cabeçalhos, loja indisponível ------------------------


@pytest.mark.parametrize('caminho', ['entrar', 'sair', 'criar', 'codigo', 'senha'])
@pytest.mark.parametrize(
    'cabecalhos',
    [
        {'Origin': 'https://outro-site.example'},
        {'Origin': 'null'},
        {'Referer': 'https://outro-site.example/x'},
    ],
)
def test_post_de_outro_site_e_recusado(navegador, clinica, engine_dono, caminho, cabecalhos):
    nav = navegador()
    dados = {'telefone': MARIA_TEL, 'senha': SENHA, 'repetir': SENHA, 't': 'x', 'v': 'x', 'codigo': '123456'}
    resposta = nav.post(f'{LOJA}/conta/{caminho}', data=dados, headers=cabecalhos, follow_redirects=False)
    assert resposta.status_code == 403
    assert 'set-cookie' not in resposta.headers
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 0


def test_post_da_propria_origem_e_aceito(navegador, clinica):
    cabecalhos = {'Origin': 'https://testserver', 'Referer': 'https://testserver/loja-a/conta/criar'}
    resposta = navegador().post(
        f'{LOJA}/conta/criar', data={'telefone': MARIA_TEL}, headers=cabecalhos, follow_redirects=False
    )
    assert resposta.status_code == 303


def test_nenhum_template_fala_em_painel_superadmin_ou_login():
    """DIR-003: o site nunca leva ao painel; a conta do cliente usa "Entrar" e "Minha conta"."""
    for arquivo in PASTA_TEMPLATES.rglob('*.html'):
        conteudo = arquivo.read_text(encoding='utf-8')
        assert re.search(r'painel|superadmin|login', conteudo, re.IGNORECASE) is None, arquivo.name


def test_paginas_da_conta_noindex_sem_painel_e_com_cabecalhos(navegador, clinica, engine_dono):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    v = confirmar(nav, t, ultimo_codigo(engine_dono, MARIA)[0])
    paginas = [
        nav.get(f'{LOJA}/conta/entrar'),
        nav.get(f'{LOJA}/conta/criar'),
        nav.get(f'{LOJA}/conta/codigo', params={'t': t}),
        nav.get(f'{LOJA}/conta/senha', params={'v': v}),
    ]
    definir(nav, v)
    paginas.append(nav.get(f'{LOJA}/conta'))
    for resposta in paginas:
        assert resposta.status_code == 200
        assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
        assert resposta.headers['cache-control'] == 'no-store'
        assert resposta.headers['x-frame-options'] == 'DENY'
        assert "form-action 'self'" in resposta.headers['content-security-policy']
        assert '<meta name="robots" content="noindex">' in resposta.text
        assert '/painel' not in resposta.text
        assert 'superadmin' not in resposta.text.lower()
        assert 'login' not in resposta.text.lower()


def test_cabecalho_do_site_mostra_entrar_ou_minha_conta(navegador, clinica, engine_dono):
    nav = navegador()
    inicio = nav.get(LOJA).text
    assert any(h.startswith(f'{LOJA}/conta/entrar') for h in hrefs(inicio))
    assert 'Minha conta' not in inicio
    criar_conta(nav, engine_dono)
    for caminho in (LOJA, f'{LOJA}/agendar?servico={clinica.limpeza}', f'{LOJA}/conta'):
        pagina = nav.get(caminho).text
        assert 'Minha conta</a>' in pagina, caminho
        assert f'{LOJA}/conta' in hrefs(pagina)


@pytest.mark.parametrize('situacao', ['suspensa', 'cancelada'])
def test_loja_indisponivel_responde_404_nas_paginas_da_conta(navegador, clinica, engine_dono, situacao):
    with engine_dono.begin() as conexao:
        conexao.execute(text(f"UPDATE lojas SET status = '{situacao}' WHERE slug = 'loja-a'"))
    nav = navegador()
    for caminho in ('conta', 'conta/entrar', 'conta/criar', 'conta/codigo?t=x', 'conta/senha?v=x'):
        assert nav.get(f'{LOJA}/{caminho}', follow_redirects=False).status_code == 404, caminho
    for caminho in ('conta/entrar', 'conta/criar', 'conta/sair'):
        assert (
            nav.post(f'{LOJA}/{caminho}', data={'telefone': MARIA_TEL}, follow_redirects=False).status_code
            == 404
        )


def test_parametros_estranhos_nunca_dao_erro_do_servidor(navegador, clinica, engine_dono):
    nav = navegador()
    for caminho in (
        f'{LOJA}/conta/entrar?voltar=%00%ff&aviso=<b>',
        f'{LOJA}/conta/criar?voltar=' + 'x' * 3000,
        f'{LOJA}/conta/codigo?t=%ff%fe',
        f'{LOJA}/conta/senha?v=' + 'z' * 3000,
        f'{LOJA}/conta?pagina=%ff',
        f'{LOJA}/conta/entrar?voltar=/loja-a/conta?pagina=²',
    ):
        assert nav.get(caminho, follow_redirects=False).status_code in (200, 303), caminho
    # Dígitos de outros alfabetos (A1): nunca 500 nem JSON, nada gravado
    for telefone in ('١١٩٨٨٨٨١١١١', '¹¹⁹⁸⁸⁸⁸¹¹¹¹'):
        criar = nav.post(f'{LOJA}/conta/criar', data={'telefone': telefone}, follow_redirects=False)
        assert criar.status_code == 200
        assert criar.headers['content-type'] == 'text/html; charset=utf-8'
    t = pedir_codigo(nav, MARIA_TEL)
    for codigo in ('١٢٣٤٥٦', '²²²²²²'):
        assert nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': codigo}).status_code == 200
    assert contar(engine_dono, 'SELECT max(tentativas) FROM cliente_codigos') == 0
    logado = navegador()
    criar_conta(logado, engine_dono, NOVO_TEL, nome='Carla', sobrenome='Dias')
    for pagina in ('²', '٣', '１', '1²', '%ff', '0x10', ' 1', '1e3'):
        assert logado.get(f'{LOJA}/conta', params={'pagina': pagina}).status_code == 200, pagina
    assert (
        nav.post(
            f'{LOJA}/conta/entrar',
            content=b'\xff\xfe',
            headers={'content-type': 'application/x-www-form-urlencoded'},
        ).status_code
        == 200
    )


def test_paginas_da_conta_contam_no_limite_do_site(navegador, clinica, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_site_por_ip', 2)
    nav = navegador('203.0.113.50')
    assert nav.get(f'{LOJA}/conta/entrar').status_code == 200
    assert nav.get(f'{LOJA}/conta/criar').status_code == 200
    assert nav.get(f'{LOJA}/conta/entrar').status_code == 429


def test_auditoria_mascara_senha_e_codigo_e_entrar_fica_fora_do_historico(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    with engine_dono.connect() as conexao:
        linhas = conexao.execute(
            text(
                'SELECT tabela, operacao::text, antes, depois, origem::text, campos_alterados FROM auditoria'
                " WHERE tabela IN ('cliente_contas', 'cliente_codigos') ORDER BY id"
            )
        ).all()
    assert {linha.tabela for linha in linhas} == {'cliente_contas', 'cliente_codigos'}
    for linha in linhas:
        assert linha.origem == 'site'
        for foto in (linha.antes, linha.depois):
            if foto is not None:
                assert 'senha_hash' not in foto
                assert 'codigo' not in foto
    antes = contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'cliente_contas'")
    with engine_dono.connect() as conexao:
        atualizado_antes = conexao.execute(text('SELECT atualizado_em FROM cliente_contas')).scalar_one()
    assert destino(entrar(navegador())) == f'{LOJA}/conta'
    assert contar(engine_dono, "SELECT count(*) FROM auditoria WHERE tabela = 'cliente_contas'") == antes
    with engine_dono.connect() as conexao:
        acesso, atualizado = conexao.execute(
            text('SELECT ultimo_acesso_em, atualizado_em FROM cliente_contas')
        ).one()
    assert atualizado == atualizado_antes
    assert acesso > atualizado_antes


# --- Concorrência (LOG-02, LOG-07) ----------------------------------------------------------------


def _postar_juntos(url: str, envios: list[tuple[str, dict[str, str]]]) -> list[httpx.Response]:
    barreira = threading.Barrier(len(envios))
    respostas: list[httpx.Response | None] = [None] * len(envios)
    erros: list[BaseException] = []

    def postar(i: int) -> None:
        caminho, dados = envios[i]
        try:
            with httpx.Client(base_url=url, timeout=60) as c:
                barreira.wait()
                respostas[i] = c.post(caminho, data=dados)
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=postar, args=(i,)) for i in range(len(envios))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if erros:
        raise erros[0]
    return [r for r in respostas if r is not None]


def test_o_mesmo_passo_da_senha_enviado_junto_vale_uma_vez(navegador, clinica, engine_dono, servidor):
    nav = navegador()
    v = confirmar(nav, pedir_codigo(nav, NOVO_TEL), ultimo_codigo(engine_dono, NOVO)[0])
    dados = {'v': v, 'senha': SENHA, 'repetir': SENHA, 'nome': 'Carla', 'sobrenome': 'Dias'}
    respostas = _postar_juntos(servidor, [(f'{LOJA}/conta/senha', dados)] * 3)
    destinos = sorted(r.headers['location'] for r in respostas)
    assert destinos == [f'{LOJA}/conta', f'{LOJA}/conta/criar', f'{LOJA}/conta/criar']
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_contas') == 1
    assert contar(engine_dono, 'SELECT sessao_versao FROM cliente_contas') == 1
    assert contar(engine_dono, "SELECT count(*) FROM clientes WHERE telefone = '(21) 97777-5555'") == 1


def test_pedidos_de_codigo_juntos_geram_um_codigo_pendente(clinica, engine_dono, servidor):
    respostas = _postar_juntos(servidor, [(f'{LOJA}/conta/criar', {'telefone': MARIA_TEL})] * 3)
    assert sorted(r.status_code for r in respostas) == [303, 429, 429]
    assert (
        contar(
            engine_dono,
            'SELECT count(*) FROM cliente_codigos WHERE invalidado_em IS NULL AND usado_em IS NULL',
        )
        == 1
    )


def test_codigo_certo_enviado_junto_confirma_uma_vez(navegador, clinica, engine_dono, servidor):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    codigo, codigo_id = ultimo_codigo(engine_dono, MARIA)
    respostas = _postar_juntos(servidor, [(f'{LOJA}/conta/codigo', {'t': t, 'codigo': codigo})] * 3)
    codigos = sorted(r.status_code for r in respostas)
    assert codigos == [200, 200, 303]  # os outros veem o código já usado
    assert (
        contar(
            engine_dono,
            'SELECT count(*) FROM cliente_codigos WHERE id = :id AND usado_em IS NOT NULL',
            id=codigo_id,
        )
        == 1
    )


def test_canal_site_nao_e_adicionado_ao_criar_a_conta(navegador, clinica, engine_dono):
    criar_conta(navegador(), engine_dono)
    with sessao(engine_dono) as db:
        maria = db.get(Cliente, UUID(clinica.maria))
        assert CanalCliente.site not in maria.canais


# --- Revisão, rodada 1 (A1 a A3 e o limite de entrar separado) ----------------------------------------


def test_intervalo_de_60s_e_por_telefone_e_ip(navegador, clinica, engine_dono):
    nav = navegador('203.0.113.120')
    t = pedir_codigo(nav, MARIA_TEL)
    assert (
        nav.post(f'{LOJA}/conta/criar', data={'telefone': MARIA_TEL}, follow_redirects=False).status_code
        == 429
    )
    outro_ip = navegador('203.0.113.121')
    assert pedir_codigo(outro_ip, MARIA_TEL)  # outro IP não espera o intervalo (e recebe o mesmo código)
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 1
    assert nav.get(f'{LOJA}/conta/codigo', params={'t': t}).status_code == 200


def test_terceiro_de_outro_ip_nao_impede_a_vitima(navegador, clinica, engine_dono, monkeypatch):
    """A3: quem só sabe o telefone pede 5 códigos e erra 5 vezes; a vítima usa o código que já tem."""
    from app.limites import _chave

    vitima = navegador('198.51.100.10')
    t_vitima = pedir_codigo(vitima, MARIA_TEL)
    codigo_vitima, codigo_id = ultimo_codigo(engine_dono, MARIA)
    atacante = navegador('203.0.113.66')
    t_atacante = ''
    for _ in range(5):
        t_atacante = pedir_codigo(atacante, MARIA_TEL)
        with engine_dono.begin() as conexao:  # sem esperar os 60 s entre um pedido e outro
            conexao.execute(
                text('DELETE FROM limites.contadores WHERE chave = :c'),
                {'c': _chave('site-codigo-intervalo', 'loja-a', MARIA, '203.0.113.66')},
            )
    errado = '000000' if codigo_vitima != '000000' else '111111'
    respostas = [
        atacante.post(f'{LOJA}/conta/codigo', data={'t': t_atacante, 'codigo': errado}) for _ in range(5)
    ]
    assert respostas[-1].status_code == 429
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 1  # nenhum código novo
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos WHERE invalidado_em IS NOT NULL') == 0
    v = confirmar(vitima, t_vitima, codigo_vitima)
    assert destino(definir(vitima, v)) == f'{LOJA}/conta'
    assert contar(engine_dono, 'SELECT tentativas FROM cliente_codigos WHERE id = :id', id=codigo_id) == 5


@pytest.mark.parametrize('telefone', ['١١٩٨٨٨٨١١١١', '¹¹⁹⁸⁸⁸⁸¹¹¹¹', '11９８８８８１１１１'])
def test_telefone_com_digitos_de_outros_alfabetos_e_recusado(navegador, clinica, engine_dono, telefone):
    nav = navegador()
    criar = nav.post(f'{LOJA}/conta/criar', data={'telefone': telefone}, follow_redirects=False)
    assert criar.status_code == 200
    assert criar.headers['content-type'] == 'text/html; charset=utf-8'
    assert 'Informe o telefone com DDD' in criar.text
    assert contar(engine_dono, 'SELECT count(*) FROM cliente_codigos') == 0
    entrar_ = nav.post(
        f'{LOJA}/conta/entrar', data={'telefone': telefone, 'senha': SENHA}, follow_redirects=False
    )
    assert entrar_.status_code == 200
    assert 'Informe o telefone com DDD' in entrar_.text


@pytest.mark.parametrize('codigo', ['١٢٣٤٥٦', '¹²³⁴⁵⁶', '１２３４５６'])
def test_codigo_com_digitos_de_outros_alfabetos_e_recusado(navegador, clinica, engine_dono, codigo):
    nav = navegador()
    t = pedir_codigo(nav, MARIA_TEL)
    resposta = nav.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': codigo}, follow_redirects=False)
    assert resposta.status_code == 200
    assert 'Digite os 6 dígitos do código.' in resposta.text
    assert contar(engine_dono, 'SELECT max(tentativas) FROM cliente_codigos') == 0


def test_so_digitos_aceita_so_ascii():
    from app.schemas.comum import so_digitos

    assert so_digitos('(11) 98888-1111') == '11988881111'
    assert so_digitos('١٢³４') == ''


def test_conflito_do_banco_numa_pagina_da_conta_responde_em_html(navegador, clinica, monkeypatch):
    """40P01 (deadlock) ou 40001 numa página HTML: página de erro em HTML, nunca JSON."""
    from sqlalchemy.exc import OperationalError

    from app.erros import MSG_TENTE_DE_NOVO
    from app.routers.site import conta as paginas_conta

    class Impasse(Exception):
        sqlstate = '40P01'

    def em_impasse(*_args, **_kwargs):
        raise OperationalError('SELECT 1', {}, Impasse())

    monkeypatch.setattr(paginas_conta, 'obter_codigo', em_impasse)
    resposta = navegador().post(f'{LOJA}/conta/criar', data={'telefone': MARIA_TEL}, follow_redirects=False)
    assert resposta.status_code == 409
    assert resposta.headers['content-type'] == 'text/html; charset=utf-8'
    assert MSG_TENTE_DE_NOVO in resposta.text
    assert 'login' not in resposta.text.lower()


def test_entrar_no_site_tem_limite_proprio_separado_do_painel(navegador, clinica, monkeypatch):
    monkeypatch.setattr(get_settings(), 'limite_login_por_ip', 2)
    nav = navegador('203.0.113.130')
    for _ in range(2):
        nav.post(f'{LOJA}/conta/entrar', data={'telefone': MARIA_TEL, 'senha': 'errada-123'})
    assert nav.post(f'{LOJA}/conta/entrar', data={'telefone': MARIA_TEL, 'senha': 'x' * 9}).status_code == 429
    painel = {'slug': 'loja-a', 'email': 'admin@loja-a.com', 'senha': 'errada-123'}
    assert nav.post('/api/loja/auth/login', json=painel).status_code == 401  # o painel não foi afetado

    outro = navegador('203.0.113.131')
    for _ in range(3):
        outro.post('/api/loja/auth/login', json=painel)
    assert outro.post('/api/loja/auth/login', json=painel).status_code == 429
    site = outro.post(f'{LOJA}/conta/entrar', data={'telefone': MARIA_TEL, 'senha': 'x' * 9})
    assert site.status_code == 200  # o site não foi afetado
    assert MSG_ENTRAR in site.text


# --- A2: ordem das travas (telefone primeiro) -----------------------------------------------------------


def _juntos(envios: list[tuple[str, str, dict, dict | None, float]], url: str) -> list[httpx.Response]:
    """(método, caminho, form, json, atraso) ao mesmo tempo contra o servidor real."""
    barreira = threading.Barrier(len(envios))
    respostas: list[httpx.Response | None] = [None] * len(envios)
    erros: list[BaseException] = []

    def enviar(i: int) -> None:
        metodo, caminho, form, cabecalhos, atraso = envios[i]
        try:
            with httpx.Client(base_url=url, timeout=60) as c:
                barreira.wait()
                if atraso:
                    time.sleep(atraso)
                respostas[i] = c.request(metodo, caminho, data=form or None, headers=cabecalhos)
        except BaseException as erro:
            erros.append(erro)

    threads = [threading.Thread(target=enviar, args=(i,)) for i in range(len(envios))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if erros:
        raise erros[0]
    return [r for r in respostas if r is not None]


@pytest.fixture
def sem_limites(monkeypatch):
    s = get_settings()
    for nome, valor in (
        ('limite_codigo_intervalo', 1),
        ('limite_codigos_por_telefone', 10_000),
        ('limite_codigos_por_ip', 10_000),
        ('limite_site_por_ip', 100_000),
    ):
        monkeypatch.setattr(s, nome, valor)


def test_senha_e_novo_codigo_juntos_sem_impasse(navegador, clinica, engine_dono, servidor, sem_limites):
    for rodada in range(8):
        zerar_limites(engine_dono)
        nav = navegador()
        v = confirmar(nav, pedir_codigo(nav, NOVO_TEL), ultimo_codigo(engine_dono, NOVO)[0])
        zerar_limites(engine_dono)
        senha = {'v': v, 'senha': SENHA, 'repetir': SENHA, 'nome': 'Carla', 'sobrenome': 'Dias'}
        atraso = 0.004 * rodada
        r_senha, r_codigo = _juntos(
            [
                ('POST', f'{LOJA}/conta/senha', senha, None, 0.0),
                ('POST', f'{LOJA}/conta/criar', {'telefone': NOVO_TEL}, None, atraso),
            ],
            servidor,
        )
        assert r_senha.status_code == 303, (rodada, r_senha.status_code, r_senha.text[:200])
        assert r_senha.headers['location'] in (f'{LOJA}/conta', f'{LOJA}/conta/criar')
        assert r_codigo.status_code == 303, (rodada, r_codigo.status_code, r_codigo.text[:200])
        assert urlsplit(r_codigo.headers['location']).path == f'{LOJA}/conta/codigo'
        with engine_dono.begin() as conexao:
            conexao.execute(text('DELETE FROM cliente_contas'))
            conexao.execute(text('DELETE FROM cliente_codigos'))


def test_senha_e_remover_acesso_juntos_sem_impasse(navegador, clinica, engine_dono, servidor, sem_limites):
    criar_conta(navegador(), engine_dono)
    admin = {'Authorization': clinica.lt.h_admin['Authorization']}
    for rodada in range(8):
        zerar_limites(engine_dono)
        nav = navegador()
        v = confirmar(nav, pedir_codigo(nav, MARIA_TEL), ultimo_codigo(engine_dono, MARIA)[0])
        senha = {'v': v, 'senha': SENHA, 'repetir': SENHA}
        r_senha, r_remover = _juntos(
            [
                ('POST', f'{LOJA}/conta/senha', senha, None, 0.0),
                ('DELETE', f'/api/loja/clientes/{clinica.maria}/conta-site', {}, admin, 0.004 * rodada),
            ],
            servidor,
        )
        assert r_senha.status_code == 303, (rodada, r_senha.status_code, r_senha.text[:200])
        assert r_senha.headers['location'] in (f'{LOJA}/conta', f'{LOJA}/conta/criar')
        assert r_remover.status_code == 204, (rodada, r_remover.status_code, r_remover.text[:200])
        zerar_limites(engine_dono)
        criar_conta(navegador(), engine_dono)  # conta de novo para a próxima rodada
