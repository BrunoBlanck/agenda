"""Serviços: vínculos com profissionais, locais e materiais, restauração de vínculo, módulos e isolamento."""

from sqlalchemy import select

from app.models import Auditoria, ServicoFuncionario
from tests.fabricas import mudar_modulo, usuario_com

URL = '/api/loja/servicos'


def _local(cliente, cab, nome):
    return cliente.post('/api/loja/locais', json={'nome': nome}, headers=cab).json()['id']


def _material(cliente, cab, nome):
    return cliente.post('/api/loja/materiais', json={'nome': nome}, headers=cab).json()['id']


def _dados(lt, **extra):
    return {
        'nome': 'Limpeza',
        'duracao_minutos': 60,
        'preco': 200,
        'funcionario_ids': [str(lt.admin.id)],
        **extra,
    }


def test_crud_com_vinculos(cliente, lojas):
    a, _ = lojas
    sala1, sala2 = _local(cliente, a.h_admin, 'Sala 1'), _local(cliente, a.h_admin, 'Sala 2')
    luvas = _material(cliente, a.h_admin, 'Luvas')
    criado = cliente.post(
        URL,
        json=_dados(
            a,
            funcionario_ids=[str(a.admin.id), str(a.prof.id), str(a.admin.id)],
            local_ids=[sala1, sala2],
            materiais=[{'material_id': luvas, 'quantidade': 2}],
        ),
        headers=a.h_admin,
    )
    assert criado.status_code == 201, criado.json()
    corpo = criado.json()
    assert corpo['preco'] == 200
    assert sorted(corpo['funcionario_ids']) == sorted([str(a.admin.id), str(a.prof.id)])
    assert [p['nome'] for p in corpo['profissionais']] == ['Admin', 'Profissional']
    assert [loc['nome'] for loc in corpo['locais']] == ['Sala 1', 'Sala 2']
    assert corpo['materiais'] == [{'material_id': luvas, 'nome': 'Luvas', 'unidade': 'un', 'quantidade': 2}]

    # local_ids e materiais nulos = não mudam; [] = qualquer local / nenhum material
    sem_mudar = cliente.put(
        f'{URL}/{corpo["id"]}', json=_dados(a, nome='Limpeza completa'), headers=a.h_admin
    ).json()
    assert sem_mudar['nome'] == 'Limpeza completa'
    assert len(sem_mudar['local_ids']) == 2
    assert len(sem_mudar['materiais']) == 1
    limpo = cliente.put(
        f'{URL}/{corpo["id"]}',
        json=_dados(a, local_ids=[], materiais=[{'material_id': luvas, 'quantidade': 3}]),
        headers=a.h_admin,
    ).json()
    assert limpo['local_ids'] == []
    assert limpo['materiais'][0]['quantidade'] == 3

    assert len(cliente.get(URL, headers=a.h_admin).json()) == 1
    assert cliente.delete(f'{URL}/{corpo["id"]}', headers=a.h_admin).status_code == 204
    assert cliente.get(f'{URL}/{corpo["id"]}', headers=a.h_admin).status_code == 404


def test_religar_vinculo_restaura_a_linha(cliente, lojas, engine_dono):
    a, _ = lojas
    ids = [str(a.admin.id), str(a.prof.id)]
    servico = cliente.post(URL, json=_dados(a, funcionario_ids=ids), headers=a.h_admin).json()
    cliente.put(
        f'{URL}/{servico["id"]}', json=_dados(a, funcionario_ids=[str(a.admin.id)]), headers=a.h_admin
    )
    religado = cliente.put(f'{URL}/{servico["id"]}', json=_dados(a, funcionario_ids=ids), headers=a.h_admin)
    assert len(religado.json()['funcionario_ids']) == 2

    with engine_dono.connect() as conexao:
        linhas = conexao.execute(
            select(ServicoFuncionario.excluido_em).where(
                ServicoFuncionario.servico_id == servico['id'], ServicoFuncionario.funcionario_id == a.prof.id
            )
        ).all()
        operacoes = (
            conexao.execute(
                select(Auditoria.operacao)
                .where(
                    Auditoria.tabela == 'servico_funcionarios',
                    Auditoria.registro_id == f'{servico["id"]}:{a.prof.id}',
                )
                .order_by(Auditoria.id)
            )
            .scalars()
            .all()
        )
    assert len(linhas) == 1  # a mesma linha, sem duplicar
    assert linhas[0].excluido_em is None
    assert operacoes == ['inserir', 'excluir', 'restaurar']


