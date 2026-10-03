"""Clientes: CRUD, permissões e isolamento entre lojas."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Agendamento, Auditoria, Cliente
from tests.fabricas import inserir, usuario_com

URL = '/api/loja/clientes'
MARIA = {
    'nome': 'Maria',
    'sobrenome': 'Oliveira',
    'cpf': '529.982.247-25',
    'telefone': '(11) 98888-1111',
    'email': 'maria@email.com',
    'data_nascimento': '1985-04-12',
    'canais': ['loja', 'whatsapp', 'loja'],
}


def _criar(cliente, cabecalho, **dados):
    resposta = cliente.post(URL, json={**MARIA, **dados}, headers=cabecalho)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_crud_completo(cliente, lojas, engine_dono):
    a, _ = lojas
    criado = _criar(cliente, a.h_admin)
    assert criado['canais'] == ['loja', 'whatsapp']  # sem repetidos
    assert criado['ativo'] is True
    assert criado['atualizado_por'] == str(a.admin.id)
    assert criado['atualizado_por_nome'] == 'Admin'

    obtido = cliente.get(f'{URL}/{criado["id"]}', headers=a.h_admin).json()
    assert obtido['nome'] == 'Maria'

    editado = cliente.put(
        f'{URL}/{criado["id"]}', json={**MARIA, 'nome': 'Mariana', 'email': ''}, headers=a.h_recepcao
    )
    assert editado.status_code == 200
    assert editado.json()['nome'] == 'Mariana'
    assert editado.json()['email'] is None  # texto vazio do formulário vira nulo
    assert editado.json()['atualizado_por_nome'] == 'Recepção'

    assert cliente.delete(f'{URL}/{criado["id"]}', headers=a.h_admin).status_code == 204
    assert cliente.get(f'{URL}/{criado["id"]}', headers=a.h_admin).status_code == 404

    with engine_dono.connect() as conexao:
        operacoes = conexao.execute(
            select(Auditoria.operacao, Auditoria.funcionario_id)
            .where(Auditoria.tabela == 'clientes')
            .order_by(Auditoria.id)
        ).all()
    assert [o for o, _ in operacoes] == ['inserir', 'alterar', 'excluir']
    assert operacoes[-1][1] == a.admin.id


def test_lista_paginada_com_busca_e_filtros(cliente, lojas):
    a, _ = lojas
    _criar(cliente, a.h_admin)
    _criar(
        cliente,
        a.h_admin,
        nome='João',
        sobrenome='Pereira',
        cpf=None,
        telefone='(21) 3222-2222',
        canais=['site'],
    )
    _criar(
        cliente,
        a.h_admin,
        nome='Fernanda',
        sobrenome='Costa',
        cpf='',
        telefone='(31) 93333-3333',
        ativo=False,
    )

    pagina = cliente.get(URL, params={'por_pagina': 2}, headers=a.h_admin).json()
    assert pagina['total'] == 3
    assert [c['nome'] for c in pagina['itens']] == ['Fernanda', 'João']
    assert (
        cliente.get(URL, params={'pagina': 2, 'por_pagina': 2}, headers=a.h_admin).json()['itens'][0]['nome']
        == 'Maria'
    )

    def nomes(**params):
        return [c['nome'] for c in cliente.get(URL, params=params, headers=a.h_admin).json()['itens']]

    assert nomes(busca='maria oli') == ['Maria']
    assert nomes(busca='2222') == ['João']
    assert nomes(busca='2132222222') == ['João']  # telefone sem máscara
    assert nomes(busca='%') == []  # curinga do LIKE é tratado como texto
    assert nomes(canal='site') == ['João']
    assert nomes(ativo=False) == ['Fernanda']


def test_cpf_repetido_na_mesma_loja(cliente, lojas):
    a, b = lojas
    criado = _criar(cliente, a.h_admin)
    repetido = cliente.post(URL, json=MARIA, headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um cliente com este CPF.'
    # Outra loja pode ter o mesmo CPF (cadastros independentes)
    _criar(cliente, b.h_admin)
    # Depois de excluído, o CPF pode ser usado de novo
    cliente.delete(f'{URL}/{criado["id"]}', headers=a.h_admin)
    _criar(cliente, a.h_admin)


def test_validacao_em_portugues(cliente, lojas):
    a, _ = lojas
    resposta = cliente.post(URL, json={**MARIA, 'nome': '   ', 'email': 'invalido'}, headers=a.h_admin)
    assert resposta.status_code == 422
    campos = {e['campo']: e['mensagem'] for e in resposta.json()['erros']}
    assert set(campos) == {'nome', 'email'}
    assert campos['email'] == 'E-mail inválido.'


def test_cliente_com_agendamento_nao_e_excluido(cliente, lojas, engine_dono):
    a, _ = lojas
    criado = _criar(cliente, a.h_admin)
    inicio = datetime.now(UTC) + timedelta(days=1)
    inserir(
        engine_dono,
        Agendamento(
            loja_id=a.loja.id,
            cliente_id=criado['id'],
            funcionario_id=a.prof.id,
            inicio=inicio,
            fim=inicio + timedelta(minutes=30),
        ),
    )
    resposta = cliente.delete(f'{URL}/{criado["id"]}', headers=a.h_admin)
    assert resposta.status_code == 409
    assert 'Inative' in resposta.json()['detail']


def test_permissoes(cliente, lojas, engine_dono):
    a, _ = lojas
    criado = _criar(cliente, a.h_admin)
    # Profissional: leitura em clientes
    assert cliente.get(URL, headers=a.h_prof).status_code == 200
    assert cliente.get(f'{URL}/{criado["id"]}', headers=a.h_prof).status_code == 200
    escrita = cliente.post(URL, json={**MARIA, 'cpf': None}, headers=a.h_prof)
    assert escrita.status_code == 403
    assert escrita.json()['detail'] == 'Você só tem permissão de leitura aqui.'
    assert cliente.put(f'{URL}/{criado["id"]}', json=MARIA, headers=a.h_prof).status_code == 403
    assert cliente.delete(f'{URL}/{criado["id"]}', headers=a.h_prof).status_code == 403
    # Sem nível em clientes: nem lê
    sem_acesso = usuario_com(engine_dono, a.loja, {'agenda_propria': 'escrita'})
    assert cliente.get(URL, headers=sem_acesso).status_code == 403
    assert cliente.get(f'{URL}/{criado["id"]}', headers=sem_acesso).status_code == 403
    # Sem token
    assert cliente.get(URL).status_code == 401


def test_isolamento_entre_lojas(cliente, lojas, engine_dono):
    a, b = lojas
    da_a = _criar(cliente, a.h_admin)
    url = f'{URL}/{da_a["id"]}'
    assert cliente.get(url, headers=b.h_admin).status_code == 404
    assert cliente.put(url, json=MARIA, headers=b.h_admin).status_code == 404
    assert cliente.delete(url, headers=b.h_admin).status_code == 404
    assert cliente.get(URL, headers=b.h_admin).json()['total'] == 0
    # loja_id no corpo é ignorado: o cliente nasce na loja do token
    criado_b = _criar(cliente, b.h_admin, loja_id=str(a.loja.id), cpf=None)
    with engine_dono.connect() as conexao:
        loja_id = conexao.execute(select(Cliente.loja_id).where(Cliente.id == criado_b['id'])).scalar()
        nome = conexao.execute(select(Cliente.nome).where(Cliente.id == da_a['id'])).scalar()
    assert loja_id == b.loja.id
    assert nome == 'Maria'
