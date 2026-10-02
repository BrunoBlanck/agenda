"""Perfis e horários: perfis, níveis, catálogo de recursos, jornada e bloqueios."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import BloqueioAgenda, Perfil, PerfilHorario
from tests.fabricas import cabecalho, criar_funcionario, mudar_modulo, usuario_com

PERFIS = '/api/loja/perfis'
HORARIOS = '/api/loja/horarios'
BLOQUEIOS = '/api/loja/bloqueios'


def _faixa(cliente, cab, perfil_id, dia=1, ini='08:00', fim='12:00'):
    return cliente.post(
        f'{PERFIS}/{perfil_id}/horarios',
        json={'dia_semana': dia, 'hora_inicio': ini, 'hora_fim': fim},
        headers=cab,
    )


# --- Recursos ------------------------------------------------------------------------------------


def test_catalogo_de_recursos_mostra_modulo_desligado(cliente, lojas, engine_dono):
    a, _ = lojas
    mudar_modulo(engine_dono, a.loja.id, 'materiais', habilitado=False)
    recursos = cliente.get('/api/loja/recursos', headers=a.h_prof).json()
    assert len(recursos) == 12
    por_codigo = {r['codigo']: r for r in recursos}
    assert por_codigo['materiais']['modulo'] == 'materiais'
    assert por_codigo['materiais']['modulo_ativo'] is False
    assert por_codigo['clientes']['modulo_ativo'] is True


# --- Perfis --------------------------------------------------------------------------------------


def test_lista_de_perfis_e_quem_ve_os_niveis(cliente, lojas):
    a, _ = lojas
    perfis = cliente.get(PERFIS, headers=a.h_admin).json()
    assert [p['nome'] for p in perfis] == ['Administrador', 'Profissional', 'Recepção']
    admin, prof, recepcao = perfis
    assert admin['acesso_total'] is True
    assert recepcao['acessos']['agenda_equipe'] == 'escrita'
    assert recepcao['acessos']['funcionarios'] == 'nenhum'
    assert [f['nome'] for f in prof['funcionarios']] == ['Profissional']
    assert prof['sem_jornada'] is True

    # Recepção: leitura em Horários e bloqueios, nenhum em Perfis de acesso -> vê a lista sem os níveis
    da_recepcao = cliente.get(PERFIS, headers=a.h_recepcao)
    assert da_recepcao.status_code == 200
    assert all(p['acessos'] is None for p in da_recepcao.json())
    # Profissional: nenhum nos três recursos
    assert cliente.get(PERFIS, headers=a.h_prof).status_code == 403


def test_lista_de_perfis_para_quem_cadastra_funcionarios(cliente, lojas, engine_dono):
    a, _ = lojas
    gestor = usuario_com(engine_dono, a.loja, {'funcionarios': 'escrita'})
    resposta = cliente.get(PERFIS, headers=gestor)
    assert resposta.status_code == 200
    assert resposta.json()[0]['acessos'] is None


def test_criar_perfil_copiando_niveis_e_jornada(cliente, lojas):
    a, _ = lojas
    recepcao_id = a.perfis['Recepção'].id
    _faixa(cliente, a.h_admin, recepcao_id, dia=1)
    _faixa(cliente, a.h_admin, recepcao_id, dia=2, ini='13:00', fim='18:00')

    criado = cliente.post(
        PERFIS, json={'nome': 'Recepção · tarde', 'copiar_de': str(recepcao_id)}, headers=a.h_admin
    )
    assert criado.status_code == 201, criado.json()
    corpo = criado.json()
    assert corpo['padrao'] is False
    assert corpo['acessos']['agenda_equipe'] == 'escrita'
    assert corpo['acessos']['config_agendamentos'] == 'leitura'
    assert corpo['sem_jornada'] is False
    faixas = cliente.get(HORARIOS, params={'perfil_id': corpo['id']}, headers=a.h_admin).json()
    assert [(f['dia_semana'], f['hora_inicio'], f['hora_fim']) for f in faixas] == [
        (1, '08:00:00', '12:00:00'),
        (2, '13:00:00', '18:00:00'),
    ]

    do_zero = cliente.post(PERFIS, json={'nome': 'Estagiário'}, headers=a.h_admin).json()
    assert set(do_zero['acessos'].values()) == {'nenhum'}
    assert len(do_zero['acessos']) == 12

    repetido = cliente.post(PERFIS, json={'nome': 'Estagiário'}, headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um perfil com este nome.'


def test_renomear_e_definir_niveis(cliente, lojas, engine_dono):
    a, _ = lojas
    novo = cliente.post(PERFIS, json={'nome': 'Estagiário'}, headers=a.h_admin).json()
    renomeado = cliente.put(f'{PERFIS}/{novo["id"]}', json={'nome': 'Estagiária'}, headers=a.h_admin)
    assert renomeado.json()['nome'] == 'Estagiária'
    padrao = cliente.put(f'{PERFIS}/{a.perfis["Recepção"].id}', json={'nome': 'Balcão'}, headers=a.h_admin)
    assert padrao.status_code == 409

    acessos = cliente.put(
        f'{PERFIS}/{novo["id"]}/acessos', json={'acessos': {'clientes': 'leitura'}}, headers=a.h_admin
    )
    assert acessos.status_code == 200
    assert acessos.json()['acessos']['clientes'] == 'leitura'
    # O nível vale de verdade para quem está no perfil
    with engine_dono.connect() as conexao:
        perfil = conexao.execute(select(Perfil).where(Perfil.id == novo['id'])).one()
    estagiaria = criar_funcionario(engine_dono, a.loja, perfil, 'estagiaria@a.com')
    assert (
        cliente.get('/api/loja/eu', headers=cabecalho(estagiaria)).json()['acessos']['clientes'] == 'leitura'
    )
    assert cliente.get('/api/loja/clientes', headers=cabecalho(estagiaria)).status_code == 200

    admin = cliente.put(
        f'{PERFIS}/{a.perfis["Administrador"].id}/acessos',
        json={'acessos': {'clientes': 'leitura'}},
        headers=a.h_admin,
    )
    assert admin.status_code == 409
    desconhecido = cliente.put(
        f'{PERFIS}/{novo["id"]}/acessos', json={'acessos': {'xpto': 'leitura'}}, headers=a.h_admin
    )
    assert desconhecido.status_code == 422
    nivel_invalido = cliente.put(
        f'{PERFIS}/{novo["id"]}/acessos', json={'acessos': {'clientes': 'total'}}, headers=a.h_admin
    )
    assert nivel_invalido.status_code == 422


def test_excluir_perfil(cliente, lojas, engine_dono):
    a, _ = lojas
    assert cliente.delete(f'{PERFIS}/{a.perfis["Recepção"].id}', headers=a.h_admin).status_code == 409
    novo = cliente.post(PERFIS, json={'nome': 'Temporário'}, headers=a.h_admin).json()
    _faixa(cliente, a.h_admin, novo['id'])
    cliente.post(
        BLOQUEIOS,
        json={'perfil_id': novo['id'], 'inicio': '2030-01-01T00:00', 'fim': '2030-01-02T00:00'},
        headers=a.h_admin,
    )
    funcionario = cliente.post(
        '/api/loja/funcionarios',
        json={'nome': 'Temp', 'email': 'temp@a.com', 'perfil_id': novo['id'], 'senha': 'senha-forte'},
        headers=a.h_admin,
    ).json()
    com_funcionario = cliente.delete(f'{PERFIS}/{novo["id"]}', headers=a.h_admin)
    assert com_funcionario.status_code == 409
    assert 'Troque o perfil' in com_funcionario.json()['detail']

    cliente.put(
        f'/api/loja/funcionarios/{funcionario["id"]}',
        json={'nome': 'Temp', 'email': 'temp@a.com', 'perfil_id': str(a.perfis['Profissional'].id)},
        headers=a.h_admin,
    )
    assert cliente.delete(f'{PERFIS}/{novo["id"]}', headers=a.h_admin).status_code == 204
    assert cliente.get(f'{PERFIS}/{novo["id"]}', headers=a.h_admin).status_code == 404
    with engine_dono.connect() as conexao:
        faixas = conexao.execute(
            select(PerfilHorario.excluido_em).where(PerfilHorario.perfil_id == novo['id'])
        ).all()
        bloqueios = conexao.execute(
            select(BloqueioAgenda.excluido_em).where(BloqueioAgenda.perfil_id == novo['id'])
        ).all()
    assert faixas
    assert all(f.excluido_em is not None for f in faixas)
    assert all(b.excluido_em is not None for b in bloqueios)


def test_permissoes_de_perfis(cliente, lojas, engine_dono):
    a, _ = lojas
    leitor = usuario_com(engine_dono, a.loja, {'perfis_acesso': 'leitura'})
    assert cliente.get(PERFIS, headers=leitor).json()[1]['acessos'] is not None
    assert cliente.post(PERFIS, json={'nome': 'X'}, headers=leitor).status_code == 403
    recepcao_id = a.perfis['Recepção'].id
    assert (
        cliente.put(f'{PERFIS}/{recepcao_id}/acessos', json={'acessos': {}}, headers=leitor).status_code
        == 403
    )
    assert cliente.delete(f'{PERFIS}/{recepcao_id}', headers=leitor).status_code == 403


# --- Jornada -------------------------------------------------------------------------------------


def test_jornada_faixas_e_sobreposicao(cliente, lojas):
    a, _ = lojas
    prof_id = a.perfis['Profissional'].id
    manha = _faixa(cliente, a.h_admin, prof_id, ini='08:00', fim='12:00')
    assert manha.status_code == 201
    assert manha.json()['atualizado_por_nome'] == 'Admin'
    assert _faixa(cliente, a.h_admin, prof_id, ini='13:00', fim='18:00').status_code == 201
    sobreposta = _faixa(cliente, a.h_admin, prof_id, ini='11:00', fim='14:00')
    assert sobreposta.status_code == 409
    assert sobreposta.json()['detail'] == 'Essa faixa se sobrepõe a outra do mesmo dia.'
    invertida = _faixa(cliente, a.h_admin, prof_id, ini='18:00', fim='17:00')
    assert invertida.status_code == 422
    assert invertida.json()['erros'][0]['mensagem'] == 'O fim deve ser depois do início.'
    assert _faixa(cliente, a.h_admin, prof_id, dia=7).status_code == 422

    assert cliente.delete(f'{HORARIOS}/{manha.json()["id"]}', headers=a.h_admin).status_code == 204
    restantes = cliente.get(HORARIOS, params={'perfil_id': str(prof_id)}, headers=a.h_admin).json()
    assert [f['hora_inicio'] for f in restantes] == ['13:00:00']
    # Depois de removida, a faixa pode ser cadastrada de novo
    assert _faixa(cliente, a.h_admin, prof_id, ini='08:00', fim='12:00').status_code == 201


def test_permissoes_de_jornada(cliente, lojas):
    a, _ = lojas
    prof_id = a.perfis['Profissional'].id
    # Recepção: leitura em Horários e bloqueios
    assert cliente.get(HORARIOS, headers=a.h_recepcao).status_code == 200
    escrita = _faixa(cliente, a.h_recepcao, prof_id)
    assert escrita.status_code == 403
    assert escrita.json()['detail'] == 'Você só tem permissão de leitura aqui.'
    # Profissional: nenhum
    assert cliente.get(HORARIOS, headers=a.h_prof).status_code == 403
    assert cliente.get(BLOQUEIOS, headers=a.h_prof).status_code == 403


# --- Bloqueios -----------------------------------------------------------------------------------


def test_bloqueios_da_loja_do_perfil_e_do_funcionario(cliente, lojas, engine_dono):
    a, _ = lojas
    prof_perfil = a.perfis['Profissional'].id
    feriado = cliente.post(
        BLOQUEIOS,
        json={'inicio': '2030-12-25T00:00', 'fim': '2030-12-26T00:00', 'motivo': 'Natal'},
        headers=a.h_admin,
    )
    assert feriado.status_code == 201, feriado.json()
    corpo = feriado.json()
    assert corpo['alvo'] == 'loja'
    assert corpo['quem'] is None
    assert corpo['inicio'] == '2030-12-25T00:00:00-03:00'  # sem fuso = horário da loja
    with engine_dono.connect() as conexao:
        inicio = conexao.execute(
            select(BloqueioAgenda.inicio).where(BloqueioAgenda.id == corpo['id'])
        ).scalar()
    assert inicio == datetime(2030, 12, 25, 3, tzinfo=UTC)

    do_perfil = cliente.post(
        BLOQUEIOS,
        json={'perfil_id': str(prof_perfil), 'inicio': '2030-12-20T08:00', 'fim': '2030-12-20T12:00'},
        headers=a.h_admin,
    ).json()
    assert do_perfil['alvo'] == 'perfil'
    assert do_perfil['quem'] == 'Perfil Profissional'
    ferias = cliente.post(
        BLOQUEIOS,
        json={
            'funcionario_id': str(a.prof.id),
            'inicio': '2030-12-10T00:00:00Z',
            'fim': '2030-12-15T00:00:00Z',
            'motivo': 'Férias',
        },
        headers=a.h_admin,
    ).json()
    assert ferias['quem'] == 'Profissional'
    da_recepcao = cliente.post(
        BLOQUEIOS,
        json={'funcionario_id': str(a.recepcao.id), 'inicio': '2030-12-11T08:00', 'fim': '2030-12-11T09:00'},
        headers=a.h_admin,
    ).json()

    def ids(**params):
        return [b['id'] for b in cliente.get(BLOQUEIOS, params=params, headers=a.h_admin).json()]

    assert ids() == [ferias['id'], da_recepcao['id'], do_perfil['id'], corpo['id']]
    assert ids(perfil_id=str(prof_perfil)) == [ferias['id'], do_perfil['id'], corpo['id']]
    assert ids(funcionario_id=str(a.recepcao.id)) == [da_recepcao['id'], corpo['id']]
    assert ids(inicio='2030-12-19', fim='2030-12-24') == [do_perfil['id']]

    assert cliente.delete(f'{BLOQUEIOS}/{do_perfil["id"]}', headers=a.h_admin).status_code == 204
    assert do_perfil['id'] not in ids()


def test_bloqueio_invalido(cliente, lojas):
    a, _ = lojas
    dois_alvos = cliente.post(
        BLOQUEIOS,
        json={
            'perfil_id': str(a.perfis['Profissional'].id),
            'funcionario_id': str(a.prof.id),
            'inicio': '2030-01-01T08:00',
            'fim': '2030-01-01T09:00',
        },
        headers=a.h_admin,
    )
    assert dois_alvos.status_code == 422
    assert dois_alvos.json()['erros'][0]['mensagem'] == 'Escolha um perfil ou um funcionário, não os dois.'
    invertido = cliente.post(
        BLOQUEIOS, json={'inicio': '2030-01-01T09:00', 'fim': '2030-01-01T08:00'}, headers=a.h_admin
    )
    assert invertido.status_code == 422
    assert invertido.json()['detail'] == 'O fim do bloqueio deve ser depois do início.'
    leitura = cliente.post(
        BLOQUEIOS, json={'inicio': '2030-01-01T08:00', 'fim': '2030-01-01T09:00'}, headers=a.h_recepcao
    )
    assert leitura.status_code == 403


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    perfil_a = a.perfis['Profissional'].id
    faixa_a = _faixa(cliente, a.h_admin, perfil_a).json()
    bloqueio_a = cliente.post(
        BLOQUEIOS,
        json={'perfil_id': str(perfil_a), 'inicio': '2030-01-01T08:00', 'fim': '2030-01-01T09:00'},
        headers=a.h_admin,
    ).json()

    assert cliente.get(f'{PERFIS}/{perfil_a}', headers=b.h_admin).status_code == 404
    assert cliente.put(f'{PERFIS}/{perfil_a}', json={'nome': 'X'}, headers=b.h_admin).status_code == 404
    assert (
        cliente.put(f'{PERFIS}/{perfil_a}/acessos', json={'acessos': {}}, headers=b.h_admin).status_code
        == 404
    )
    assert cliente.delete(f'{PERFIS}/{perfil_a}', headers=b.h_admin).status_code == 404
    assert _faixa(cliente, b.h_admin, perfil_a).status_code == 404
    assert cliente.delete(f'{HORARIOS}/{faixa_a["id"]}', headers=b.h_admin).status_code == 404
    assert cliente.delete(f'{BLOQUEIOS}/{bloqueio_a["id"]}', headers=b.h_admin).status_code == 404
    assert (
        cliente.post(
            PERFIS, json={'nome': 'Cópia', 'copiar_de': str(perfil_a)}, headers=b.h_admin
        ).status_code
        == 404
    )
    alheio = cliente.post(
        BLOQUEIOS,
        json={'funcionario_id': str(a.prof.id), 'inicio': '2030-01-01T08:00', 'fim': '2030-01-01T09:00'},
        headers=b.h_admin,
    )
    assert alheio.status_code == 404
    assert cliente.get(HORARIOS, headers=b.h_admin).json() == []
    assert cliente.get(BLOQUEIOS, headers=b.h_admin).json() == []
    assert {p['nome'] for p in cliente.get(PERFIS, headers=b.h_admin).json()} == {
        'Administrador',
        'Recepção',
        'Profissional',
    }
