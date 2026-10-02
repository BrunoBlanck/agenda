"""Agenda: visão do período (semana/mês/dia) com agendamentos, jornada e bloqueios."""

from tests.clinica import SEGUNDA
from tests.fabricas import usuario_com

URL = '/api/loja/agenda'
AGENDAMENTOS = '/api/loja/agendamentos'


def _agendar(cliente, c, **extra):
    resposta = cliente.post(AGENDAMENTOS, json=c.dados(**extra), headers=c.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def _bloquear(cliente, c, **corpo):
    resposta = cliente.post('/api/loja/bloqueios', json=corpo, headers=c.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_semana_da_equipe(cliente, clinica):
    c = clinica
    do_prof = _agendar(cliente, c)
    do_admin = _agendar(cliente, c, funcionario_id=str(c.lt.admin.id), local_id=c.online)
    fora = _agendar(cliente, c, inicio='2030-01-21T09:00')
    feriado = _bloquear(cliente, c, inicio='2030-01-08T00:00', fim='2030-01-09T00:00', motivo='Feriado')
    ferias = _bloquear(
        cliente, c, funcionario_id=str(c.lt.prof.id), inicio='2030-01-10T00:00', fim='2030-01-12T00:00'
    )

    semana = cliente.get(URL, params={'inicio': '2030-01-06', 'fim': '2030-01-12'}, headers=c.lt.h_recepcao)
    assert semana.status_code == 200, semana.json()
    corpo = semana.json()
    assert corpo['so_propria'] is False
    assert {a['id'] for a in corpo['agendamentos']} == {do_prof['id'], do_admin['id']}
    assert fora['id'] not in {a['id'] for a in corpo['agendamentos']}
    assert [p['nome'] for p in corpo['profissionais']] == ['Admin', 'Profissional', 'Recepção']
    assert len(corpo['jornadas']) == 6  # 2 faixas x 3 perfis
    assert [b['id'] for b in corpo['bloqueios']] == [feriado['id'], ferias['id']]
    assert corpo['bloqueios'][1]['quem'] == 'Profissional'

    # Filtrando pelo Administrador: só os dele, só a jornada do perfil dele, sem as férias do outro
    do_filtro = cliente.get(
        URL,
        params={'inicio': '2030-01-06', 'fim': '2030-01-12', 'funcionario_id': str(c.lt.admin.id)},
        headers=c.lt.h_recepcao,
    ).json()
    assert [a['id'] for a in do_filtro['agendamentos']] == [do_admin['id']]
    assert [p['nome'] for p in do_filtro['profissionais']] == ['Admin']
    assert {j['perfil_id'] for j in do_filtro['jornadas']} == {str(c.lt.perfis['Administrador'].id)}
    assert [b['id'] for b in do_filtro['bloqueios']] == [feriado['id']]


def test_painel_do_dia(cliente, clinica):
    c = clinica
    das_9 = _agendar(cliente, c)
    das_14 = _agendar(cliente, c, inicio=f'{SEGUNDA}T14:00')
    _agendar(cliente, c, inicio='2030-01-14T09:00')
    dia = cliente.get(URL, params={'inicio': SEGUNDA}, headers=c.lt.h_admin).json()
    assert (dia['inicio'], dia['fim']) == (SEGUNDA, SEGUNDA)
    assert [a['id'] for a in dia['agendamentos']] == [das_9['id'], das_14['id']]
    assert dia['agendamentos'][0]['cor_agenda'] is None
    assert dia['agendamentos'][0]['servico_nome'] == 'Limpeza'


def test_profissional_ve_so_a_propria_agenda(cliente, clinica):
    c = clinica
    proprio = _agendar(cliente, c)
    _agendar(cliente, c, funcionario_id=str(c.lt.admin.id), local_id=c.online)
    _bloquear(
        cliente, c, funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T13:00', fim=f'{SEGUNDA}T14:00'
    )
    # Mesmo pedindo a agenda de outro, recebe a própria
    corpo = cliente.get(
        URL, params={'inicio': SEGUNDA, 'funcionario_id': str(c.lt.admin.id)}, headers=c.lt.h_prof
    ).json()
    assert corpo['so_propria'] is True
    assert [a['id'] for a in corpo['agendamentos']] == [proprio['id']]
    assert [p['nome'] for p in corpo['profissionais']] == ['Profissional']
    assert {j['perfil_id'] for j in corpo['jornadas']} == {str(c.lt.perfis['Profissional'].id)}
    assert corpo['bloqueios'] == []  # o bloqueio do Administrador não aparece


def test_periodo_invalido_e_permissoes(cliente, clinica, engine_dono):
    c = clinica
    assert (
        cliente.get(
            URL, params={'inicio': '2030-01-10', 'fim': '2030-01-01'}, headers=c.lt.h_admin
        ).status_code
        == 422
    )
    longo = cliente.get(URL, params={'inicio': '2030-01-01', 'fim': '2030-06-01'}, headers=c.lt.h_admin)
    assert longo.status_code == 422
    assert longo.json()['detail'] == 'O período pode ter no máximo 62 dias.'
    assert cliente.get(URL, headers=c.lt.h_admin).status_code == 422  # início obrigatório
    sem_agenda = usuario_com(engine_dono, c.lt.loja, {'clientes': 'leitura'})
    assert cliente.get(URL, params={'inicio': SEGUNDA}, headers=sem_agenda).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas, clinica):
    c = clinica
    _, b = lojas
    _agendar(cliente, c)
    _bloquear(cliente, c, inicio=f'{SEGUNDA}T00:00', fim=f'{SEGUNDA}T01:00')
    da_b = cliente.get(URL, params={'inicio': SEGUNDA}, headers=b.h_admin).json()
    assert da_b['agendamentos'] == []
    assert da_b['bloqueios'] == []
    assert da_b['jornadas'] == []
    assert {p['nome'] for p in da_b['profissionais']} == {'Admin', 'Profissional', 'Recepção'}
    assert {p['id'] for p in da_b['profissionais']}.isdisjoint({str(c.lt.admin.id), str(c.lt.prof.id)})
    filtro_de_a = cliente.get(
        URL, params={'inicio': SEGUNDA, 'funcionario_id': str(c.lt.prof.id)}, headers=b.h_admin
    )
    assert filtro_de_a.status_code == 404
