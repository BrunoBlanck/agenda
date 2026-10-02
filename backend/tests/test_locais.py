"""Locais e rótulos do menu: CRUD, permissões, módulo desligado e isolamento entre lojas."""

from datetime import UTC, datetime, timedelta

from app.models import Agendamento, Cliente, Servico, ServicoLocal
from app.models.enums import StatusAgendamento
from tests.fabricas import inserir, mudar_modulo, usuario_com

URL = '/api/loja/locais'
ROTULOS = '/api/loja/locais/rotulos'


def test_crud_de_locais(cliente, lojas):
    a, _ = lojas
    sala = cliente.post(URL, json={'nome': 'Sala 101', 'descricao': 'Piano de cauda'}, headers=a.h_admin)
    assert sala.status_code == 201, sala.json()
    assert sala.json()['tipo'] == 'presencial'
    assert sala.json()['atualizado_por_nome'] == 'Admin'

    online = cliente.post(
        URL,
        json={'nome': 'Online · Ana', 'tipo': 'online', 'link_padrao': 'https://meet.google.com/abc'},
        headers=a.h_admin,
    ).json()
    assert online['link_padrao'] == 'https://meet.google.com/abc'
    # Link só vale para local online: ao virar presencial, some
    editado = cliente.put(
        f'{URL}/{online["id"]}',
        json={'nome': 'Online · Ana', 'tipo': 'presencial', 'link_padrao': 'https://meet.google.com/abc'},
        headers=a.h_admin,
    ).json()
    assert editado['link_padrao'] is None

    link_ruim = cliente.post(
        URL, json={'nome': 'Zoom', 'tipo': 'online', 'link_padrao': 'zoom'}, headers=a.h_admin
    )
    assert link_ruim.status_code == 422
    assert link_ruim.json()['erros'][0]['mensagem'] == 'Informe um link válido (https://...).'
    repetido = cliente.post(URL, json={'nome': 'Sala 101'}, headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Já existe um local com este nome.'

    inativo = cliente.put(
        f'{URL}/{sala.json()["id"]}', json={'nome': 'Sala 101', 'ativo': False}, headers=a.h_admin
    )
    assert inativo.json()['ativo'] is False
    assert [loc['nome'] for loc in cliente.get(URL, params={'ativo': True}, headers=a.h_admin).json()] == [
        'Online · Ana'
    ]
    assert len(cliente.get(URL, headers=a.h_admin).json()) == 2


def test_servicos_vinculados_e_proximos_agendamentos(cliente, lojas, engine_dono):
    a, _ = lojas
    sala = cliente.post(URL, json={'nome': 'Sala 1'}, headers=a.h_admin).json()
    servico = inserir(engine_dono, Servico(loja_id=a.loja.id, nome='Limpeza', duracao_minutos=30))
    inserir(engine_dono, ServicoLocal(loja_id=a.loja.id, servico_id=servico.id, local_id=sala['id']))
    pessoa = inserir(engine_dono, Cliente(loja_id=a.loja.id, nome='Ana', sobrenome='Lima', telefone='1'))
    amanha = datetime.now(UTC) + timedelta(days=1)
    for horas, situacao in (
        (0, StatusAgendamento.agendado),
        (1, StatusAgendamento.cancelado),
        (-48, StatusAgendamento.concluido),
    ):
        inicio = amanha + timedelta(hours=horas)
        inserir(
            engine_dono,
            Agendamento(
                loja_id=a.loja.id,
                cliente_id=pessoa.id,
                funcionario_id=a.prof.id,
                local_id=sala['id'],
                inicio=inicio,
                fim=inicio + timedelta(minutes=30),
                status=situacao,
                motivo_cancelamento='x' if situacao == StatusAgendamento.cancelado else None,
            ),
        )
    obtido = cliente.get(f'{URL}/{sala["id"]}', headers=a.h_admin).json()
    assert obtido['servicos'] == [{'id': str(servico.id), 'nome': 'Limpeza'}]
    assert obtido['proximos_agendamentos'] == 1  # cancelado e passado não contam
    # Sem o módulo Serviços, a lista de serviços não aparece
    mudar_modulo(engine_dono, a.loja.id, 'servicos', habilitado=False)
    assert cliente.get(f'{URL}/{sala["id"]}', headers=a.h_admin).json()['servicos'] == []


def test_rotulos_do_menu(cliente, lojas):
    a, _ = lojas
    assert cliente.get(ROTULOS, headers=a.h_admin).json()['rotulo_local'] == 'Local'
    novo = cliente.put(
        ROTULOS, json={'rotulo_local': ' Sala ', 'rotulo_local_plural': 'Salas'}, headers=a.h_admin
    )
    assert novo.status_code == 200
    assert novo.json()['rotulo_local'] == 'Sala'
    assert novo.json()['atualizado_por_nome'] == 'Admin'
    eu = cliente.get('/api/loja/eu', headers=a.h_prof).json()
    assert (eu['loja']['rotulo_local'], eu['loja']['rotulo_local_plural']) == ('Sala', 'Salas')
    vazio = cliente.put(ROTULOS, json={'rotulo_local': '', 'rotulo_local_plural': 'Salas'}, headers=a.h_admin)
    assert vazio.status_code == 422


def test_permissoes_e_modulo_desligado(cliente, lojas, engine_dono):
    a, _ = lojas
    sala = cliente.post(URL, json={'nome': 'Sala 1'}, headers=a.h_admin).json()
    # Recepção: leitura em locais
    assert cliente.get(URL, headers=a.h_recepcao).status_code == 200
    assert cliente.get(ROTULOS, headers=a.h_recepcao).status_code == 200
    assert cliente.post(URL, json={'nome': 'X'}, headers=a.h_recepcao).status_code == 403
    assert cliente.put(f'{URL}/{sala["id"]}', json={'nome': 'X'}, headers=a.h_recepcao).status_code == 403
    assert (
        cliente.put(
            ROTULOS, json={'rotulo_local': 'A', 'rotulo_local_plural': 'B'}, headers=a.h_recepcao
        ).status_code
        == 403
    )
    # Profissional: nenhum
    assert cliente.get(URL, headers=a.h_prof).status_code == 403
    assert cliente.get(f'{URL}/{sala["id"]}', headers=a.h_prof).status_code == 403
    # Módulo desligado: nem o Administrador acessa
    mudar_modulo(engine_dono, a.loja.id, 'locais', habilitado=False)
    desligado = cliente.get(URL, headers=a.h_admin)
    assert desligado.status_code == 403
    assert desligado.json()['detail'] == 'Este módulo não está ativo na sua loja.'
    escritor = usuario_com(engine_dono, a.loja, {'locais': 'escrita'})
    assert cliente.post(URL, json={'nome': 'Y'}, headers=escritor).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    sala_a = cliente.post(URL, json={'nome': 'Sala 1'}, headers=a.h_admin).json()
    assert cliente.get(f'{URL}/{sala_a["id"]}', headers=b.h_admin).status_code == 404
    assert (
        cliente.put(f'{URL}/{sala_a["id"]}', json={'nome': 'Invadida'}, headers=b.h_admin).status_code == 404
    )
    assert cliente.get(URL, headers=b.h_admin).json() == []
    # Mesmo nome em outra loja é permitido
    assert cliente.post(URL, json={'nome': 'Sala 1'}, headers=b.h_admin).status_code == 201
    cliente.put(
        ROTULOS, json={'rotulo_local': 'Cadeira', 'rotulo_local_plural': 'Cadeiras'}, headers=b.h_admin
    )
    assert cliente.get(ROTULOS, headers=a.h_admin).json()['rotulo_local'] == 'Local'
    assert cliente.get(f'{URL}/{sala_a["id"]}', headers=a.h_admin).json()['nome'] == 'Sala 1'
