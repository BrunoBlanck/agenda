"""Serviços vinculados pela tela de Locais (LOC-06): PUT/POST /locais com servico_ids e GET /locais/opcoes.

O vínculo é o mesmo de servico_locais editado na tela de Serviços e restringe o serviço, não o local
(SER-04 / AGE-12): serviço sem nenhum local vinculado aceita qualquer local.
"""

from uuid import uuid4

from sqlalchemy import select, text

from app.models import Auditoria, ServicoLocal
from tests.clinica import SEGUNDA
from tests.fabricas import mudar_modulo, usuario_com

URL = '/api/loja/locais'
OPCOES = f'{URL}/opcoes'
AGENDAMENTOS = '/api/loja/agendamentos'
NAO_PERMITIDO = 'Este local não é permitido para o serviço escolhido.'


def _put(cliente, cab, local_id, nome, **extra):
    return cliente.put(f'{URL}/{local_id}', json={'nome': nome, **extra}, headers=cab)


def _servicos(corpo):
    return [(s['nome'], s['ativo']) for s in corpo['servicos']]


def _opcoes(cliente, cab):
    return {s['nome']: s for s in cliente.get(OPCOES, headers=cab).json()['servicos']}


def _vinculos(engine, local_id) -> list[tuple]:
    with engine.connect() as conexao:
        return conexao.execute(
            select(ServicoLocal.servico_id, ServicoLocal.excluido_em).where(ServicoLocal.local_id == local_id)
        ).all()


def test_vincular_desvincular_e_religar_restaura_a_linha(cliente, clinica, engine_dono):
    c, h = clinica, clinica.lt.h_admin
    # Ids repetidos são deduplicados
    vinculado = _put(cliente, h, c.sala2, 'Sala 2', servico_ids=[c.limpeza, c.avaliacao, c.limpeza])
    assert vinculado.status_code == 200, vinculado.json()
    assert _servicos(vinculado.json()) == [('Avaliação', True), ('Limpeza', True)]
    assert [s['id'] for s in vinculado.json()['servicos']] == [c.avaliacao, c.limpeza]

    so_limpeza = _put(cliente, h, c.sala2, 'Sala 2', servico_ids=[c.limpeza]).json()
    assert _servicos(so_limpeza) == [('Limpeza', True)]
    religado = _put(cliente, h, c.sala2, 'Sala 2', servico_ids=[c.limpeza, c.avaliacao]).json()
    assert _servicos(religado) == [('Avaliação', True), ('Limpeza', True)]

    linhas = [v for v in _vinculos(engine_dono, c.sala2) if str(v.servico_id) == c.avaliacao]
    assert len(linhas) == 1  # a mesma linha, sem duplicar
    assert linhas[0].excluido_em is None
    with engine_dono.connect() as conexao:
        operacoes = (
            conexao.execute(
                select(Auditoria.operacao)
                .where(
                    Auditoria.tabela == 'servico_locais', Auditoria.registro_id == f'{c.avaliacao}:{c.sala2}'
                )
                .order_by(Auditoria.id)
            )
            .scalars()
            .all()
        )
    assert operacoes == ['inserir', 'excluir', 'restaurar']


def test_servico_ids_ausente_ou_nulo_nao_mexe_e_lista_vazia_remove(cliente, clinica):
    c, h = clinica, clinica.lt.h_admin
    sem_campo = _put(cliente, h, c.sala1, 'Sala Um', descricao='Janela')
    assert sem_campo.status_code == 200
    assert sem_campo.json()['nome'] == 'Sala Um'
    assert _servicos(sem_campo.json()) == [('Limpeza', True)]
    nulo = _put(cliente, h, c.sala1, 'Sala Um', servico_ids=None).json()
    assert _servicos(nulo) == [('Limpeza', True)]

    vazio = _put(cliente, h, c.sala1, 'Sala Um', servico_ids=[]).json()
    assert vazio['servicos'] == []
    # O mesmo vínculo some na tela de Serviços (os vínculos com outros locais continuam)
    limpeza = cliente.get(f'/api/loja/servicos/{c.limpeza}', headers=h).json()
    assert limpeza['local_ids'] == [c.online]


def test_cadastrar_local_com_servicos_e_servico_inativo(cliente, clinica):
    c, h = clinica, clinica.lt.h_admin
    antigo = cliente.post(
        '/api/loja/servicos',
        json={'nome': 'Antigo', 'duracao_minutos': 30, 'ativo': False},
        headers=h,
    ).json()['id']
    criado = cliente.post(URL, json={'nome': 'Sala 3', 'servico_ids': [antigo, c.avaliacao]}, headers=h)
    assert criado.status_code == 201, criado.json()
    assert _servicos(criado.json()) == [('Antigo', False), ('Avaliação', True)]
    # Local inativo também pode ter os vínculos editados (LOC-02)
    inativo = _put(cliente, h, criado.json()['id'], 'Sala 3', ativo=False, servico_ids=[c.limpeza]).json()
    assert inativo['ativo'] is False
    assert _servicos(inativo) == [('Limpeza', True)]
    assert len(cliente.get(URL, headers=h).json()) == 4


