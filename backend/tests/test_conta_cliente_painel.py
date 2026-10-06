"""Painel: códigos do site e acesso do cliente ao site (CLI-06, SIT-17, SIT-20).

Rotas: ``GET /api/loja/clientes/codigos-site``, ``GET`` e ``DELETE /api/loja/clientes/{id}/conta-site``.
Todas exigem escrita em Clientes. Os códigos e as contas nascem pelas páginas do site (tests/clinica.py:
Maria (11) 98888-1111 e João (11) 98888-2222).
"""

from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models import Cliente
from tests.fabricas import inserir, mudar_modulo, usuario_com

LOJA = '/loja-a'
MARIA_TEL, MARIA = '(11) 98888-1111', '11988881111'
SENHA = 'senha-forte-1'
CODIGOS = '/api/loja/clientes/codigos-site'


def conta_site(cliente_id) -> str:
    return f'/api/loja/clientes/{cliente_id}/conta-site'


def pedir_codigo(cliente, telefone: str, slug: str = 'loja-a') -> str:
    resposta = cliente.post(f'/{slug}/conta/criar', data={'telefone': telefone}, follow_redirects=False)
    assert resposta.status_code == 303
    return parse_qs(urlsplit(resposta.headers['location']).query)['t'][0]


def ultimo_codigo(engine, digitos: str) -> str:
    with engine.connect() as conexao:
        return conexao.execute(
            text(
                'SELECT codigo FROM cliente_codigos WHERE telefone_digitos = :d ORDER BY criado_em DESC LIMIT 1'
            ),
            {'d': digitos},
        ).scalar_one()


def criar_conta(cliente, engine, telefone: str = MARIA_TEL) -> None:
    t = pedir_codigo(cliente, telefone)
    digitos = ''.join(c for c in telefone if c.isdigit())
    resposta = cliente.post(
        f'{LOJA}/conta/codigo',
        data={'t': t, 'codigo': ultimo_codigo(engine, digitos)},
        follow_redirects=False,
    )
    v = parse_qs(urlsplit(resposta.headers['location']).query)['v'][0]
    resposta = cliente.post(
        f'{LOJA}/conta/senha',
        data={'v': v, 'senha': SENHA, 'repetir': SENHA, 'nome': 'Novo', 'sobrenome': 'Cliente'},
        follow_redirects=False,
    )
    assert resposta.headers['location'] == f'{LOJA}/conta'
    cliente.cookies.clear()


def zerar_limites(engine) -> None:
    with engine.begin() as conexao:
        conexao.execute(text('DELETE FROM limites.contadores'))


def test_codigos_pendentes_com_os_clientes_do_telefone(cliente, clinica, engine_dono):
    lt = clinica.lt
    xara = inserir(
        engine_dono, Cliente(loja_id=lt.loja.id, nome='Mariana', sobrenome='Souza', telefone=MARIA_TEL)
    )
    pedir_codigo(cliente, '(21) 97777-5555')  # sem cadastro
    pedir_codigo(cliente, MARIA_TEL)
    resposta = cliente.get(CODIGOS, headers=lt.h_admin)
    assert resposta.status_code == 200
    itens = resposta.json()
    assert [i['telefone'] for i in itens] == [MARIA_TEL, '(21) 97777-5555']  # mais novo primeiro
    maria = itens[0]
    assert set(maria) == {'telefone', 'codigo', 'expira_em', 'criado_em', 'clientes'}
    assert maria['codigo'] == ultimo_codigo(engine_dono, MARIA)
    assert maria['clientes'] == [
        {'id': clinica.maria, 'nome': 'Maria Oliveira'},
        {'id': str(xara.id), 'nome': 'Mariana Souza'},
    ]
    assert itens[1]['clientes'] == []
    # Datas no fuso da loja, validade de 15 minutos
    expira, criado = datetime.fromisoformat(maria['expira_em']), datetime.fromisoformat(maria['criado_em'])
    assert maria['expira_em'].endswith('-03:00')
    assert (expira - criado).total_seconds() == pytest.approx(15 * 60, abs=1)


