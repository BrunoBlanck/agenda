"""Materiais, categorias e movimentações de estoque."""

from app.models import Servico, ServicoMaterial
from tests.fabricas import inserir, mudar_modulo, usuario_com

URL = '/api/loja/materiais'
CATEGORIAS = '/api/loja/categorias-material'


def _material(cliente, cab, **dados):
    corpo = {'nome': 'Luvas (cx)', 'unidade': 'cx', 'estoque_minimo': 10, 'quantidade_inicial': 25, **dados}
    resposta = cliente.post(URL, json=corpo, headers=cab)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastro_lanca_estoque_inicial_como_entrada(cliente, lojas):
    a, _ = lojas
    categoria = cliente.post(CATEGORIAS, json={'nome': 'Descartáveis'}, headers=a.h_admin).json()
    luvas = _material(cliente, a.h_admin, categoria_id=categoria['id'])
    assert luvas['quantidade_atual'] == 25
    assert luvas['estoque_minimo'] == 10
    assert luvas['categoria_nome'] == 'Descartáveis'
    assert luvas['repor'] is False

    historico = cliente.get(f'{URL}/{luvas["id"]}/movimentacoes', headers=a.h_admin).json()
    assert historico['total'] == 1
    entrada = historico['itens'][0]
    assert (entrada['tipo'], entrada['quantidade'], entrada['motivo']) == ('entrada', 25, 'Estoque inicial')
    assert entrada['funcionario_nome'] == 'Admin'

    sem_estoque = _material(cliente, a.h_admin, nome='Gaze', unidade='', quantidade_inicial=0)
    assert sem_estoque['unidade'] == 'un'  # unidade vazia vira "un"
    assert sem_estoque['quantidade_atual'] == 0
    assert sem_estoque['repor'] is True
    assert cliente.get(f'{URL}/{sem_estoque["id"]}/movimentacoes', headers=a.h_admin).json()['total'] == 0


def test_edicao_nao_mexe_no_estoque(cliente, lojas):
    a, _ = lojas
    luvas = _material(cliente, a.h_admin)
    editado = cliente.put(
        f'{URL}/{luvas["id"]}',
        json={'nome': 'Luvas nitrílicas', 'unidade': 'cx', 'estoque_minimo': 30, 'quantidade_atual': 999},
        headers=a.h_admin,
    ).json()
    assert editado['nome'] == 'Luvas nitrílicas'
    assert editado['quantidade_atual'] == 25  # campo ignorado
    assert editado['repor'] is True


def test_movimentacoes_entrada_ajuste_e_perda(cliente, lojas):
    a, _ = lojas
    luvas = _material(cliente, a.h_admin)
    mov = f'{URL}/{luvas["id"]}/movimentacoes'

    assert cliente.post(mov, json={'tipo': 'entrada', 'quantidade': 5}, headers=a.h_admin).status_code == 201
    perda = cliente.post(
        mov, json={'tipo': 'perda', 'quantidade': 3, 'motivo': 'Rasgadas'}, headers=a.h_admin
    )
    assert perda.json()['quantidade'] == -3  # perda informada positiva vira saída
    cliente.post(mov, json={'tipo': 'ajuste', 'quantidade': -2.5, 'motivo': 'Contagem'}, headers=a.h_admin)
    assert cliente.get(f'{URL}/{luvas["id"]}', headers=a.h_admin).json()['quantidade_atual'] == 24.5

    sem_motivo = cliente.post(mov, json={'tipo': 'ajuste', 'quantidade': 1}, headers=a.h_admin)
    assert sem_motivo.status_code == 422
    assert sem_motivo.json()['erros'][0]['mensagem'] == 'Informe o motivo do ajuste ou da perda.'
    entrada_negativa = cliente.post(mov, json={'tipo': 'entrada', 'quantidade': -1}, headers=a.h_admin)
    assert entrada_negativa.status_code == 422
    zero = cliente.post(mov, json={'tipo': 'entrada', 'quantidade': 0}, headers=a.h_admin)
    assert zero.status_code == 422
    manual = cliente.post(mov, json={'tipo': 'saida_atendimento', 'quantidade': -1}, headers=a.h_admin)
    assert manual.status_code == 422  # só ao concluir um atendimento

    pagina = cliente.get(mov, params={'por_pagina': 2}, headers=a.h_admin).json()
    assert pagina['total'] == 4
    assert [m['tipo'] for m in pagina['itens']] == ['ajuste', 'perda']  # mais recente primeiro