def test_regras_de_validacao(cliente, lojas):
    a, _ = lojas
    sem_profissional = cliente.post(URL, json=_dados(a, funcionario_ids=[]), headers=a.h_admin)
    assert sem_profissional.status_code == 422
    assert sem_profissional.json()['detail'] == 'Selecione ao menos um profissional que realiza o serviço.'
    # Serviço inativo pode ficar sem profissional
    assert (
        cliente.post(
            URL, json=_dados(a, nome='Antigo', funcionario_ids=[], ativo=False), headers=a.h_admin
        ).status_code
        == 201
    )

    luvas = _material(cliente, a.h_admin, 'Luvas')
    repetido = cliente.post(
        URL,
        json=_dados(a, materiais=[{'material_id': luvas}, {'material_id': luvas, 'quantidade': 2}]),
        headers=a.h_admin,
    )
    assert repetido.status_code == 422
    assert repetido.json()['erros'][0]['mensagem'] == 'Cada material só pode aparecer uma vez no serviço.'
    assert cliente.post(URL, json=_dados(a, duracao_minutos=0), headers=a.h_admin).status_code == 422
    assert cliente.post(URL, json=_dados(a, preco=-1), headers=a.h_admin).status_code == 422
    cliente.post(URL, json=_dados(a), headers=a.h_admin)
    nome_repetido = cliente.post(URL, json=_dados(a), headers=a.h_admin)
    assert nome_repetido.status_code == 409
    assert nome_repetido.json()['detail'] == 'Já existe um serviço com este nome.'


def test_modulos_locais_e_materiais_desligados(cliente, lojas, engine_dono):
    a, _ = lojas
    sala = _local(cliente, a.h_admin, 'Sala 1')
    luvas = _material(cliente, a.h_admin, 'Luvas')
    servico = cliente.post(
        URL, json=_dados(a, local_ids=[sala], materiais=[{'material_id': luvas}]), headers=a.h_admin
    ).json()
    mudar_modulo(engine_dono, a.loja.id, 'locais', habilitado=False)
    mudar_modulo(engine_dono, a.loja.id, 'materiais', habilitado=False)
    # Sem os módulos, os vínculos não aparecem e não são alterados
    editado = cliente.put(
        f'{URL}/{servico["id"]}', json=_dados(a, local_ids=[], materiais=[]), headers=a.h_admin
    ).json()
    assert editado['local_ids'] == []
    assert editado['materiais'] == []
    mudar_modulo(engine_dono, a.loja.id, 'locais', habilitado=True)
    mudar_modulo(engine_dono, a.loja.id, 'materiais', habilitado=True)
    de_volta = cliente.get(f'{URL}/{servico["id"]}', headers=a.h_admin).json()
    assert de_volta['local_ids'] == [sala]
    assert de_volta['materiais'][0]['material_id'] == luvas