def test_vinculos_pelo_local_mudam_as_regras_do_agendamento(cliente, clinica):
    """AGE-12: serviço que estava sem vínculo passa a recusar outro local; ao perder o último
    vínculo, volta a aceitar qualquer local. Agendamentos já marcados não mudam."""
    c, h = clinica, clinica.lt.h_admin

    def agendar(servico, local, hora, funcionario=c.lt.admin.id):
        dados = c.dados(
            servico_id=servico, local_id=local, inicio=f'{SEGUNDA}T{hora}', funcionario_id=str(funcionario)
        )
        return cliente.post(AGENDAMENTOS, json=dados, headers=h)

    # Avaliação ainda não tem local: vale qualquer um
    antes = agendar(c.avaliacao, c.sala2, '08:00')
    assert antes.status_code == 201, antes.json()

    _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[c.limpeza, c.avaliacao])
    avaliacao = cliente.get(f'/api/loja/servicos/{c.avaliacao}', headers=h).json()
    assert [loc['nome'] for loc in avaliacao['locais']] == ['Sala 1']
    recusado = agendar(c.avaliacao, c.sala2, '09:00')
    assert recusado.status_code == 422
    assert recusado.json()['detail'] == NAO_PERMITIDO
    assert agendar(c.avaliacao, c.sala1, '09:00').status_code == 201
    # O agendamento marcado antes continua lá
    assert cliente.get(f'{AGENDAMENTOS}/{antes.json()["id"]}', headers=h).json()['local_id'] == c.sala2

    # Sala 1 deixa de ter serviços: Avaliação perde o último vínculo e volta a aceitar qualquer local;
    # Limpeza continua presa ao local que sobrou (Online)
    _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[])
    assert agendar(c.avaliacao, c.sala2, '10:00').status_code == 201
    limpeza_na_sala1 = agendar(c.limpeza, c.sala1, '11:00', funcionario=c.lt.prof.id)
    assert limpeza_na_sala1.status_code == 422
    assert limpeza_na_sala1.json()['detail'] == NAO_PERMITIDO


def test_opcoes_e_locais_vinculados(cliente, clinica, engine_dono):
    c, h = clinica, clinica.lt.h_admin
    so_locais = usuario_com(engine_dono, c.lt.loja, {'locais': 'escrita'})
    resposta = cliente.get(OPCOES, headers=so_locais)  # não exige acesso a Serviços
    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()['servicos'] == [
        {'id': c.avaliacao, 'nome': 'Avaliação', 'ativo': True, 'locais_vinculados': 0},
        {'id': c.limpeza, 'nome': 'Limpeza', 'ativo': True, 'locais_vinculados': 2},
    ]

    # Inativo aparece; excluído não
    inativo = cliente.post(
        '/api/loja/servicos', json={'nome': 'Clareamento', 'duracao_minutos': 30, 'ativo': False}, headers=h
    ).json()['id']
    excluido = cliente.post(
        '/api/loja/servicos',
        json={'nome': 'Extinto', 'duracao_minutos': 30, 'funcionario_ids': [str(c.lt.admin.id)]},
        headers=h,
    ).json()['id']
    _put(cliente, h, c.sala2, 'Sala 2', servico_ids=[inativo, excluido, c.limpeza])
    assert cliente.delete(f'/api/loja/servicos/{excluido}', headers=h).status_code == 204
    opcoes = _opcoes(cliente, h)
    assert list(opcoes) == ['Avaliação', 'Clareamento', 'Limpeza']
    assert (opcoes['Clareamento']['ativo'], opcoes['Clareamento']['locais_vinculados']) == (False, 1)
    assert opcoes['Limpeza']['locais_vinculados'] == 3
    # O serviço excluído some dos serviços do local
    assert _servicos(cliente.get(f'{URL}/{c.sala2}', headers=h).json()) == [
        ('Clareamento', False),
        ('Limpeza', True),
    ]

    # Vínculo removido e local excluído (só pelo banco: a API só inativa) não contam
    _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[])
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE locais SET excluido_em = now() WHERE id = :i'), {'i': c.sala2})
    opcoes = _opcoes(cliente, h)
    assert opcoes['Limpeza']['locais_vinculados'] == 1  # só o Online
    assert opcoes['Clareamento']['locais_vinculados'] == 0