def test_filtros_da_lista(cliente, lojas):
    a, _ = lojas
    _material(cliente, a.h_admin)
    _material(cliente, a.h_admin, nome='Máscaras', quantidade_inicial=6)
    _material(cliente, a.h_admin, nome='Anestésico', ativo=False)

    def nomes(**params):
        return [m['nome'] for m in cliente.get(URL, params=params, headers=a.h_admin).json()]

    assert nomes() == ['Anestésico', 'Luvas (cx)', 'Máscaras']
    assert nomes(repor=True) == ['Máscaras']
    assert nomes(ativo=False) == ['Anestésico']
    assert nomes(busca='más') == ['Máscaras']


def test_exclusoes_bloqueadas_quando_em_uso(cliente, lojas, engine_dono):
    a, _ = lojas
    categoria = cliente.post(CATEGORIAS, json={'nome': 'Descartáveis'}, headers=a.h_admin).json()
    luvas = _material(cliente, a.h_admin, categoria_id=categoria['id'])
    assert cliente.delete(f'{CATEGORIAS}/{categoria["id"]}', headers=a.h_admin).status_code == 409

    servico = inserir(engine_dono, Servico(loja_id=a.loja.id, nome='Limpeza', duracao_minutos=30))
    inserir(
        engine_dono,
        ServicoMaterial(loja_id=a.loja.id, servico_id=servico.id, material_id=luvas['id'], quantidade=1),
    )
    em_uso = cliente.delete(f'{URL}/{luvas["id"]}', headers=a.h_admin)
    assert em_uso.status_code == 409
    assert em_uso.json()['detail'] == 'Este material é usado em serviços. Retire-o dos serviços ou inative-o.'

    livre = _material(cliente, a.h_admin, nome='Gaze')
    assert cliente.delete(f'{URL}/{livre["id"]}', headers=a.h_admin).status_code == 204
    assert cliente.get(f'{URL}/{livre["id"]}', headers=a.h_admin).status_code == 404
    vazia = cliente.post(CATEGORIAS, json={'nome': 'Limpeza'}, headers=a.h_admin).json()
    assert cliente.delete(f'{CATEGORIAS}/{vazia["id"]}', headers=a.h_admin).status_code == 204
    repetida = cliente.post(CATEGORIAS, json={'nome': 'Descartáveis'}, headers=a.h_admin)
    assert repetida.json()['detail'] == 'Já existe uma categoria com este nome.'


def test_permissoes_e_modulo_desligado(cliente, lojas, engine_dono):
    a, _ = lojas
    luvas = _material(cliente, a.h_admin)
    leitor = usuario_com(engine_dono, a.loja, {'materiais': 'leitura'})
    assert cliente.get(URL, headers=leitor).status_code == 200
    assert cliente.get(f'{URL}/{luvas["id"]}/movimentacoes', headers=leitor).status_code == 200
    assert cliente.get(CATEGORIAS, headers=leitor).status_code == 200
    assert cliente.post(URL, json={'nome': 'X'}, headers=leitor).status_code == 403
    assert (
        cliente.post(
            f'{URL}/{luvas["id"]}/movimentacoes', json={'tipo': 'entrada', 'quantidade': 1}, headers=leitor
        ).status_code
        == 403
    )
    assert cliente.post(CATEGORIAS, json={'nome': 'X'}, headers=leitor).status_code == 403
    # Recepção e Profissional: nenhum em materiais
    assert cliente.get(URL, headers=a.h_recepcao).status_code == 403
    assert cliente.get(URL, headers=a.h_prof).status_code == 403
    mudar_modulo(engine_dono, a.loja.id, 'materiais', habilitado=False)
    assert cliente.get(URL, headers=a.h_admin).status_code == 403
    assert cliente.get(CATEGORIAS, headers=a.h_admin).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas):
    a, b = lojas
    luvas = _material(cliente, a.h_admin)
    categoria_a = cliente.post(CATEGORIAS, json={'nome': 'Descartáveis'}, headers=a.h_admin).json()
    url = f'{URL}/{luvas["id"]}'
    assert cliente.get(url, headers=b.h_admin).status_code == 404
    assert cliente.put(url, json={'nome': 'X'}, headers=b.h_admin).status_code == 404
    assert cliente.delete(url, headers=b.h_admin).status_code == 404
    assert cliente.get(f'{url}/movimentacoes', headers=b.h_admin).status_code == 404
    assert (
        cliente.post(
            f'{url}/movimentacoes', json={'tipo': 'entrada', 'quantidade': 100}, headers=b.h_admin
        ).status_code
        == 404
    )
    assert (
        cliente.put(f'{CATEGORIAS}/{categoria_a["id"]}', json={'nome': 'X'}, headers=b.h_admin).status_code
        == 404
    )
    com_categoria_de_a = cliente.post(
        URL, json={'nome': 'Y', 'categoria_id': categoria_a['id']}, headers=b.h_admin
    )
    assert com_categoria_de_a.status_code == 422
    assert cliente.get(URL, headers=b.h_admin).json() == []
    assert cliente.get(url, headers=a.h_admin).json()['quantidade_atual'] == 25
