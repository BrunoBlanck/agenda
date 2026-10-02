"""Funcionários e cargos: CRUD, regras do Administrador, permissões e isolamento entre lojas."""

from sqlalchemy import select

from app.auth.senhas import verificar_senha
from app.models import Funcionario
from tests.fabricas import usuario_com

URL = '/api/loja/funcionarios'
CARGOS = '/api/loja/cargos'


def _dados(lt, **extra):
    return {
        'nome': 'Dra. Bia',
        'email': 'bia@loja.com',
        'perfil_id': str(lt.perfis['Profissional'].id),
        'telefone': '(11) 99999-0009',
        'cor_agenda': '#2563eb',
        'senha': 'senha-forte-1',
        **extra,
    }


def test_crud_de_funcionario_com_cargo(cliente, lojas, engine_dono):
    a, _ = lojas
    cargo = cliente.post(CARGOS, json={'nome': 'Dentista'}, headers=a.h_admin)
    assert cargo.status_code == 201
    cargo_id = cargo.json()['id']

    criado = cliente.post(URL, json=_dados(a, cargo_id=cargo_id), headers=a.h_admin)
    assert criado.status_code == 201, criado.json()
    corpo = criado.json()
    assert corpo['cargo_nome'] == 'Dentista'
    assert corpo['perfil_nome'] == 'Profissional'
    assert corpo['perfil_acesso_total'] is False
    assert 'senha' not in corpo
    assert 'senha_hash' not in corpo

    lista = cliente.get(URL, headers=a.h_admin).json()
    assert [f['nome'] for f in lista] == ['Admin', 'Dra. Bia', 'Profissional', 'Recepção']
    assert [f['nome'] for f in cliente.get(URL, params={'ativo': False}, headers=a.h_admin).json()] == []

    editado = cliente.put(
        f'{URL}/{corpo["id"]}',
        json=_dados(a, nome='Dra. Beatriz', ativo=False, senha=None),
        headers=a.h_admin,
    )
    assert editado.status_code == 200
    assert editado.json()['ativo'] is False
    with engine_dono.connect() as conexao:
        senha_hash = conexao.execute(
            select(Funcionario.senha_hash).where(Funcionario.id == corpo['id'])
        ).scalar()
    assert verificar_senha('senha-forte-1', senha_hash)[0]  # sem senha na edição, mantém a atual

    cliente.put(f'{URL}/{corpo["id"]}', json=_dados(a, senha='outra-senha-2'), headers=a.h_admin)
    with engine_dono.connect() as conexao:
        senha_hash = conexao.execute(
            select(Funcionario.senha_hash).where(Funcionario.id == corpo['id'])
        ).scalar()
    assert verificar_senha('outra-senha-2', senha_hash)[0]