def test_isolamento_e_ids_invalidos(cliente, clinica, lojas, engine_dono):
    c, h = clinica, clinica.lt.h_admin
    _, b = lojas
    servico_b = cliente.post(
        '/api/loja/servicos',
        json={'nome': 'Corte', 'duracao_minutos': 30, 'funcionario_ids': [str(b.admin.id)]},
        headers=b.h_admin,
    ).json()['id']

    # Serviço da loja B: 422 e nada gravado (nem o nome do local)
    outra_loja = _put(cliente, h, c.sala1, 'Renomeada', servico_ids=[c.avaliacao, servico_b])
    assert outra_loja.status_code == 422
    assert outra_loja.json() == {'detail': 'Serviço não encontrado.'}
    sala1 = cliente.get(f'{URL}/{c.sala1}', headers=h).json()
    assert sala1['nome'] == 'Sala 1'
    assert _servicos(sala1) == [('Limpeza', True)]
    criar = cliente.post(URL, json={'nome': 'Sala X', 'servico_ids': [servico_b]}, headers=h)
    assert criar.status_code == 422
    assert all(loc['nome'] != 'Sala X' for loc in cliente.get(URL, headers=h).json())
    assert not any(str(v.servico_id) == servico_b for v in _vinculos(engine_dono, c.sala1))

    # Inexistente ou excluído
    assert _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[str(uuid4())]).json()['detail'] == (
        'Serviço não encontrado.'
    )
    assert cliente.delete(f'/api/loja/servicos/{c.avaliacao}', headers=h).status_code == 204
    excluido = _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[c.avaliacao])
    assert (excluido.status_code, excluido.json()['detail']) == (422, 'Serviço não encontrado.')

    # Formato inválido e lista grande demais
    malformado = _put(cliente, h, c.sala1, 'Sala 1', servico_ids=['abc'])
    assert malformado.status_code == 422
    assert malformado.json()['detail'] == 'Verifique os dados informados.'
    assert malformado.json()['erros'] == [{'campo': 'servico_ids.0', 'mensagem': 'Identificador inválido.'}]
    demais = _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[str(uuid4()) for _ in range(201)])
    assert demais.status_code == 422
    assert demais.json()['erros'][0]['campo'] == 'servico_ids'

    # Local da loja B: 404; opções da loja B não mostram serviços da A
    invadido = _put(cliente, b.h_admin, c.sala1, 'Invadida', servico_ids=[servico_b])
    assert (invadido.status_code, invadido.json()['detail']) == (404, 'Local não encontrado.')
    assert [s['nome'] for s in cliente.get(OPCOES, headers=b.h_admin).json()['servicos']] == ['Corte']
    assert _servicos(cliente.get(f'{URL}/{c.sala1}', headers=h).json()) == [('Limpeza', True)]


def test_permissoes(cliente, clinica, engine_dono):
    c, lt = clinica, clinica.lt
    # Recepção: leitura em Locais vê os serviços, mas não grava nem busca as opções
    assert _servicos(cliente.get(f'{URL}/{c.sala1}', headers=lt.h_recepcao).json()) == [('Limpeza', True)]
    negado = _put(cliente, lt.h_recepcao, c.sala1, 'Sala 1', servico_ids=[])
    assert (negado.status_code, negado.json()['detail']) == (403, 'Você só tem permissão de leitura aqui.')
    assert cliente.get(OPCOES, headers=lt.h_recepcao).status_code == 403
    assert cliente.get(OPCOES, headers=lt.h_prof).status_code == 403
    assert cliente.get(OPCOES).status_code == 401
    assert _servicos(cliente.get(f'{URL}/{c.sala1}', headers=lt.h_admin).json()) == [('Limpeza', True)]

    # Só escrita em Locais (sem acesso a Serviços) basta para vincular
    so_locais = usuario_com(engine_dono, lt.loja, {'locais': 'escrita'})
    assert _servicos(_put(cliente, so_locais, c.sala1, 'Sala 1', servico_ids=[c.avaliacao]).json()) == [
        ('Avaliação', True)
    ]

    mudar_modulo(engine_dono, lt.loja.id, 'locais', habilitado=False)
    desligado = cliente.get(OPCOES, headers=lt.h_admin)
    assert (desligado.status_code, desligado.json()['detail']) == (
        403,
        'Este módulo não está ativo na sua loja.',
    )


def test_modulo_servicos_desligado(cliente, clinica, engine_dono):
    c, h = clinica, clinica.lt.h_admin
    mudar_modulo(engine_dono, c.lt.loja.id, 'servicos', habilitado=False)
    assert cliente.get(OPCOES, headers=h).json() == {'servicos': None}
    ignorado = _put(cliente, h, c.sala1, 'Sala 1', servico_ids=[c.avaliacao])
    assert ignorado.status_code == 200
    assert ignorado.json()['servicos'] == []
    criado = cliente.post(URL, json={'nome': 'Sala 3', 'servico_ids': [str(uuid4())]}, headers=h)
    assert criado.status_code == 201  # nem confere os ids: o campo é ignorado
    assert criado.json()['servicos'] == []

    mudar_modulo(engine_dono, c.lt.loja.id, 'servicos', habilitado=True)
    assert _servicos(cliente.get(f'{URL}/{c.sala1}', headers=h).json()) == [('Limpeza', True)]
    assert cliente.get(f'{URL}/{criado.json()["id"]}', headers=h).json()['servicos'] == []
