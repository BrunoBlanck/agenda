"""Busca de clientes do formulário de agendamento (GET /api/loja/apoio/clientes, ACE-21)."""

from tests.fabricas import mudar_modulo, usuario_com

URL = '/api/loja/apoio/clientes'


def _criar(cliente, h, nome, telefone, **extra):
    resposta = cliente.post(
        '/api/loja/clientes',
        json={'nome': nome, 'sobrenome': 'Silva', 'telefone': telefone, **extra},
        headers=h,
    )
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_busca_por_nome_e_telefone(cliente, lojas):
    a, _ = lojas
    _criar(cliente, a.h_admin, 'Maria', '(11) 98888-1111', cpf='529.982.247-25')
    _criar(cliente, a.h_admin, 'Mariana', '(21) 3222-1010')
    _criar(cliente, a.h_admin, 'Marta', '(31) 97777-0000', ativo=False)

    def nomes(busca, h=a.h_recepcao):
        resposta = cliente.get(URL, params={'busca': busca}, headers=h)
        assert resposta.status_code == 200, resposta.json()
        return [c['nome'] for c in resposta.json()['itens']]

    assert nomes('mar') == ['Maria', 'Mariana']  # só ativos
    assert nomes('maria silva') == ['Maria']
    for termo in ('11988881111', '(11) 98888-1111', '8888-1111', '98888 1111'):
        assert nomes(termo) == ['Maria'], termo
    assert nomes('2132221010') == ['Mariana']


def test_nao_busca_por_cpf_nem_email(cliente, lojas, engine_dono):
    """Quem só agenda não descobre se um CPF ou e-mail é cliente da loja (SEG-06)."""
    a, _ = lojas
    _criar(cliente, a.h_admin, 'Maria', '(11) 98888-1111', cpf='529.982.247-25', email='maria.o@exemplo.com')
    so_agenda = usuario_com(engine_dono, a.loja, {'agenda_propria': 'escrita'})
    for termo in (
        '52998224725',
        '529.982.247-25',
        '982.247',
        'maria.o@exemplo.com',
        'exemplo.com',
        '@exemplo',
    ):
        resposta = cliente.get(URL, params={'busca': termo}, headers=so_agenda)
        assert resposta.status_code == 200, resposta.json()
        assert resposta.json()['total'] == 0, termo
    # A lista de Clientes (recurso clientes) continua achando por CPF e e-mail
    for termo in ('52998224725', '529.982.247-25', 'exemplo.com'):
        resposta = cliente.get('/api/loja/clientes', params={'busca': termo}, headers=a.h_admin)
        assert [c['nome'] for c in resposta.json()['itens']] == ['Maria'], termo


def test_devolve_so_o_necessario_e_paginado(cliente, lojas):
    a, _ = lojas
    for i in range(3):
        _criar(cliente, a.h_admin, f'Ana {i}', f'(11) 9888{i}-0000', email=f'ana{i}@x.com', cpf=None)
    resposta = cliente.get(URL, params={'busca': 'ana', 'por_pagina': 2}, headers=a.h_admin).json()
    assert resposta['total'] == 3
    assert (resposta['pagina'], resposta['por_pagina']) == (1, 2)
    assert len(resposta['itens']) == 2
    assert set(resposta['itens'][0]) == {'id', 'nome', 'sobrenome', 'telefone'}  # sem CPF nem e-mail
    assert resposta['itens'][0]['telefone'] == '(11) 98880-0000'


def test_busca_exige_termo_minimo(cliente, lojas):
    a, _ = lojas
    curto = cliente.get(URL, params={'busca': ' a '}, headers=a.h_admin)
    assert curto.status_code == 422
    assert curto.json()['detail'] == 'Digite pelo menos 2 caracteres para buscar.'
    assert cliente.get(URL, headers=a.h_admin).status_code == 422
    assert cliente.get(URL, params={'busca': 'x' * 101}, headers=a.h_admin).status_code == 422


def test_liberada_para_quem_agenda_mesmo_sem_acesso_a_clientes(cliente, lojas, engine_dono):
    a, _ = lojas
    _criar(cliente, a.h_admin, 'Maria', '(11) 98888-1111')
    so_agenda = usuario_com(engine_dono, a.loja, {'agenda_propria': 'escrita'})
    assert cliente.get('/api/loja/clientes', headers=so_agenda).status_code == 403
    assert cliente.get(URL, params={'busca': 'maria'}, headers=so_agenda).json()['total'] == 1
    # Quem só lê a agenda, ou só mexe em clientes, não usa a busca do formulário
    so_le = usuario_com(engine_dono, a.loja, {'agenda_equipe': 'leitura'})
    assert cliente.get(URL, params={'busca': 'maria'}, headers=so_le).status_code == 403
    so_clientes = usuario_com(engine_dono, a.loja, {'clientes': 'escrita'})
    assert cliente.get(URL, params={'busca': 'maria'}, headers=so_clientes).status_code == 403
    assert cliente.get(URL, params={'busca': 'maria'}).status_code == 401


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    _criar(cliente, a.h_admin, 'Maria', '(11) 98888-1111')
    assert cliente.get(URL, params={'busca': 'maria'}, headers=b.h_admin).json()['total'] == 0
    assert cliente.get(URL, params={'busca': '11988881111'}, headers=b.h_admin).json()['total'] == 0


def test_apoio_do_agendamento_nao_traz_mais_a_lista_de_clientes(cliente, lojas, engine_dono):
    a, _ = lojas
    _criar(cliente, a.h_admin, 'Maria', '(11) 98888-1111')
    apoio = cliente.get('/api/loja/apoio/agendamento', headers=a.h_admin).json()
    assert set(apoio) == {'servicos', 'profissionais', 'locais', 'materiais'}
    mudar_modulo(engine_dono, a.loja.id, 'servicos', habilitado=False)
    assert cliente.get('/api/loja/apoio/agendamento', headers=a.h_admin).json()['servicos'] is None