def test_cadastro_exige_senha_e_email_unico(cliente, lojas):
    a, _ = lojas
    sem_senha = cliente.post(URL, json=_dados(a, senha=None), headers=a.h_admin)
    assert sem_senha.status_code == 422
    assert 'senha' in sem_senha.json()['detail']
    repetido = cliente.post(URL, json=_dados(a, email='PROF@loja-a.com'), headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um funcionário com este e-mail.'
    cor_invalida = cliente.post(URL, json=_dados(a, cor_agenda='azul'), headers=a.h_admin)
    assert cor_invalida.status_code == 422


def test_so_administrador_atribui_ou_altera_administrador(cliente, lojas, engine_dono):
    a, _ = lojas
    gestor = usuario_com(engine_dono, a.loja, {'funcionarios': 'escrita'})
    admin_id = str(a.perfis['Administrador'].id)

    novo_admin = cliente.post(URL, json=_dados(a, perfil_id=admin_id), headers=gestor)
    assert novo_admin.status_code == 403
    assert novo_admin.json()['detail'] == 'Só um Administrador pode atribuir o perfil Administrador.'

    promover = cliente.put(
        f'{URL}/{a.prof.id}', json=_dados(a, email='prof@loja-a.com', perfil_id=admin_id), headers=gestor
    )
    assert promover.status_code == 403

    mexer_no_admin = cliente.put(
        f'{URL}/{a.admin.id}', json=_dados(a, email='admin@loja-a.com', perfil_id=admin_id), headers=gestor
    )
    assert mexer_no_admin.status_code == 403
    assert mexer_no_admin.json()['detail'] == 'Só um Administrador pode alterar outro Administrador.'

    # O gestor pode cadastrar com perfis comuns
    assert cliente.post(URL, json=_dados(a), headers=gestor).status_code == 201
    # O Administrador pode promover
    assert (
        cliente.put(
            f'{URL}/{a.prof.id}',
            json=_dados(a, email='prof@loja-a.com', perfil_id=admin_id),
            headers=a.h_admin,
        ).status_code
        == 200
    )


def test_ultimo_administrador_ativo_nao_e_desativado(cliente, lojas):
    a, _ = lojas
    admin_id = str(a.perfis['Administrador'].id)
    dados_admin = {'nome': 'Admin', 'email': 'admin@loja-a.com', 'perfil_id': admin_id}
    inativar = cliente.put(f'{URL}/{a.admin.id}', json={**dados_admin, 'ativo': False}, headers=a.h_admin)
    assert inativar.status_code == 409
    assert inativar.json()['detail'] == 'A loja precisa de pelo menos um Administrador ativo.'
    rebaixar = cliente.put(
        f'{URL}/{a.admin.id}',
        json={**dados_admin, 'perfil_id': str(a.perfis['Recepção'].id)},
        headers=a.h_admin,
    )
    assert rebaixar.status_code == 409
    # Com outro Administrador ativo, pode
    cliente.put(
        f'{URL}/{a.prof.id}', json=_dados(a, email='prof@loja-a.com', perfil_id=admin_id), headers=a.h_admin
    )
    assert (
        cliente.put(
            f'{URL}/{a.admin.id}', json={**dados_admin, 'ativo': False}, headers=a.h_admin
        ).status_code
        == 200
    )


def test_cargos_crud_e_exclusao_bloqueada_em_uso(cliente, lojas):
    a, _ = lojas
    cargo = cliente.post(CARGOS, json={'nome': 'Dentista'}, headers=a.h_admin).json()
    repetido = cliente.post(CARGOS, json={'nome': 'Dentista'}, headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um cargo com este nome.'
    editado = cliente.put(f'{CARGOS}/{cargo["id"]}', json={'nome': 'Dentista clínico'}, headers=a.h_admin)
    assert editado.json()['nome'] == 'Dentista clínico'
    cliente.post(URL, json=_dados(a, cargo_id=cargo['id']), headers=a.h_admin)
    em_uso = cliente.delete(f'{CARGOS}/{cargo["id"]}', headers=a.h_admin)
    assert em_uso.status_code == 409
    livre = cliente.post(CARGOS, json={'nome': 'Recepcionista'}, headers=a.h_admin).json()
    assert cliente.delete(f'{CARGOS}/{livre["id"]}', headers=a.h_admin).status_code == 204
    assert [c['nome'] for c in cliente.get(CARGOS, headers=a.h_admin).json()] == ['Dentista clínico']


def test_permissoes(cliente, lojas, engine_dono):
    a, _ = lojas
    leitor = usuario_com(engine_dono, a.loja, {'funcionarios': 'leitura'})
    assert cliente.get(URL, headers=leitor).status_code == 200
    assert cliente.get(CARGOS, headers=leitor).status_code == 200
    assert cliente.post(URL, json=_dados(a), headers=leitor).status_code == 403
    assert cliente.post(CARGOS, json={'nome': 'X'}, headers=leitor).status_code == 403
    # Recepção e Profissional: nenhum em funcionários
    for cabecalho in (a.h_recepcao, a.h_prof):
        assert cliente.get(URL, headers=cabecalho).status_code == 403
        assert cliente.get(f'{URL}/{a.admin.id}', headers=cabecalho).status_code == 403
        assert cliente.get(CARGOS, headers=cabecalho).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    url = f'{URL}/{a.prof.id}'
    assert cliente.get(url, headers=b.h_admin).status_code == 404
    assert cliente.put(url, json=_dados(b), headers=b.h_admin).status_code == 404
    assert {f['email'] for f in cliente.get(URL, headers=b.h_admin).json()} == {
        'admin@loja-b.com',
        'prof@loja-b.com',
        'recepcao@loja-b.com',
    }
    # Perfil e cargo de outra loja não podem ser usados
    com_perfil_de_a = cliente.post(
        URL, json=_dados(b, perfil_id=str(a.perfis['Profissional'].id)), headers=b.h_admin
    )
    assert com_perfil_de_a.status_code == 422
    assert com_perfil_de_a.json()['detail'] == 'Perfil não encontrado.'
    cargo_a = cliente.post(CARGOS, json={'nome': 'Dentista'}, headers=a.h_admin).json()
    assert cliente.post(URL, json=_dados(b, cargo_id=cargo_a['id']), headers=b.h_admin).status_code == 422
    assert cliente.put(f'{CARGOS}/{cargo_a["id"]}', json={'nome': 'X'}, headers=b.h_admin).status_code == 404
    assert cliente.delete(f'{CARGOS}/{cargo_a["id"]}', headers=b.h_admin).status_code == 404