def test_codigos_usados_vencidos_ou_invalidados_nao_aparecem(cliente, clinica, engine_dono):
    lt = clinica.lt
    t = pedir_codigo(cliente, MARIA_TEL)
    cliente.post(f'{LOJA}/conta/codigo', data={'t': t, 'codigo': ultimo_codigo(engine_dono, MARIA)})  # usado
    pedir_codigo(cliente, '(11) 98888-2222')
    zerar_limites(engine_dono)
    pedir_codigo(cliente, '(11) 98888-2222')  # invalida o anterior do João
    pedir_codigo(cliente, '(11) 91111-0001')
    with engine_dono.begin() as conexao:
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text(
                "UPDATE cliente_codigos SET criado_em = now() - interval '1 hour',"
                " expira_em = now() - interval '1 minute' WHERE telefone_digitos = '11911110001'"
            )
        )
    itens = cliente.get(CODIGOS, headers=lt.h_admin).json()
    assert [i['telefone'] for i in itens] == ['(11) 98888-2222']
    assert itens[0]['codigo'] == ultimo_codigo(engine_dono, '11988882222')


def test_codigos_de_outra_loja_nao_aparecem(cliente, clinica, lojas, engine_dono):
    pedir_codigo(cliente, MARIA_TEL)
    assert cliente.get(CODIGOS, headers=lojas[1].h_admin).json() == []
    pedir_codigo(cliente, MARIA_TEL, 'loja-b')
    itens = cliente.get(CODIGOS, headers=lojas[1].h_admin).json()
    assert len(itens) == 1
    assert itens[0]['clientes'] == []  # a Maria é cliente da loja A, não da B


def test_conta_site_sem_conta_com_codigo_e_com_conta(cliente, clinica, engine_dono):
    h = clinica.lt.h_admin
    vazio = cliente.get(conta_site(clinica.maria), headers=h)
    assert vazio.status_code == 200
    assert vazio.json() == {
        'possui_conta': False,
        'criada_em': None,
        'ultimo_acesso_em': None,
        'codigo_pendente': None,
    }
    pedir_codigo(cliente, MARIA_TEL)
    so_codigo = cliente.get(conta_site(clinica.maria), headers=h).json()
    assert so_codigo['possui_conta'] is False
    assert so_codigo['codigo_pendente']['codigo'] == ultimo_codigo(engine_dono, MARIA)
    assert set(so_codigo['codigo_pendente']) == {'codigo', 'expira_em'}

    zerar_limites(engine_dono)
    criar_conta(cliente, engine_dono)
    com_conta = cliente.get(conta_site(clinica.maria), headers=h).json()
    assert com_conta['possui_conta'] is True
    assert com_conta['criada_em'].endswith('-03:00')
    assert com_conta['ultimo_acesso_em'] is not None
    assert com_conta['codigo_pendente'] is None  # o código foi consumido
    # O João (outro telefone) não tem conta
    assert cliente.get(conta_site(clinica.joao), headers=h).json()['possui_conta'] is False


def test_conta_site_segue_o_telefone_atual_do_cliente(cliente, clinica, engine_dono):
    h = clinica.lt.h_admin
    criar_conta(cliente, engine_dono)
    cliente.put(
        f'/api/loja/clientes/{clinica.joao}',
        json={'nome': 'João', 'sobrenome': 'Pereira', 'telefone': MARIA_TEL},
        headers=h,
    )
    assert cliente.get(conta_site(clinica.joao), headers=h).json()['possui_conta'] is True


def test_remover_acesso(cliente, clinica, engine_dono):
    h = clinica.lt.h_admin
    criar_conta(cliente, engine_dono)
    zerar_limites(engine_dono)
    pedir_codigo(cliente, MARIA_TEL)  # código pendente: também é invalidado
    resposta = cliente.delete(conta_site(clinica.maria), headers=h)
    assert resposta.status_code == 204
    with engine_dono.connect() as conexao:
        versao, excluido_em, excluido_por = conexao.execute(
            text('SELECT sessao_versao, excluido_em, excluido_por FROM cliente_contas')
        ).one()
        pendentes = conexao.execute(
            text('SELECT count(*) FROM cliente_codigos WHERE invalidado_em IS NULL AND usado_em IS NULL')
        ).scalar_one()
    assert versao == 2
    assert excluido_em is not None
    assert excluido_por == clinica.lt.admin.id
    assert pendentes == 0
    assert cliente.get(conta_site(clinica.maria), headers=h).json() == {
        'possui_conta': False,
        'criada_em': None,
        'ultimo_acesso_em': None,
        'codigo_pendente': None,
    }
    segunda = cliente.delete(conta_site(clinica.maria), headers=h)
    assert segunda.status_code == 404
    assert segunda.json() == {'detail': 'Este cliente não tem acesso ao site.'}


