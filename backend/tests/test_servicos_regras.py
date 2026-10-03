"""Serviços: SER-02 (profissional ativo) e exclusão bloqueada com agendamentos futuros."""

from datetime import UTC, datetime, timedelta

from app.models import Agendamento
from tests.fabricas import inserir

URL = '/api/loja/servicos'


def _dados(lt, **extra):
    return {
        'nome': 'Limpeza',
        'duracao_minutos': 60,
        'preco': 200,
        'funcionario_ids': [str(lt.admin.id)],
        **extra,
    }


def _inativo(cliente, lt):
    resposta = cliente.post(
        '/api/loja/funcionarios',
        json={
            'nome': 'Inativo',
            'email': 'ina@loja-a.com',
            'perfil_id': str(lt.perfis['Profissional'].id),
            'senha': 'senha-forte-1',
            'ativo': False,
        },
        headers=lt.h_admin,
    )
    assert resposta.status_code == 201
    return resposta.json()['id']


def test_servico_ativo_precisa_de_profissional_ativo(cliente, lojas):
    a, _ = lojas
    inativo = _inativo(cliente, a)
    so_inativo = cliente.post(URL, json=_dados(a, funcionario_ids=[inativo]), headers=a.h_admin)
    assert so_inativo.status_code == 422
    assert so_inativo.json()['detail'] == 'Selecione ao menos um profissional ativo que realiza o serviço.'
    # Serviço inativo pode ficar só com profissional inativo
    inativo_ok = cliente.post(URL, json=_dados(a, funcionario_ids=[inativo], ativo=False), headers=a.h_admin)
    assert inativo_ok.status_code == 201
    # Ativo com pelo menos um ativo também
    misto = cliente.post(
        URL, json=_dados(a, nome='Avaliação', funcionario_ids=[inativo, str(a.prof.id)]), headers=a.h_admin
    )
    assert misto.status_code == 201
    # Na edição vale o mesmo, e reativar um serviço só com inativos é recusado
    editar = cliente.put(
        f'{URL}/{misto.json()["id"]}',
        json=_dados(a, nome='Avaliação', funcionario_ids=[inativo]),
        headers=a.h_admin,
    )
    assert editar.status_code == 422
    reativar = cliente.put(
        f'{URL}/{inativo_ok.json()["id"]}', json=_dados(a, funcionario_ids=[inativo]), headers=a.h_admin
    )
    assert reativar.status_code == 422


def test_servico_com_agendamento_futuro_nao_e_excluido(cliente, clinica):
    c, h = clinica, clinica.lt.h_admin
    ag = cliente.post('/api/loja/agendamentos', json=c.dados(), headers=h).json()
    bloqueado = cliente.delete(f'{URL}/{c.limpeza}', headers=h)
    assert bloqueado.status_code == 409
    assert bloqueado.json()['detail'].startswith('Este serviço tem agendamentos marcados de agora em diante')
    assert cliente.get(f'{URL}/{c.limpeza}', headers=h).status_code == 200
    # Serviço sem agendamentos é excluído
    assert cliente.delete(f'{URL}/{c.avaliacao}', headers=h).status_code == 204
    # Cancelado não segura a exclusão
    cancelar = cliente.post(
        f'/api/loja/agendamentos/{ag["id"]}/status',
        json={'status': 'cancelado', 'motivo_cancelamento': 'Desistiu'},
        headers=h,
    )
    assert cancelar.status_code == 200
    assert cliente.delete(f'{URL}/{c.limpeza}', headers=h).status_code == 204
    # O agendamento cancelado ainda pode ser reaberto com o serviço que já tinha
    reabrir = cliente.put(f'/api/loja/agendamentos/{ag["id"]}', json=c.dados(status='agendado'), headers=h)
    assert reabrir.status_code == 200, reabrir.json()
    assert reabrir.json()['servico_nome'] == 'Limpeza'
    # Trocar para um serviço excluído continua recusado
    trocar = cliente.put(
        f'/api/loja/agendamentos/{ag["id"]}', json=c.dados(servico_id=c.avaliacao), headers=h
    )
    assert trocar.status_code == 422
    assert trocar.json()['detail'] == 'Serviço não encontrado.'


def test_agendamento_passado_nao_segura_a_exclusao_do_servico(cliente, clinica, engine_dono):
    c = clinica
    inicio = datetime.now(UTC) - timedelta(days=2)
    inserir(
        engine_dono,
        Agendamento(
            loja_id=c.lt.loja.id,
            cliente_id=c.maria,
            servico_id=c.avaliacao,
            funcionario_id=c.lt.admin.id,
            inicio=inicio,
            fim=inicio + timedelta(minutes=30),
        ),
    )
    assert cliente.delete(f'{URL}/{c.avaliacao}', headers=c.lt.h_admin).status_code == 204


def test_exclusao_respeita_permissao_e_loja(cliente, clinica, lojas):
    _, b = lojas
    assert cliente.delete(f'{URL}/{clinica.limpeza}', headers=b.h_admin).status_code == 404
    assert cliente.delete(f'{URL}/{clinica.limpeza}', headers=clinica.lt.h_recepcao).status_code == 403
