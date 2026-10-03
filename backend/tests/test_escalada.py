"""Sem escalada de acesso dentro da loja (ACE-19, SEG-05).

Quem não é Administrador não concede nível acima do seu (editando um perfil, copiando um perfil ou
atribuindo um perfil a alguém), não altera o próprio perfil, não troca o próprio perfil no cadastro
e não troca a senha de um colega que tem acesso maior que o seu.
"""

from sqlalchemy import select

from app.auth.senhas import verificar_senha
from app.models import Funcionario
from tests.fabricas import usuario_com

API = '/api/loja'
MSG_CONCEDER = 'Você não pode conceder um nível de acesso maior que o seu.'
MSG_PROPRIO_PERFIL = 'Você não pode alterar o seu próprio perfil de acesso.'
MSG_ATRIBUIR = 'Você não pode atribuir um perfil com acesso maior que o seu.'
MSG_TROCAR_PROPRIO = 'Você não pode trocar o seu próprio perfil de acesso.'
MSG_SENHA = 'Você não pode trocar a senha de quem tem acesso maior que o seu.'


def _eu(cliente, h):
    return cliente.get(f'{API}/eu', headers=h).json()


def _perfil(cliente, h_admin, nome, acessos):
    perfil = cliente.post(f'{API}/perfis', json={'nome': nome}, headers=h_admin).json()
    resposta = cliente.put(f'{API}/perfis/{perfil["id"]}/acessos', json={'acessos': acessos}, headers=h_admin)
    assert resposta.status_code == 200, resposta.json()
    return perfil['id']


# --- Níveis do perfil --------------------------------------------------------------------------------


def test_nao_edita_os_niveis_do_proprio_perfil(cliente, lojas, engine_dono):
    a, _ = lojas
    h = usuario_com(engine_dono, a.loja, {'perfis_acesso': 'escrita'})
    eu = _eu(cliente, h)
    resposta = cliente.put(
        f'{API}/perfis/{eu["perfil"]["id"]}/acessos',
        json={'acessos': {'config_loja': 'escrita', 'funcionarios': 'escrita'}},
        headers=h,
    )
    assert resposta.status_code == 403
    assert resposta.json()['detail'] == MSG_PROPRIO_PERFIL
    assert _eu(cliente, h)['acessos']['config_loja'] == 'nenhum'
    assert cliente.get(f'{API}/configuracoes/loja', headers=h).status_code == 403
    # Nem renomear o próprio perfil
    renomear = cliente.put(f'{API}/perfis/{eu["perfil"]["id"]}', json={'nome': 'Chefe'}, headers=h)
    assert renomear.status_code == 403


def test_nao_concede_nivel_acima_do_seu_em_outro_perfil(cliente, lojas, engine_dono):
    a, _ = lojas
    h = usuario_com(engine_dono, a.loja, {'perfis_acesso': 'escrita', 'clientes': 'leitura'})
    alvo = _perfil(cliente, a.h_admin, 'Estagiário', {'clientes': 'nenhum'})

    acima = cliente.put(f'{API}/perfis/{alvo}/acessos', json={'acessos': {'clientes': 'escrita'}}, headers=h)
    assert acima.status_code == 403
    assert acima.json()['detail'] == MSG_CONCEDER
    outro_recurso = cliente.put(
        f'{API}/perfis/{alvo}/acessos', json={'acessos': {'config_loja': 'leitura'}}, headers=h
    )
    assert outro_recurso.status_code == 403
    # Até o próprio nível pode
    igual = cliente.put(f'{API}/perfis/{alvo}/acessos', json={'acessos': {'clientes': 'leitura'}}, headers=h)
    assert igual.status_code == 200
    assert igual.json()['acessos']['clientes'] == 'leitura'


def test_reenviar_ou_baixar_nivel_que_o_perfil_ja_tem_nao_e_escalada(cliente, lojas, engine_dono):
    a, _ = lojas
    # Recepção tem escrita em clientes e agenda da equipe; este usuário não
    h = usuario_com(engine_dono, a.loja, {'perfis_acesso': 'escrita'})
    recepcao = str(a.perfis['Recepção'].id)
    atual = cliente.get(f'{API}/perfis/{recepcao}', headers=h).json()['acessos']
    resposta = cliente.put(
        f'{API}/perfis/{recepcao}/acessos',
        json={'acessos': {**atual, 'clientes': 'leitura'}},  # tela manda tudo, baixando um nível
        headers=h,
    )
    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()['acessos']['clientes'] == 'leitura'
    assert resposta.json()['acessos']['agenda_equipe'] == 'escrita'
    # Mas voltar para escrita é conceder
    subir = cliente.put(
        f'{API}/perfis/{recepcao}/acessos', json={'acessos': {'clientes': 'escrita'}}, headers=h
    )
    assert subir.status_code == 403


def test_nao_copia_perfil_com_nivel_acima_do_seu(cliente, lojas, engine_dono):
    a, _ = lojas
    h = usuario_com(engine_dono, a.loja, {'perfis_acesso': 'escrita'})
    copia = cliente.post(
        f'{API}/perfis', json={'nome': 'Recepção 2', 'copiar_de': str(a.perfis['Recepção'].id)}, headers=h
    )
    assert copia.status_code == 403
    assert copia.json()['detail'] == MSG_CONCEDER
    assert all(p['nome'] != 'Recepção 2' for p in cliente.get(f'{API}/perfis', headers=a.h_admin).json())
    # O Administrador copia qualquer perfil
    assert (
        cliente.post(
            f'{API}/perfis',
            json={'nome': 'Recepção 2', 'copiar_de': str(a.perfis['Recepção'].id)},
            headers=a.h_admin,
        ).status_code
        == 201
    )