def test_auditoria_da_remocao_pelo_painel(cliente, clinica, engine_dono):
    criar_conta(cliente, engine_dono)
    cliente.delete(conta_site(clinica.maria), headers=clinica.lt.h_admin)
    with engine_dono.connect() as conexao:
        linha = conexao.execute(
            text(
                'SELECT operacao::text, origem::text, funcionario_id, antes, depois FROM auditoria'
                " WHERE tabela = 'cliente_contas' ORDER BY id DESC LIMIT 1"
            )
        ).one()
    assert linha.operacao == 'excluir'
    assert linha.origem == 'painel'
    assert linha.funcionario_id == clinica.lt.admin.id
    assert 'senha_hash' not in linha.antes
    assert 'senha_hash' not in linha.depois
    assert linha.depois['sessao_versao'] == 2


@pytest.mark.parametrize(
    ('metodo', 'caminho'),
    [('get', CODIGOS), ('get', 'conta'), ('delete', 'conta')],
)
def test_exige_escrita_em_clientes(cliente, clinica, engine_dono, metodo, caminho):
    url = conta_site(clinica.maria) if caminho == 'conta' else caminho
    leitura = usuario_com(engine_dono, clinica.lt.loja, {'clientes': 'leitura'})
    resposta = getattr(cliente, metodo)(url, headers=leitura)
    assert resposta.status_code == 403
    assert resposta.json() == {'detail': 'Você só tem permissão de leitura aqui.'}
    nenhum = usuario_com(engine_dono, clinica.lt.loja, {'agenda_equipe': 'escrita'})
    assert getattr(cliente, metodo)(url, headers=nenhum).status_code == 403
    sem_token = getattr(cliente, metodo)(url)
    assert sem_token.status_code == 401
    escrita = usuario_com(engine_dono, clinica.lt.loja, {'clientes': 'escrita'})
    assert getattr(cliente, metodo)(url, headers=escrita).status_code in (200, 404)  # 404: sem conta


def test_loja_suspensa_responde_403(cliente, clinica, engine_dono):
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET status = 'suspensa' WHERE slug = 'loja-a'"))
    resposta = cliente.get(CODIGOS, headers=clinica.lt.h_admin)
    assert resposta.status_code == 403
    assert resposta.json() == {'detail': 'Esta loja está suspensa. Fale com o suporte da plataforma.'}


def test_cliente_de_outra_loja_inexistente_ou_excluido_responde_404(cliente, clinica, lojas, engine_dono):
    criar_conta(cliente, engine_dono)
    h_b = lojas[1].h_admin
    for metodo in ('get', 'delete'):
        resposta = getattr(cliente, metodo)(conta_site(clinica.maria), headers=h_b)
        assert resposta.status_code == 404
        assert resposta.json() == {'detail': 'Cliente não encontrado.'}
        assert getattr(cliente, metodo)(conta_site(uuid4()), headers=clinica.lt.h_admin).status_code == 404
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE clientes SET excluido_em = now() WHERE id = :id'), {'id': clinica.maria})
    for metodo in ('get', 'delete'):
        assert (
            getattr(cliente, metodo)(conta_site(clinica.maria), headers=clinica.lt.h_admin).status_code == 404
        )
    # A conta da loja A continua lá (ninguém de fora a removeu)
    with engine_dono.connect() as conexao:
        assert (
            conexao.execute(
                text('SELECT count(*) FROM cliente_contas WHERE excluido_em IS NULL')
            ).scalar_one()
            == 1
        )


def test_rota_de_codigos_vem_antes_do_id(cliente, clinica):
    """``codigos-site`` não é lido como id do cliente (seria 422)."""
    assert cliente.get(CODIGOS, headers=clinica.lt.h_admin).status_code == 200
    assert (
        cliente.get('/api/loja/clientes/nao-e-id/conta-site', headers=clinica.lt.h_admin).status_code == 422
    )


def test_modulos_opcionais_nao_mudam_o_acesso(cliente, clinica, engine_dono):
    """Clientes não é módulo opcional: desligar Serviços ou Locais não esconde as rotas."""
    for modulo in ('servicos', 'locais'):
        mudar_modulo(engine_dono, clinica.lt.loja.id, modulo, habilitado=False)
    assert cliente.get(CODIGOS, headers=clinica.lt.h_admin).status_code == 200


def test_codigo_mascarado_na_auditoria(cliente, clinica, engine_dono):
    pedir_codigo(cliente, MARIA_TEL)
    codigo = ultimo_codigo(engine_dono, MARIA)
    with engine_dono.connect() as conexao:
        fotos = conexao.execute(
            text("SELECT antes, depois FROM auditoria WHERE tabela = 'cliente_codigos'")
        ).all()
    assert fotos
    for antes, depois in fotos:
        for foto in (antes, depois):
            if foto is not None:
                assert 'codigo' not in foto
                assert codigo not in str(foto)