def test_permissoes_e_modulo_servicos_desligado(cliente, lojas, engine_dono):
    a, _ = lojas
    servico = cliente.post(URL, json=_dados(a), headers=a.h_admin).json()
    # Recepção: leitura em serviços
    assert cliente.get(URL, headers=a.h_recepcao).status_code == 200
    assert cliente.post(URL, json=_dados(a, nome='Outro'), headers=a.h_recepcao).status_code == 403
    assert cliente.put(f'{URL}/{servico["id"]}', json=_dados(a), headers=a.h_recepcao).status_code == 403
    assert cliente.delete(f'{URL}/{servico["id"]}', headers=a.h_recepcao).status_code == 403
    # Profissional: nenhum
    assert cliente.get(URL, headers=a.h_prof).status_code == 403
    mudar_modulo(engine_dono, a.loja.id, 'servicos', habilitado=False)
    desligado = cliente.get(URL, headers=a.h_admin)
    assert desligado.status_code == 403
    assert desligado.json()['detail'] == 'Este módulo não está ativo na sua loja.'


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    servico_a = cliente.post(URL, json=_dados(a), headers=a.h_admin).json()
    url = f'{URL}/{servico_a["id"]}'
    assert cliente.get(url, headers=b.h_admin).status_code == 404
    assert cliente.put(url, json=_dados(b), headers=b.h_admin).status_code == 404
    assert cliente.delete(url, headers=b.h_admin).status_code == 404
    assert cliente.get(URL, headers=b.h_admin).json() == []
    # Vínculos com profissional, local ou material de outra loja são recusados
    com_prof_a = cliente.post(URL, json=_dados(b, funcionario_ids=[str(a.prof.id)]), headers=b.h_admin)
    assert com_prof_a.status_code == 422
    assert com_prof_a.json()['detail'] == 'Profissional não encontrado.'
    sala_a = _local(cliente, a.h_admin, 'Sala 1')
    assert cliente.post(URL, json=_dados(b, local_ids=[sala_a]), headers=b.h_admin).status_code == 422
    luvas_a = _material(cliente, a.h_admin, 'Luvas')
    assert (
        cliente.post(URL, json=_dados(b, materiais=[{'material_id': luvas_a}]), headers=b.h_admin).status_code
        == 422
    )
    assert cliente.get(URL, headers=b.h_admin).json() == []


def test_opcoes_do_formulario(cliente, lojas, engine_dono):
    """GET /servicos/opcoes: só ativos, da própria loja, sem exigir Funcionários/Locais/Materiais."""
    a, b = lojas
    sala = _local(cliente, a.h_admin, 'Sala 1')
    cliente.post('/api/loja/locais', json={'nome': 'Sala velha', 'ativo': False}, headers=a.h_admin)
    luvas = _material(cliente, a.h_admin, 'Luvas')
    cliente.post('/api/loja/materiais', json={'nome': 'Gaze', 'ativo': False}, headers=a.h_admin)
    _local(cliente, b.h_admin, 'Sala da loja B')

    so_servicos = usuario_com(engine_dono, a.loja, {'servicos': 'escrita'})
    resposta = cliente.get(f'{URL}/opcoes', headers=so_servicos)
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert {p['nome'] for p in corpo['profissionais']} >= {'Admin', 'Profissional', 'Recepção'}
    assert corpo['locais'] == [{'id': sala, 'nome': 'Sala 1', 'tipo': 'presencial'}]
    assert corpo['materiais'] == [{'id': luvas, 'nome': 'Luvas', 'unidade': 'un'}]

    # Módulos desligados: listas nulas (o formulário esconde os campos)
    mudar_modulo(engine_dono, a.loja.id, 'locais', habilitado=False)
    mudar_modulo(engine_dono, a.loja.id, 'materiais', habilitado=False)
    corpo = cliente.get(f'{URL}/opcoes', headers=a.h_admin).json()
    assert corpo['locais'] is None
    assert corpo['materiais'] is None

    # Só leitura em Serviços (Recepção) não precisa das opções
    assert cliente.get(f'{URL}/opcoes', headers=a.h_recepcao).status_code == 403
    mudar_modulo(engine_dono, a.loja.id, 'servicos', habilitado=False)
    assert cliente.get(f'{URL}/opcoes', headers=a.h_admin).status_code == 403
