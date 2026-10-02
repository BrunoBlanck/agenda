"""Agendamentos: regras do README, fluxo de status, estoque, visibilidade e isolamento entre lojas.

Datas fixas no futuro: 2030-01-07 é uma segunda-feira (dia_semana = 1).
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Agendamento, MovimentacaoEstoque
from app.models.enums import OrigemAgendamento, StatusAgendamento
from tests.clinica import SEGUNDA, Clinica, montar_clinica
from tests.fabricas import inserir, mudar_modulo, usuario_com

URL = '/api/loja/agendamentos'


def _criar(cliente, c: Clinica, cab=None, **extra):
    resposta = cliente.post(URL, json=c.dados(**extra), headers=cab or c.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def _erro(resposta, codigo):
    assert resposta.status_code == codigo, resposta.json()
    return resposta.json()['detail']


def _estoque(cliente, c: Clinica):
    return cliente.get(f'/api/loja/materiais/{c.luvas}', headers=c.lt.h_admin).json()['quantidade_atual']


# --- Criação: serviço define duração e preço ----------------------------------------------------


def test_criar_usa_duracao_e_preco_do_servico_e_copia_materiais(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    assert ag['inicio'] == f'{SEGUNDA}T09:00:00-03:00'
    assert ag['fim'] == f'{SEGUNDA}T10:00:00-03:00'
    assert ag['duracao_minutos'] == 60
    assert ag['preco'] == 200
    assert (ag['status'], ag['origem']) == ('agendado', 'painel')
    assert ag['cliente_nome'] == 'Maria Oliveira'
    assert (ag['servico_nome'], ag['funcionario_nome'], ag['local_nome']) == (
        'Limpeza',
        'Profissional',
        'Sala 1',
    )
    assert ag['materiais'] == [{'material_id': c.luvas, 'nome': 'Luvas', 'unidade': 'un', 'quantidade': 2}]
    assert ag['atualizado_por_nome'] == 'Admin'
    assert ag['criado_por'] == str(c.lt.admin.id)


def test_preco_fica_congelado_e_duracao_pode_ser_ajustada(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c, duracao_minutos=90, preco=180)
    assert ag['fim'] == f'{SEGUNDA}T10:30:00-03:00'
    assert ag['preco'] == 180
    cliente.put(
        f'/api/loja/servicos/{c.limpeza}',
        json={'nome': 'Limpeza', 'duracao_minutos': 60, 'preco': 250, 'funcionario_ids': [str(c.lt.prof.id)]},
        headers=c.lt.h_admin,
    )
    assert cliente.get(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).json()['preco'] == 180


def test_so_profissionais_habilitados(cliente, clinica):
    c = clinica
    detalhe = _erro(
        cliente.post(URL, json=c.dados(servico_id=c.avaliacao, local_id=c.sala2), headers=c.lt.h_admin), 422
    )
    assert detalhe == 'Este profissional não realiza o serviço escolhido.'
    assert (
        _erro(cliente.post(URL, json=c.dados(servico_id=None), headers=c.lt.h_admin), 422)
        == 'Escolha o serviço.'
    )


def test_jornada_e_bloqueios(cliente, clinica):
    c = clinica
    fora = cliente.post(URL, json=c.dados(inicio=f'{SEGUNDA}T11:30'), headers=c.lt.h_admin)  # termina 12:30
    assert _erro(fora, 422) == 'Horário fora da jornada de trabalho do profissional.'
    domingo = cliente.post(URL, json=c.dados(inicio='2030-01-06T09:00'), headers=c.lt.h_admin)
    assert _erro(domingo, 422) == 'Horário fora da jornada de trabalho do profissional.'

    cliente.post(
        '/api/loja/bloqueios',
        json={
            'funcionario_id': str(c.lt.prof.id),
            'inicio': f'{SEGUNDA}T14:00',
            'fim': f'{SEGUNDA}T16:00',
            'motivo': 'Consulta médica',
        },
        headers=c.lt.h_admin,
    )
    bloqueado = cliente.post(URL, json=c.dados(inicio=f'{SEGUNDA}T15:30'), headers=c.lt.h_admin)
    assert _erro(bloqueado, 422) == 'Horário bloqueado: Consulta médica.'
    # O bloqueio é só desse funcionário: o Administrador atende no mesmo horário
    _criar(cliente, c, funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T15:00')
    # Feriado (loja inteira) bloqueia todos
    cliente.post(
        '/api/loja/bloqueios',
        json={'inicio': '2030-01-14T00:00', 'fim': '2030-01-15T00:00'},
        headers=c.lt.h_admin,
    )
    feriado = cliente.post(URL, json=c.dados(inicio='2030-01-14T09:00'), headers=c.lt.h_admin)
    assert _erro(feriado, 422) == 'Horário bloqueado: sem motivo informado.'


def test_conflito_de_horario_do_profissional_e_do_local(cliente, clinica):
    c = clinica
    primeiro = _criar(cliente, c)
    mesmo_prof = cliente.post(
        URL, json=c.dados(inicio=f'{SEGUNDA}T09:30', local_id=c.online), headers=c.lt.h_admin
    )
    assert _erro(mesmo_prof, 409) == 'O profissional já tem um agendamento nesse horário.'
    mesmo_local = cliente.post(
        URL, json=c.dados(funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T09:30'), headers=c.lt.h_admin
    )
    assert _erro(mesmo_local, 409) == 'Este local já está ocupado nesse horário.'
    # Encostado (10:00) não conflita
    _criar(cliente, c, inicio=f'{SEGUNDA}T10:00')
    # Cancelado libera o horário
    cliente.post(
        f'{URL}/{primeiro["id"]}/status',
        json={'status': 'cancelado', 'motivo_cancelamento': 'Desmarcou'},
        headers=c.lt.h_admin,
    )
    _criar(cliente, c, inicio=f'{SEGUNDA}T09:00', cliente_id=c.joao)


def test_regras_de_local(cliente, clinica):
    c = clinica
    assert (
        _erro(cliente.post(URL, json=c.dados(local_id=None), headers=c.lt.h_admin), 422)
        == 'Escolha o local do atendimento.'
    )
    nao_permitido = cliente.post(URL, json=c.dados(local_id=c.sala2), headers=c.lt.h_admin)
    assert _erro(nao_permitido, 422) == 'Este local não é permitido para o serviço escolhido.'
    # Serviço sem local vinculado aceita qualquer local ativo
    _criar(cliente, c, servico_id=c.avaliacao, funcionario_id=str(c.lt.admin.id), local_id=c.sala2)
    cliente.put('/api/loja/locais/' + c.sala1, json={'nome': 'Sala 1', 'ativo': False}, headers=c.lt.h_admin)
    assert _erro(cliente.post(URL, json=c.dados(), headers=c.lt.h_admin), 422) == 'Este local está inativo.'


def test_local_online_e_link(cliente, clinica):
    c = clinica
    fixo = _criar(cliente, c, local_id=c.online)
    assert fixo['local_tipo'] == 'online'
    assert fixo['link_reuniao'] is None
    assert fixo['link'] == 'https://meet.example.com/fixo'
    proprio = _criar(
        cliente, c, local_id=c.online, inicio=f'{SEGUNDA}T13:00', link_reuniao='https://meet.example.com/x'
    )
    assert proprio['link'] == 'https://meet.example.com/x'
    presencial = _criar(cliente, c, inicio=f'{SEGUNDA}T15:00', link_reuniao='https://meet.example.com/y')
    assert presencial['link_reuniao'] is None
    assert presencial['link'] is None


def test_modulo_servicos_desligado(cliente, clinica, engine_dono):
    c = clinica
    mudar_modulo(engine_dono, c.lt.loja.id, 'servicos', habilitado=False)
    sem_duracao = cliente.post(URL, json=c.dados(), headers=c.lt.h_admin)
    assert _erro(sem_duracao, 422) == 'Informe a duração do atendimento.'
    ag = _criar(cliente, c, duracao_minutos=45, preco=99, local_id=c.sala2)  # qualquer local ativo
    assert ag['servico_id'] is None
    assert ag['duracao_minutos'] == 45
    assert ag['preco'] == 99
    assert ag['materiais'] == []
    # Profissional não habilitado para nenhum serviço pode atender sem serviço
    _criar(cliente, c, funcionario_id=str(c.lt.recepcao.id), duracao_minutos=30, local_id=c.sala1)


def test_modulo_locais_desligado(cliente, clinica, engine_dono):
    c = clinica
    mudar_modulo(engine_dono, c.lt.loja.id, 'locais', habilitado=False)
    ag = _criar(cliente, c, local_id=c.sala2)  # local ignorado
    assert ag['local_id'] is None
    # Sem locais, dois atendimentos ao mesmo tempo com profissionais diferentes
    _criar(cliente, c, funcionario_id=str(c.lt.admin.id), local_id=None)


# --- Status e estoque ---------------------------------------------------------------------------


def test_fluxo_de_status_baixa_e_estorno_do_estoque(cliente, clinica, engine_dono):
    c = clinica
    ag = _criar(cliente, c)
    url = f'{URL}/{ag["id"]}/status'
    pular = cliente.post(url, json={'status': 'concluido'}, headers=c.lt.h_admin)
    assert _erro(pular, 409) == 'Não é possível passar de "Agendado" para "Concluído".'
    assert (
        cliente.post(url, json={'status': 'confirmado'}, headers=c.lt.h_admin).json()['status']
        == 'confirmado'
    )
    assert (
        cliente.post(url, json={'status': 'concluido'}, headers=c.lt.h_admin).json()['status'] == 'concluido'
    )
    assert _estoque(cliente, c) == 8  # 10 - 2 luvas

    final = cliente.post(url, json={'status': 'cancelado', 'motivo_cancelamento': 'x'}, headers=c.lt.h_admin)
    assert _erro(final, 409) == 'Um agendamento "Concluído" não pode passar para "Cancelado".'
    reabrir_recepcao = cliente.post(url, json={'status': 'confirmado'}, headers=c.lt.h_recepcao)
    assert _erro(reabrir_recepcao, 403) == 'Só o Administrador pode reabrir um agendamento "Concluído".'
    editar = cliente.put(f'{URL}/{ag["id"]}', json=c.dados(), headers=c.lt.h_admin)
    assert 'não pode ser editado' in _erro(editar, 409)

    assert (
        cliente.post(url, json={'status': 'confirmado'}, headers=c.lt.h_admin).json()['status']
        == 'confirmado'
    )
    assert _estoque(cliente, c) == 10  # estorno
    cliente.post(url, json={'status': 'concluido'}, headers=c.lt.h_admin)
    assert _estoque(cliente, c) == 8
    with engine_dono.connect() as conexao:
        movimentos = conexao.execute(
            select(MovimentacaoEstoque.tipo, MovimentacaoEstoque.quantidade)
            .where(MovimentacaoEstoque.agendamento_id == ag['id'])
            .order_by(MovimentacaoEstoque.criado_em)
        ).all()
    assert [(t.value, float(q)) for t, q in movimentos] == [
        ('saida_atendimento', -2),
        ('ajuste', 2),
        ('saida_atendimento', -2),
    ]


def test_estoque_pode_ficar_negativo(cliente, clinica):
    c = clinica
    for hora in ('08:00', '09:00', '10:00', '13:00', '14:00', '15:00'):
        ag = _criar(cliente, c, inicio=f'{SEGUNDA}T{hora}', local_id=c.online)
        for st in ('confirmado', 'concluido'):
            cliente.post(f'{URL}/{ag["id"]}/status', json={'status': st}, headers=c.lt.h_admin)
    assert _estoque(cliente, c) == -2
    material = cliente.get(f'/api/loja/materiais/{c.luvas}', headers=c.lt.h_admin).json()
    assert material['repor'] is True


def test_sem_modulo_materiais_nao_ha_baixa(cliente, clinica, engine_dono):
    c = clinica
    mudar_modulo(engine_dono, c.lt.loja.id, 'materiais', habilitado=False)
    ag = _criar(cliente, c)
    assert ag['materiais'] is None
    for st in ('confirmado', 'concluido'):
        cliente.post(f'{URL}/{ag["id"]}/status', json={'status': st}, headers=c.lt.h_admin)
    mudar_modulo(engine_dono, c.lt.loja.id, 'materiais', habilitado=True)
    assert _estoque(cliente, c) == 10


def test_cancelar_exige_motivo_e_pendente_so_pelo_site(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    url = f'{URL}/{ag["id"]}/status'
    assert (
        _erro(cliente.post(url, json={'status': 'cancelado'}, headers=c.lt.h_admin), 422)
        == 'Informe o motivo do cancelamento.'
    )
    pendente = cliente.post(url, json={'status': 'pendente'}, headers=c.lt.h_admin)
    assert _erro(pendente, 422) == 'Só pedidos feitos pelo site ficam aguardando aceite.'
    cancelado = cliente.post(
        url, json={'status': 'cancelado', 'motivo_cancelamento': 'Desmarcou'}, headers=c.lt.h_admin
    )
    assert cancelado.json()['motivo_cancelamento'] == 'Desmarcou'
    criar_concluido = cliente.post(
        URL, json=c.dados(inicio=f'{SEGUNDA}T13:00', status='concluido'), headers=c.lt.h_admin
    )
    assert _erro(criar_concluido, 422) == 'Um novo agendamento começa como "Agendado" ou "Confirmado".'


def test_aceitar_e_recusar_solicitacao_do_site(cliente, clinica, engine_dono):
    c = clinica

    def pedido(hora):
        inicio = datetime.fromisoformat(f'{SEGUNDA}T{hora}-03:00').astimezone(UTC)
        return inserir(
            engine_dono,
            Agendamento(
                loja_id=c.lt.loja.id,
                cliente_id=c.maria,
                servico_id=c.limpeza,
                funcionario_id=c.lt.prof.id,
                local_id=c.sala1,
                inicio=inicio,
                fim=inicio.replace(hour=inicio.hour + 1),
                status=StatusAgendamento.pendente,
                origem=OrigemAgendamento.site,
            ),
        ).id

    aceito = cliente.post(f'{URL}/{pedido("09:00")}/aceitar', headers=c.lt.h_recepcao)
    assert aceito.status_code == 200
    assert (aceito.json()['status'], aceito.json()['origem']) == ('confirmado', 'site')
    assert _erro(cliente.post(f'{URL}/{aceito.json()["id"]}/aceitar', headers=c.lt.h_recepcao), 409) == (
        'Esta solicitação já foi respondida.'
    )
    recusado = cliente.post(f'{URL}/{pedido("13:00")}/recusar', headers=c.lt.h_recepcao).json()
    assert (recusado['status'], recusado['motivo_cancelamento']) == ('cancelado', 'Recusado pela loja')
    com_motivo = cliente.post(
        f'{URL}/{pedido("14:00")}/recusar',
        json={'motivo_cancelamento': 'Sem horário'},
        headers=c.lt.h_recepcao,
    ).json()
    assert com_motivo['motivo_cancelamento'] == 'Sem horário'


# --- Edição e exclusão --------------------------------------------------------------------------


def test_remarcar_trocar_servico_e_status_pelo_put(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    remarcado = cliente.put(
        f'{URL}/{ag["id"]}', json=c.dados(inicio=f'{SEGUNDA}T14:00'), headers=c.lt.h_admin
    ).json()
    assert remarcado['inicio'] == f'{SEGUNDA}T14:00:00-03:00'
    assert remarcado['duracao_minutos'] == 60  # mantém a duração
    fora = cliente.put(f'{URL}/{ag["id"]}', json=c.dados(inicio=f'{SEGUNDA}T17:30'), headers=c.lt.h_admin)
    assert _erro(fora, 422) == 'Horário fora da jornada de trabalho do profissional.'

    trocado = cliente.put(
        f'{URL}/{ag["id"]}',
        json=c.dados(
            servico_id=c.avaliacao,
            funcionario_id=str(c.lt.admin.id),
            local_id=c.sala2,
            inicio=f'{SEGUNDA}T14:00',
        ),
        headers=c.lt.h_admin,
    ).json()
    assert (trocado['servico_nome'], trocado['duracao_minutos'], trocado['preco']) == ('Avaliação', 30, 100)
    assert trocado['materiais'] == []  # materiais do novo serviço
    confirmado = cliente.put(
        f'{URL}/{ag["id"]}',
        json=c.dados(
            servico_id=c.avaliacao,
            funcionario_id=str(c.lt.admin.id),
            local_id=c.sala2,
            inicio=f'{SEGUNDA}T14:00',
            status='confirmado',
        ),
        headers=c.lt.h_admin,
    ).json()
    assert confirmado['status'] == 'confirmado'


def test_ajustar_materiais_antes_de_concluir(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    ajustado = cliente.put(
        f'{URL}/{ag["id"]}/materiais',
        json={'materiais': [{'material_id': c.luvas, 'quantidade': 3}]},
        headers=c.lt.h_prof,
    )
    assert ajustado.json()['materiais'][0]['quantidade'] == 3
    for st in ('confirmado', 'concluido'):
        cliente.post(f'{URL}/{ag["id"]}/status', json={'status': st}, headers=c.lt.h_prof)
    assert _estoque(cliente, c) == 7
    depois = cliente.put(f'{URL}/{ag["id"]}/materiais', json={'materiais': []}, headers=c.lt.h_admin)
    assert _erro(depois, 409) == 'Os materiais só podem ser ajustados antes de concluir o atendimento.'


def test_excluir(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    assert cliente.delete(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).status_code == 204
    assert cliente.get(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).status_code == 404
    # O horário fica livre de novo
    concluido = _criar(cliente, c)
    for st in ('confirmado', 'concluido'):
        cliente.post(f'{URL}/{concluido["id"]}/status', json={'status': st}, headers=c.lt.h_admin)
    assert 'não pode ser excluído' in _erro(
        cliente.delete(f'{URL}/{concluido["id"]}', headers=c.lt.h_admin), 409
    )


# --- Lista ---------------------------------------------------------------------------------------


def test_lista_filtrada_e_paginada(cliente, clinica):
    c = clinica
    a1 = _criar(cliente, c)
    a2 = _criar(
        cliente,
        c,
        funcionario_id=str(c.lt.admin.id),
        local_id=c.online,
        cliente_id=c.joao,
        inicio=f'{SEGUNDA}T10:00',
    )
    a3 = _criar(cliente, c, inicio='2030-01-14T09:00')
    cliente.post(f'{URL}/{a3["id"]}/status', json={'status': 'confirmado'}, headers=c.lt.h_admin)

    def ids(**params):
        return [a['id'] for a in cliente.get(URL, params=params, headers=c.lt.h_admin).json()['itens']]

    assert ids() == [a1['id'], a2['id'], a3['id']]
    assert ids(funcionario_id=str(c.lt.admin.id)) == [a2['id']]
    assert ids(local_id=c.sala1) == [a1['id'], a3['id']]
    assert ids(cliente_id=c.joao) == [a2['id']]
    assert ids(status=['confirmado']) == [a3['id']]
    assert ids(status=['agendado', 'confirmado'], inicio='2030-01-08') == [a3['id']]
    assert ids(inicio=SEGUNDA, fim=SEGUNDA) == [a1['id'], a2['id']]
    pagina = cliente.get(URL, params={'por_pagina': 2, 'pagina': 2}, headers=c.lt.h_admin).json()
    assert (pagina['total'], [a['id'] for a in pagina['itens']]) == (3, [a3['id']])
    invertido = cliente.get(URL, params={'inicio': '2030-01-10', 'fim': '2030-01-01'}, headers=c.lt.h_admin)
    assert invertido.status_code == 422


# --- Visibilidade e permissões ------------------------------------------------------------------


def test_profissional_so_ve_e_altera_os_proprios(cliente, clinica):
    c = clinica
    do_admin = _criar(cliente, c, funcionario_id=str(c.lt.admin.id), local_id=c.online)
    proprio = _criar(cliente, c, cab=c.lt.h_prof, inicio=f'{SEGUNDA}T14:00')
    assert proprio['funcionario_id'] == str(c.lt.prof.id)

    lista = cliente.get(URL, headers=c.lt.h_prof).json()
    assert [a['id'] for a in lista['itens']] == [proprio['id']]
    assert cliente.get(f'{URL}/{do_admin["id"]}', headers=c.lt.h_prof).status_code == 404
    assert (
        cliente.post(
            f'{URL}/{do_admin["id"]}/status', json={'status': 'confirmado'}, headers=c.lt.h_prof
        ).status_code
        == 404
    )
    para_outro = cliente.post(
        URL, json=c.dados(funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T15:00'), headers=c.lt.h_prof
    )
    assert _erro(para_outro, 403) == 'Você só pode agendar para você mesmo.'
    passar_adiante = cliente.put(
        f'{URL}/{proprio["id"]}',
        json=c.dados(funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T14:00'),
        headers=c.lt.h_prof,
    )
    assert passar_adiante.status_code == 403
    # A Recepção (agenda da equipe) vê os dois
    assert cliente.get(URL, headers=c.lt.h_recepcao).json()['total'] == 2


def test_niveis_de_acesso_da_agenda(cliente, clinica, engine_dono):
    c = clinica
    ag = _criar(cliente, c)
    so_le_equipe = usuario_com(engine_dono, c.lt.loja, {'agenda_equipe': 'leitura'})
    assert cliente.get(URL, headers=so_le_equipe).json()['total'] == 1
    assert cliente.get(f'{URL}/{ag["id"]}', headers=so_le_equipe).status_code == 200
    escrita = cliente.post(URL, json=c.dados(inicio=f'{SEGUNDA}T14:00'), headers=so_le_equipe)
    assert _erro(escrita, 403) == 'Você só tem permissão de leitura aqui.'
    assert cliente.delete(f'{URL}/{ag["id"]}', headers=so_le_equipe).status_code == 403
    le_equipe_escreve_propria = usuario_com(
        engine_dono, c.lt.loja, {'agenda_equipe': 'leitura', 'agenda_propria': 'escrita'}
    )
    assert (
        cliente.post(
            f'{URL}/{ag["id"]}/status', json={'status': 'confirmado'}, headers=le_equipe_escreve_propria
        ).status_code
        == 403
    )
    sem_agenda = usuario_com(engine_dono, c.lt.loja, {'clientes': 'escrita'})
    assert cliente.get(URL, headers=sem_agenda).status_code == 403
    assert cliente.get('/api/loja/apoio/agendamento', headers=sem_agenda).status_code == 403


# --- Listas de apoio e disponibilidade ----------------------------------------------------------


def test_listas_de_apoio(cliente, clinica):
    c = clinica
    cliente.put(
        f'/api/loja/clientes/{c.joao}',
        json={'nome': 'João', 'sobrenome': 'Pereira', 'telefone': '2', 'ativo': False},
        headers=c.lt.h_admin,
    )
    da_recepcao = cliente.get('/api/loja/apoio/agendamento', headers=c.lt.h_recepcao).json()
    assert [cl['nome'] for cl in da_recepcao['clientes']] == ['Maria']  # só ativos
    assert {p['nome'] for p in da_recepcao['profissionais']} == {'Admin', 'Profissional', 'Recepção'}
    assert [s['nome'] for s in da_recepcao['servicos']] == ['Avaliação', 'Limpeza']
    assert [loc['nome'] for loc in da_recepcao['locais']] == ['Online', 'Sala 1', 'Sala 2']

    # Profissional: ele mesmo e só os serviços que realiza (sem leitura em Serviços)
    do_prof = cliente.get('/api/loja/apoio/agendamento', headers=c.lt.h_prof).json()
    assert [p['nome'] for p in do_prof['profissionais']] == ['Profissional']
    assert [s['nome'] for s in do_prof['servicos']] == ['Limpeza']
    assert cliente.get('/api/loja/servicos', headers=c.lt.h_prof).status_code == 403


def test_disponibilidade(cliente, clinica):
    c = clinica
    ag = _criar(cliente, c)
    url = '/api/loja/apoio/disponibilidade'
    params = {'funcionario_id': str(c.lt.prof.id), 'inicio': f'{SEGUNDA}T09:30', 'duracao_minutos': 30}
    ocupado = cliente.get(url, params=params, headers=c.lt.h_admin).json()
    assert ocupado == {'aviso': None, 'profissional_ocupado': True, 'locais_ocupados': [c.sala1]}
    editando = cliente.get(url, params={**params, 'agendamento_id': ag['id']}, headers=c.lt.h_admin).json()
    assert editando == {'aviso': None, 'profissional_ocupado': False, 'locais_ocupados': []}
    almoco = cliente.get(url, params={**params, 'inicio': f'{SEGUNDA}T12:00'}, headers=c.lt.h_admin).json()
    assert almoco['aviso'] == 'Horário fora da jornada de trabalho do profissional.'
    de_outro = cliente.get(url, params={**params, 'funcionario_id': str(c.lt.admin.id)}, headers=c.lt.h_prof)
    assert de_outro.status_code == 403


# --- Histórico do cliente -----------------------------------------------------------------------


def test_historico_do_cliente(cliente, clinica):
    c = clinica
    concluido = _criar(cliente, c)
    for st in ('confirmado', 'concluido'):
        cliente.post(f'{URL}/{concluido["id"]}/status', json={'status': st}, headers=c.lt.h_admin)
    falta = _criar(cliente, c, inicio=f'{SEGUNDA}T10:00')
    cliente.post(f'{URL}/{falta["id"]}/status', json={'status': 'nao_compareceu'}, headers=c.lt.h_admin)
    do_admin = _criar(cliente, c, funcionario_id=str(c.lt.admin.id), inicio='2030-01-14T09:00')
    _criar(cliente, c, cliente_id=c.joao, inicio=f'{SEGUNDA}T13:00')

    url = f'/api/loja/clientes/{c.maria}/historico'
    completo = cliente.get(url, headers=c.lt.h_admin).json()
    assert completo['cliente']['nome'] == 'Maria'
    assert (completo['concluidos'], completo['faltas'], completo['cancelados']) == (1, 1, 0)
    assert completo['total_gasto'] == 200
    assert completo['ultimo']['id'] == concluido['id']
    assert completo['proximo']['id'] == do_admin['id']
    assert completo['parcial'] is False
    assert [a['id'] for a in completo['agendamentos']['itens']] == [
        do_admin['id'],
        falta['id'],
        concluido['id'],
    ]
    faltas = cliente.get(url, params={'filtro': 'faltas'}, headers=c.lt.h_admin).json()
    assert [a['id'] for a in faltas['agendamentos']['itens']] == [falta['id']]

    # O Profissional só vê os atendimentos dele com o cliente
    do_prof = cliente.get(url, headers=c.lt.h_prof).json()
    assert do_prof['parcial'] is True
    assert do_prof['proximo'] is None
    assert len(do_prof['agendamentos']['itens']) == 2


# --- Isolamento entre lojas ---------------------------------------------------------------------


def test_isolamento_entre_lojas(cliente, lojas, clinica):
    c = clinica
    _, b = lojas
    ag = _criar(cliente, c)
    url = f'{URL}/{ag["id"]}'
    assert cliente.get(url, headers=b.h_admin).status_code == 404
    assert cliente.put(url, json=c.dados(), headers=b.h_admin).status_code == 404
    assert cliente.delete(url, headers=b.h_admin).status_code == 404
    assert cliente.post(f'{url}/status', json={'status': 'confirmado'}, headers=b.h_admin).status_code == 404
    assert cliente.post(f'{url}/aceitar', headers=b.h_admin).status_code == 404
    assert cliente.put(f'{url}/materiais', json={'materiais': []}, headers=b.h_admin).status_code == 404
    assert cliente.get(URL, headers=b.h_admin).json()['total'] == 0
    assert cliente.get(f'/api/loja/clientes/{c.maria}/historico', headers=b.h_admin).status_code == 404

    # Loja B não usa cliente, serviço, profissional ou local da loja A
    outra = montar_clinica(cliente, b)
    for campo, valor, mensagem in (
        ('cliente_id', c.maria, 'Cliente não encontrado.'),
        ('servico_id', c.limpeza, 'Serviço não encontrado.'),
        ('funcionario_id', str(c.lt.prof.id), 'Profissional não encontrado.'),
        ('local_id', c.sala1, 'Local não encontrado.'),
    ):
        resposta = cliente.post(URL, json=outra.dados(**{campo: valor}), headers=b.h_admin)
        assert _erro(resposta, 422) == mensagem
    # Mesmo horário e "mesmo" profissional em outra loja não conflita
    _criar(cliente, outra)
    assert cliente.get(url, headers=c.lt.h_admin).json()['status'] == 'agendado'