# --- Perfil do funcionário ---------------------------------------------------------------------------


def _corpo(funcionario, **extra):
    return {
        'nome': funcionario['nome'],
        'email': funcionario['email'],
        'perfil_id': funcionario['perfil_id'],
        **extra,
    }


def test_nao_troca_o_proprio_perfil(cliente, lojas, engine_dono):
    a, _ = lojas
    # Perfil "Gerente" com escrita em tudo, criado pelo Administrador
    tudo = dict.fromkeys(_eu(cliente, a.h_admin)['acessos'], 'escrita')
    gerente = _perfil(cliente, a.h_admin, 'Gerente', tudo)
    h = usuario_com(engine_dono, a.loja, {'funcionarios': 'escrita'})
    eu = _eu(cliente, h)['funcionario']
    resposta = cliente.put(f'{API}/funcionarios/{eu["id"]}', json=_corpo(eu, perfil_id=gerente), headers=h)
    assert resposta.status_code == 403
    assert resposta.json()['detail'] == MSG_TROCAR_PROPRIO
    assert _eu(cliente, h)['acessos']['config_loja'] == 'nenhum'
    # Nem o Administrador troca o próprio perfil (outro Administrador faz isso)
    admin = cliente.put(
        f'{API}/funcionarios/{a.admin.id}',
        json={'nome': 'Admin', 'email': 'admin@loja-a.com', 'perfil_id': str(a.perfis['Recepção'].id)},
        headers=a.h_admin,
    )
    assert admin.status_code == 403
    # Editar os outros dados do próprio cadastro continua liberado
    nome = cliente.put(f'{API}/funcionarios/{eu["id"]}', json=_corpo(eu, nome='Novo nome'), headers=h)
    assert nome.status_code == 200


def test_nao_atribui_perfil_com_nivel_acima_do_seu(cliente, lojas, engine_dono):
    a, _ = lojas
    h = usuario_com(engine_dono, a.loja, {'funcionarios': 'escrita', 'clientes': 'leitura'})
    recepcao = str(a.perfis['Recepção'].id)  # tem escrita em clientes e agenda
    novo = {'nome': 'Bia', 'email': 'bia@loja-a.com', 'perfil_id': recepcao, 'senha': 'senha-forte-1'}
    cadastro = cliente.post(f'{API}/funcionarios', json=novo, headers=h)
    assert cadastro.status_code == 403
    assert cadastro.json()['detail'] == MSG_ATRIBUIR
    promover = cliente.put(
        f'{API}/funcionarios/{a.prof.id}',
        json={'nome': 'Profissional', 'email': 'prof@loja-a.com', 'perfil_id': recepcao},
        headers=h,
    )
    assert promover.status_code == 403
    # Perfil com níveis iguais ou menores pode
    menor = _perfil(cliente, a.h_admin, 'Consulta', {'clientes': 'leitura'})
    assert (
        cliente.post(f'{API}/funcionarios', json={**novo, 'perfil_id': menor}, headers=h).status_code == 201
    )


def test_nao_troca_a_senha_de_quem_tem_acesso_maior(cliente, lojas, engine_dono):
    a, _ = lojas
    h = usuario_com(engine_dono, a.loja, {'funcionarios': 'escrita', 'clientes': 'leitura'})
    recepcao = {'nome': 'Recepção', 'email': 'recepcao@loja-a.com', 'perfil_id': str(a.perfis['Recepção'].id)}
    resposta = cliente.put(
        f'{API}/funcionarios/{a.recepcao.id}', json={**recepcao, 'senha': 'invasor-123'}, headers=h
    )
    assert resposta.status_code == 403
    assert resposta.json()['detail'] == MSG_SENHA
    with engine_dono.connect() as conexao:
        senha_hash = conexao.execute(
            select(Funcionario.senha_hash).where(Funcionario.id == a.recepcao.id)
        ).scalar()
    assert not verificar_senha('invasor-123', senha_hash)[0]
    # Sem trocar a senha, editar o colega continua liberado (o perfil não muda)
    assert cliente.put(f'{API}/funcionarios/{a.recepcao.id}', json=recepcao, headers=h).status_code == 200
    # Colega com acesso menor ou igual: pode trocar a senha
    menor = _perfil(cliente, a.h_admin, 'Consulta', {'clientes': 'leitura'})
    colega = cliente.post(
        f'{API}/funcionarios',
        json={'nome': 'Bia', 'email': 'bia@loja-a.com', 'perfil_id': menor, 'senha': 'senha-forte-1'},
        headers=a.h_admin,
    ).json()
    trocar = cliente.put(
        f'{API}/funcionarios/{colega["id"]}',
        json={'nome': 'Bia', 'email': 'bia@loja-a.com', 'perfil_id': menor, 'senha': 'nova-senha-2'},
        headers=h,
    )
    assert trocar.status_code == 200
    # A própria senha sempre pode
    eu = _eu(cliente, h)['funcionario']
    assert (
        cliente.put(
            f'{API}/funcionarios/{eu["id"]}', json=_corpo(eu, senha='minha-nova-3'), headers=h
        ).status_code
        == 200
    )


def test_administrador_continua_sem_restricao(cliente, lojas):
    a, _ = lojas
    gerente = _perfil(cliente, a.h_admin, 'Gerente', {'config_loja': 'escrita', 'funcionarios': 'escrita'})
    resposta = cliente.put(
        f'{API}/funcionarios/{a.recepcao.id}',
        json={
            'nome': 'Recepção',
            'email': 'recepcao@loja-a.com',
            'perfil_id': gerente,
            'senha': 'senha-nova-1',
        },
        headers=a.h_admin,
    )
    assert resposta.status_code == 200
