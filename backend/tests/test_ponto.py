"""Controle de Tempo: registrar entrada/saída, correção manual, total por dia, permissões e isolamento."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import RegistroPonto
from app.models.enums import OrigemPonto
from tests.fabricas import inserir, mudar_modulo, usuario_com

URL = '/api/loja/ponto'
SP = ZoneInfo('America/Sao_Paulo')


def _registro(engine, lt, funcionario, entrada, saida=None):
    return inserir(
        engine,
        RegistroPonto(loja_id=lt.loja.id, funcionario_id=funcionario.id, entrada=entrada, saida=saida),
    )


def test_registrar_entrada_e_saida_com_hora_do_servidor(cliente, lojas, engine_dono):
    a, _ = lojas
    antes = datetime.now(UTC).replace(microsecond=0)
    entrada = cliente.post(f'{URL}/registrar', json={'acao': 'entrada'}, headers=a.h_prof)
    assert entrada.status_code == 200, entrada.json()
    assert entrada.json()['acao'] == 'entrada'
    registro = entrada.json()['registro']
    assert registro['saida'] is None
    assert registro['origem'] == 'sistema'
    assert datetime.fromisoformat(registro['entrada']) >= antes
    assert cliente.get(f'{URL}/aberto', headers=a.h_prof).json()['id'] == registro['id']

    saida = cliente.post(f'{URL}/registrar', json={'acao': 'saida'}, headers=a.h_prof).json()
    assert saida['acao'] == 'saida'
    assert saida['registro']['id'] == registro['id']
    assert saida['registro']['minutos'] == 0
    assert cliente.get(f'{URL}/aberto', headers=a.h_prof).json() is None

    with engine_dono.connect() as conexao:
        assert len(conexao.execute(select(RegistroPonto)).all()) == 1


def test_lista_do_dia_e_total_por_dia(cliente, lojas, engine_dono):
    a, _ = lojas
    dia = datetime(2030, 1, 7, tzinfo=SP)
    _registro(engine_dono, a, a.prof, dia.replace(hour=8), dia.replace(hour=12))
    _registro(engine_dono, a, a.prof, dia.replace(hour=13), dia.replace(hour=17, minute=30))
    _registro(engine_dono, a, a.recepcao, dia.replace(hour=7, minute=45))
    _registro(engine_dono, a, a.prof, dia.replace(day=8, hour=8), dia.replace(day=8, hour=9))

    corpo = cliente.get(URL, params={'inicio': '2030-01-07'}, headers=a.h_admin).json()
    assert [(r['funcionario_nome'], r['entrada'][11:16]) for r in corpo['registros']] == [
        ('Recepção', '07:45'),
        ('Profissional', '08:00'),
        ('Profissional', '13:00'),
    ]
    assert corpo['registros'][0]['minutos'] is None  # em serviço
    assert corpo['registros'][0]['data'] == '2030-01-07'
    assert corpo['totais'] == [
        {
            'funcionario_id': str(a.prof.id),
            'funcionario_nome': 'Profissional',
            'data': '2030-01-07',
            'minutos': 510,
        }
    ]
    semana = cliente.get(URL, params={'inicio': '2030-01-07', 'fim': '2030-01-08'}, headers=a.h_admin).json()
    assert [t['minutos'] for t in semana['totais']] == [510, 60]
    so_prof = cliente.get(
        URL, params={'inicio': '2030-01-07', 'funcionario_id': str(a.prof.id)}, headers=a.h_admin
    )
    assert len(so_prof.json()['registros']) == 2
    hoje_vazio = cliente.get(URL, headers=a.h_admin).json()
    assert hoje_vazio['registros'] == []
    assert (
        cliente.get(URL, params={'inicio': '2030-01-01', 'fim': '2030-05-01'}, headers=a.h_admin).status_code
        == 422
    )


def test_correcao_e_lancamento_manual(cliente, lojas, engine_dono):
    a, _ = lojas
    ontem = datetime.now(SP).replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=1)
    registro = _registro(engine_dono, a, a.prof, ontem)
    url = f'{URL}/{registro.id}'
    sem_justificativa = cliente.put(
        url, json={'entrada': ontem.isoformat(), 'justificativa': ' '}, headers=a.h_admin
    )
    assert sem_justificativa.status_code == 422
    invertida = cliente.put(
        url,
        json={
            'entrada': ontem.isoformat(),
            'saida': (ontem - timedelta(hours=1)).isoformat(),
            'justificativa': 'x',
        },
        headers=a.h_admin,
    )
    assert invertida.json()['detail'] == 'A saída deve ser depois da entrada.'
    futuro = cliente.put(
        url,
        json={'entrada': (datetime.now(SP) + timedelta(days=1)).isoformat(), 'justificativa': 'x'},
        headers=a.h_admin,
    )
    assert futuro.json()['detail'] == 'O registro de ponto não pode ficar no futuro.'

    corrigido = cliente.put(
        url,
        json={
            'entrada': ontem.replace(tzinfo=None).isoformat(),  # sem fuso = horário da loja
            'saida': ontem.replace(hour=17, tzinfo=None).isoformat(),
            'justificativa': 'Esqueceu de bater a saída',
        },
        headers=a.h_admin,
    )
    assert corrigido.status_code == 200, corrigido.json()
    corpo = corrigido.json()
    assert (corpo['origem'], corpo['minutos'], corpo['editado_por_nome']) == ('manual', 540, 'Admin')
    assert corpo['justificativa'] == 'Esqueceu de bater a saída'

    manual = cliente.post(
        URL,
        json={
            'funcionario_id': str(a.recepcao.id),
            'entrada': (ontem - timedelta(days=1)).isoformat(),
            'saida': (ontem - timedelta(days=1) + timedelta(hours=4)).isoformat(),
            'justificativa': 'Ponto em papel',
        },
        headers=a.h_admin,
    )
    assert manual.status_code == 201, manual.json()
    assert manual.json()['origem'] == 'manual'

    with engine_dono.connect() as conexao:
        origem = conexao.execute(select(RegistroPonto.origem).where(RegistroPonto.id == registro.id)).scalar()
    assert origem == OrigemPonto.manual


def test_um_registro_aberto_por_funcionario(cliente, lojas, engine_dono):
    a, _ = lojas
    ontem = datetime.now(UTC) - timedelta(days=1)
    _registro(engine_dono, a, a.prof, ontem)
    em_aberto = cliente.post(
        URL,
        json={
            'funcionario_id': str(a.prof.id),
            'entrada': (ontem - timedelta(days=1)).isoformat(),
            'justificativa': 'x',
        },
        headers=a.h_admin,
    )
    assert em_aberto.status_code == 409
    assert em_aberto.json()['detail'] == 'Este funcionário já tem um registro de ponto em aberto.'
    # Registrar agora fecha o que estava aberto
    assert (
        cliente.post(f'{URL}/registrar', json={'acao': 'saida'}, headers=a.h_prof).json()['acao'] == 'saida'
    )


def test_permissoes(cliente, lojas, engine_dono):
    a, _ = lojas
    ontem = datetime.now(UTC) - timedelta(days=1)
    do_admin = _registro(engine_dono, a, a.admin, ontem, ontem + timedelta(hours=1))
    _registro(engine_dono, a, a.prof, ontem, ontem + timedelta(hours=2))
    dia = ontem.astimezone(SP).date().isoformat()

    # Profissional: só o próprio ponto
    do_prof = cliente.get(
        URL, params={'inicio': dia, 'funcionario_id': str(a.admin.id)}, headers=a.h_prof
    ).json()
    assert [r['funcionario_nome'] for r in do_prof['registros']] == ['Profissional']
    assert (
        cliente.get(f'{URL}/aberto', params={'funcionario_id': str(a.admin.id)}, headers=a.h_prof).status_code
        == 403
    )
    para_outro = cliente.post(
        f'{URL}/registrar', json={'acao': 'entrada', 'funcionario_id': str(a.admin.id)}, headers=a.h_prof
    )
    assert para_outro.status_code == 403
    assert para_outro.json()['detail'] == 'Você só pode registrar o seu próprio ponto.'
    correcao = cliente.put(
        f'{URL}/{do_admin.id}', json={'entrada': ontem.isoformat(), 'justificativa': 'x'}, headers=a.h_prof
    )
    assert correcao.status_code == 403

    # Quem lê o ponto da equipe vê todos, mas não corrige
    leitor = usuario_com(engine_dono, a.loja, {'ponto_equipe': 'leitura'})
    assert len(cliente.get(URL, params={'inicio': dia}, headers=leitor).json()['registros']) == 2
    assert cliente.post(f'{URL}/registrar', json={'acao': 'entrada'}, headers=leitor).status_code == 403
    # Quem corrige pode registrar para outro funcionário
    assert (
        cliente.post(
            f'{URL}/registrar', json={'acao': 'entrada', 'funcionario_id': str(a.prof.id)}, headers=a.h_admin
        ).json()['acao']
        == 'entrada'
    )
    # Sem nível em ponto
    sem = usuario_com(engine_dono, a.loja, {'clientes': 'leitura'})
    assert cliente.get(URL, headers=sem).status_code == 403
    # Funcionário inativo não registra
    cliente.put(
        f'/api/loja/funcionarios/{a.recepcao.id}',
        json={
            'nome': 'Recepção',
            'email': 'recepcao@loja-a.com',
            'perfil_id': str(a.perfis['Recepção'].id),
            'ativo': False,
        },
        headers=a.h_admin,
    )
    inativo = cliente.post(
        f'{URL}/registrar', json={'acao': 'entrada', 'funcionario_id': str(a.recepcao.id)}, headers=a.h_admin
    )
    assert inativo.json()['detail'] == 'Funcionário inativo não registra ponto.'
    # Módulo desligado
    mudar_modulo(engine_dono, a.loja.id, 'controle_tempo', habilitado=False)
    assert cliente.get(URL, headers=a.h_admin).status_code == 403
    assert cliente.post(f'{URL}/registrar', json={'acao': 'entrada'}, headers=a.h_admin).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas, engine_dono):
    a, b = lojas
    ontem = datetime.now(UTC) - timedelta(days=1)
    registro_a = _registro(engine_dono, a, a.prof, ontem)
    dia = ontem.astimezone(SP).date().isoformat()
    assert cliente.get(URL, params={'inicio': dia}, headers=b.h_admin).json()['registros'] == []
    corrigir = cliente.put(
        f'{URL}/{registro_a.id}', json={'entrada': ontem.isoformat(), 'justificativa': 'x'}, headers=b.h_admin
    )
    assert corrigir.status_code == 404
    para_func_de_a = cliente.post(
        f'{URL}/registrar', json={'acao': 'saida', 'funcionario_id': str(a.prof.id)}, headers=b.h_admin
    )
    assert para_func_de_a.status_code == 404
    manual = cliente.post(
        URL,
        json={'funcionario_id': str(a.prof.id), 'entrada': ontem.isoformat(), 'justificativa': 'x'},
        headers=b.h_admin,
    )
    assert manual.status_code == 404
    assert (
        cliente.get(f'{URL}/aberto', params={'funcionario_id': str(a.prof.id)}, headers=b.h_admin).json()
        is None
    )
    with engine_dono.connect() as conexao:
        saida = conexao.execute(select(RegistroPonto.saida).where(RegistroPonto.id == registro_a.id)).scalar()
    assert saida is None


def test_funcionarios_do_ponto_da_equipe(cliente, lojas, engine_dono):
    """GET /ponto/funcionarios: lista de apoio da loja (com inativos), só com Ponto da equipe."""
    a, b = lojas
    leitor = usuario_com(engine_dono, a.loja, {'ponto_equipe': 'leitura'}, nome='Leitor do ponto')
    resposta = cliente.get(f'{URL}/funcionarios', headers=leitor)
    assert resposta.status_code == 200, resposta.json()
    nomes = [f['nome'] for f in resposta.json()]
    assert {'Admin', 'Profissional', 'Recepção', 'Leitor do ponto'} <= set(nomes)
    assert all(set(f) == {'id', 'nome', 'cor_agenda', 'ativo'} for f in resposta.json())
    ids_b = {str(b.admin.id), str(b.prof.id), str(b.recepcao.id)}
    assert not ids_b & {f['id'] for f in resposta.json()}

    assert cliente.get(f'{URL}/funcionarios', headers=a.h_prof).status_code == 403
    mudar_modulo(engine_dono, a.loja.id, 'controle_tempo', habilitado=False)
    assert cliente.get(f'{URL}/funcionarios', headers=a.h_admin).status_code == 403
