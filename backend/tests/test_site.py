"""Site do consumidor (/api/site/{slug}): dados públicos, horários livres e pedido de agendamento.

Usa a loja de tests/clinica.py: jornada só na segunda (08–12 e 13–18) para todos os perfis;
Limpeza (60 min, Admin e Profissional, locais Sala 1 e Online) e Avaliação (30 min, só Admin, sem
local vinculado = qualquer local ativo).
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.models.enums import StatusLoja
from tests.clinica import SEGUNDA
from tests.fabricas import cabecalho_superadmin, criar_loja, criar_superadmin, mudar_modulo

SITE = '/api/site/loja-a'
TERCA = '2030-01-08'
FUSO = ZoneInfo('America/Sao_Paulo')


def pedido(clinica, **extra):
    return {
        'servico_id': clinica.limpeza,
        'funcionario_id': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T14:00',
        'nome': 'Ana',
        'sobrenome': 'Souza',
        'telefone': '(11) 97777-6666',
        'email': 'ana@example.com',
        **extra,
    }


def horarios(cliente, **params):
    resposta = cliente.get(f'{SITE}/horarios', params={'inicio': SEGUNDA, **params})
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def horas(cliente, **params):
    return [h['hora'] for h in horarios(cliente, **params)[0]['horarios']]


def consultar(engine, sql, **params):
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).mappings().all()


# --- Dados públicos -----------------------------------------------------------------------------


def test_dados_publicos_da_loja(cliente, clinica):
    resposta = cliente.get(SITE)
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados['slug'] == 'loja-a'
    assert dados['nome_fantasia'] == 'Loja loja-a'
    assert (dados['usa_servicos'], dados['usa_locais']) == (True, True)
    # Nada interno: id, CNPJ, plano, situação...
    assert not {'id', 'cnpj', 'plano_id', 'status', 'nome'} & set(dados)


@pytest.mark.parametrize('slug', ['nao-existe', 'LOJA-A', 'loja_a', '-loja-a'])
def test_slug_inexistente_ou_invalido_responde_404(cliente, clinica, slug):
    resposta = cliente.get(f'/api/site/{slug}/servicos')
    assert resposta.status_code == 404
    assert resposta.json()['detail'] == 'Loja não encontrada.'


@pytest.mark.parametrize('situacao', [StatusLoja.suspensa, StatusLoja.cancelada])
def test_loja_suspensa_ou_cancelada_responde_404(cliente, engine_dono, situacao):
    criar_loja(engine_dono, 'fechada', status=situacao)
    for rota in ('', '/servicos', '/locais', '/horarios'):
        resposta = cliente.get(f'/api/site/fechada{rota}')
        assert resposta.status_code == 404
        assert resposta.json()['detail'] == 'Loja não encontrada.'


def test_loja_excluida_responde_404(cliente, engine_dono, clinica):
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET excluido_em = now() WHERE slug = 'loja-a'"))
    assert cliente.get(SITE).status_code == 404


def test_servicos_com_profissionais_habilitados(cliente, clinica):
    servicos = cliente.get(f'{SITE}/servicos').json()
    assert [s['nome'] for s in servicos] == ['Avaliação', 'Limpeza']
    limpeza = servicos[1]
    assert (limpeza['duracao_minutos'], limpeza['preco']) == (60, 200)
    assert [p['nome'] for p in limpeza['profissionais']] == ['Admin', 'Profissional']
    # Só id, nome e cor dos profissionais
    assert set(limpeza['profissionais'][0]) == {'id', 'nome', 'cor_agenda'}


def test_servico_inativo_ou_sem_profissional_ativo_nao_aparece(cliente, clinica):
    h = clinica.lt.h_admin
    servico = cliente.get(f'/api/loja/servicos/{clinica.avaliacao}', headers=h).json()
    cliente.put(f'/api/loja/servicos/{clinica.avaliacao}', json={**servico, 'ativo': False}, headers=h)
    assert [s['nome'] for s in cliente.get(f'{SITE}/servicos').json()] == ['Limpeza']


def test_sem_modulo_servicos_oferece_atendimento_generico(cliente, engine_dono, clinica):
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'servicos', habilitado=False)
    servicos = cliente.get(f'{SITE}/servicos').json()
    assert len(servicos) == 1
    assert (servicos[0]['id'], servicos[0]['nome'], servicos[0]['duracao_minutos']) == (
        None,
        'Atendimento',
        30,
    )
    assert {p['nome'] for p in servicos[0]['profissionais']} == {'Admin', 'Recepção', 'Profissional'}

    livres = horas(cliente, funcionario_id=str(clinica.lt.prof.id))
    assert livres[:2] == ['08:00', '08:30']
    criado = cliente.post(
        f'{SITE}/agendamentos', json=pedido(clinica, servico_id=None, inicio=f'{SEGUNDA}T08:00')
    )
    assert criado.status_code == 201, criado.json()
    assert criado.json()['servico_nome'] == 'Atendimento'


def test_locais_publicos_sem_link(cliente, engine_dono, clinica):
    locais = cliente.get(f'{SITE}/locais', params={'servico_id': clinica.limpeza}).json()
    assert [(x['nome'], x['tipo']) for x in locais] == [('Online', 'online'), ('Sala 1', 'presencial')]
    assert all(set(x) == {'id', 'nome', 'tipo'} for x in locais)
    assert len(cliente.get(f'{SITE}/locais').json()) == 3
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'locais', habilitado=False)
    assert cliente.get(f'{SITE}/locais').json() == []


# --- Horários livres ----------------------------------------------------------------------------


def test_horarios_seguem_a_jornada(cliente, clinica):
    dia = horarios(cliente, servico_id=clinica.limpeza)[0]
    assert dia['data'] == SEGUNDA
    assert [h['hora'] for h in dia['horarios']] == [
        *('08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00'),
        *('13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00'),
    ]
    primeiro = dia['horarios'][0]
    assert primeiro['funcionario_nome'] == 'Admin'  # com "qualquer profissional", o primeiro livre
    assert primeiro['inicio'] == f'{SEGUNDA}T08:00:00-03:00'
    assert primeiro['local'] == {'id': clinica.online, 'nome': 'Online', 'tipo': 'online'}
    # Terça: ninguém tem jornada
    assert horas(cliente, servico_id=clinica.limpeza, inicio=TERCA) == []


def test_varios_dias_e_limites_da_consulta(cliente, clinica):
    dias = horarios(cliente, servico_id=clinica.avaliacao, fim=TERCA)
    assert [(d['data'], len(d['horarios'])) for d in dias] == [(SEGUNDA, 18), (TERCA, 0)]
    longe = cliente.get(
        f'{SITE}/horarios', params={'servico_id': clinica.limpeza, 'inicio': SEGUNDA, 'fim': '2030-03-01'}
    )
    assert longe.status_code == 422
    invertido = cliente.get(
        f'{SITE}/horarios', params={'servico_id': clinica.limpeza, 'inicio': TERCA, 'fim': SEGUNDA}
    )
    assert invertido.status_code == 422
    sem_servico = cliente.get(f'{SITE}/horarios', params={'inicio': SEGUNDA})
    assert sem_servico.status_code == 422
    assert sem_servico.json()['detail'] == 'Escolha o serviço.'


def test_agendamento_existente_ocupa_o_profissional(cliente, clinica):
    resposta = cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=clinica.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()  # Profissional, 09:00–10:00, Sala 1
    prof = horas(cliente, servico_id=clinica.limpeza, funcionario_id=str(clinica.lt.prof.id))
    assert '08:30' not in prof
    assert '09:00' not in prof
    assert '09:30' not in prof
    assert {'08:00', '10:00'} <= set(prof)
    # Qualquer profissional: o Admin continua livre às 09:00
    qualquer = {h['hora']: h for h in horarios(cliente, servico_id=clinica.limpeza)[0]['horarios']}
    assert qualquer['09:00']['funcionario_nome'] == 'Admin'


def test_cancelado_libera_o_horario(cliente, clinica):
    h = clinica.lt.h_admin
    ag = cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=h).json()
    cancelado = cliente.post(
        f'/api/loja/agendamentos/{ag["id"]}/status',
        json={'status': 'cancelado', 'motivo_cancelamento': 'Desistiu'},
        headers=h,
    )
    assert cancelado.status_code == 200, cancelado.json()
    assert '09:00' in horas(cliente, servico_id=clinica.limpeza, funcionario_id=str(clinica.lt.prof.id))


def test_bloqueio_tira_os_horarios(cliente, clinica):
    resposta = cliente.post(
        '/api/loja/bloqueios',
        json={'inicio': f'{SEGUNDA}T16:00', 'fim': f'{SEGUNDA}T18:00', 'motivo': 'Reunião'},
        headers=clinica.lt.h_admin,
    )
    assert resposta.status_code == 201, resposta.json()
    livres = horas(cliente, servico_id=clinica.limpeza)
    assert livres[-1] == '15:00'  # 15:30–16:30 já pega o bloqueio


def test_sem_local_livre_nao_oferece_o_horario(cliente, clinica):
    h = clinica.lt.h_admin
    online = cliente.get(f'/api/loja/locais/{clinica.online}', headers=h).json()
    resposta = cliente.put(f'/api/loja/locais/{clinica.online}', json={**online, 'ativo': False}, headers=h)
    assert resposta.status_code == 200, resposta.json()
    # Profissional ocupa a Sala 1 (único local permitido e ativo) às 09:00
    cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=h)
    admin = horas(cliente, servico_id=clinica.limpeza, funcionario_id=str(clinica.lt.admin.id))
    assert '09:00' not in admin  # o Admin está livre, mas não há local
    assert '10:00' in admin
    # Avaliação aceita qualquer local ativo: Sala 2 está livre
    avaliacao = {h['hora']: h for h in horarios(cliente, servico_id=clinica.avaliacao)[0]['horarios']}
    assert avaliacao['09:00']['local']['nome'] == 'Sala 2'


def test_horarios_de_um_local_escolhido(cliente, engine_dono, clinica):
    admin = str(clinica.lt.admin.id)
    # Profissional ocupa a Sala 1 às 09:00; o Admin continua livre, com o Online
    cliente.post('/api/loja/agendamentos', json=clinica.dados(), headers=clinica.lt.h_admin)
    qualquer = {
        h['hora']: h
        for h in horarios(cliente, servico_id=clinica.limpeza, funcionario_id=admin)[0]['horarios']
    }
    assert qualquer['09:00']['local']['nome'] == 'Online'
    sala1 = horarios(cliente, servico_id=clinica.limpeza, funcionario_id=admin, local_id=clinica.sala1)[0]
    assert all(h['local']['nome'] == 'Sala 1' for h in sala1['horarios'])
    assert '09:00' not in [h['hora'] for h in sala1['horarios']]
    assert '10:00' in [h['hora'] for h in sala1['horarios']]
    # Local não permitido para o serviço
    fora = cliente.get(
        f'{SITE}/horarios',
        params={'servico_id': clinica.limpeza, 'inicio': SEGUNDA, 'local_id': clinica.sala2},
    )
    assert fora.status_code == 422
    assert fora.json()['detail'] == 'Local não encontrado para este serviço.'
    # Sem o módulo Locais, o filtro é ignorado
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'locais', habilitado=False)
    sem_modulo = horarios(cliente, servico_id=clinica.limpeza, local_id=clinica.sala2)[0]
    assert sem_modulo['horarios']
    assert all(h['local'] is None for h in sem_modulo['horarios'])


def test_sem_modulo_locais_horario_sem_local(cliente, engine_dono, clinica):
    mudar_modulo(engine_dono, clinica.lt.loja.id, 'locais', habilitado=False)
    dia = horarios(cliente, servico_id=clinica.limpeza)[0]
    assert dia['horarios'][0]['local'] is None
    criado = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica)).json()
    assert criado['local'] is None


def test_antecedencia_minima(cliente, clinica):
    agora = datetime.now(FUSO)
    hoje = agora.date()
    dia_semana = (hoje.weekday() + 1) % 7
    if dia_semana == 1:  # segunda: o dia já tem a jornada do cenário (08–12 e 13–18)
        pytest.skip('Hoje é segunda; a jornada de teste já cobre o dia.')
    h = clinica.lt.h_admin
    perfil = clinica.lt.perfis['Profissional'].id
    resposta = cliente.post(
        f'/api/loja/perfis/{perfil}/horarios',
        json={'dia_semana': dia_semana, 'hora_inicio': '00:00', 'hora_fim': '23:59'},
        headers=h,
    )
    assert resposta.status_code == 201, resposta.json()
    params = {
        'servico_id': clinica.limpeza,
        'funcionario_id': str(clinica.lt.prof.id),
        'inicio': hoje.isoformat(),
    }
    livres = horarios(cliente, **params)[0]['horarios']
    limite = datetime.now(UTC) + timedelta(minutes=60)
    assert all(datetime.fromisoformat(h['inicio']) >= limite - timedelta(seconds=5) for h in livres)
    ontem = cliente.get(
        f'{SITE}/horarios', params={**params, 'inicio': (hoje - timedelta(days=1)).isoformat()}
    )
    assert ontem.json()[0]['horarios'] == []


# --- Pedido de agendamento ----------------------------------------------------------------------


def test_pedido_entra_pendente_e_ocupa_o_horario(cliente, engine_dono, clinica):
    resposta = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica))
    assert resposta.status_code == 201, resposta.json()
    criado = resposta.json()
    assert criado['status'] == 'pendente'
    assert criado['inicio'] == f'{SEGUNDA}T14:00:00-03:00'
    assert criado['fim'] == f'{SEGUNDA}T15:00:00-03:00'
    assert (criado['servico_nome'], criado['funcionario_nome'], criado['preco']) == (
        'Limpeza',
        'Profissional',
        200,
    )
    assert criado['local']['nome'] == 'Online'
    assert criado['cliente_nome'] == 'Ana'
    assert 'cliente_id' not in criado

    ag = consultar(
        engine_dono,
        'SELECT origem::text AS origem, status::text AS status, atualizado_por, criado_por, cliente_id'
        ' FROM agendamentos WHERE id = :i',
        i=criado['id'],
    )[0]
    assert (ag['origem'], ag['status'], ag['atualizado_por'], ag['criado_por']) == (
        'site',
        'pendente',
        None,
        None,
    )
    cli = consultar(
        engine_dono,
        'SELECT nome, sobrenome, telefone, canais::text[] AS canais FROM clientes WHERE id = :i',
        i=ag['cliente_id'],
    )[0]
    assert cli == {'nome': 'Ana', 'sobrenome': 'Souza', 'telefone': '(11) 97777-6666', 'canais': ['site']}
    materiais = consultar(
        engine_dono, 'SELECT quantidade FROM agendamento_materiais WHERE agendamento_id = :i', i=criado['id']
    )
    assert [float(m['quantidade']) for m in materiais] == [2.0]

    # O horário deixa de ser oferecido e um segundo pedido igual é recusado
    assert '14:00' not in horas(cliente, servico_id=clinica.limpeza, funcionario_id=str(clinica.lt.prof.id))
    repetido = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, telefone='11 95555-4444'))
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Este horário não está mais disponível. Escolha outro horário.'

    # No painel, aparece como "Aguardando aceite" e a recepção aceita
    h = clinica.lt.h_recepcao
    painel = cliente.get(f'/api/loja/agendamentos/{criado["id"]}', headers=h).json()
    assert (painel['status'], painel['origem'], painel['cliente_nome']) == ('pendente', 'site', 'Ana Souza')
    aceito = cliente.post(f'/api/loja/agendamentos/{criado["id"]}/aceitar', headers=h)
    assert aceito.status_code == 200, aceito.json()
    assert aceito.json()['status'] == 'confirmado'


def test_pedido_auditado_como_cliente_pelo_site(cliente, engine_dono, clinica):
    criado = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica)).json()
    registros = consultar(
        engine_dono,
        'SELECT tabela, operacao::text AS operacao, origem::text AS origem, funcionario_id, superadmin_id'
        ' FROM auditoria WHERE origem = :o ORDER BY id',
        o='site',
    )
    assert {(r['tabela'], r['operacao']) for r in registros} == {
        ('clientes', 'inserir'),
        ('agendamentos', 'inserir'),
        ('agendamento_materiais', 'inserir'),
        ('notificacoes', 'inserir'),  # NOT-01: os avisos do pedido, na mesma transação
    }
    assert all(r['funcionario_id'] is None and r['superadmin_id'] is None for r in registros)

    # Na tela de auditoria do superadmin: "Cliente, pelo site"
    h = cabecalho_superadmin(criar_superadmin(engine_dono))
    itens = cliente.get(
        '/api/superadmin/auditoria',
        params={'loja': str(clinica.lt.loja.id), 'tabela': 'agendamentos', 'quem': 'site'},
        headers=h,
    ).json()['itens']
    assert len(itens) == 1
    assert itens[0]['registro_id'] == criado['id']
    assert itens[0]['quem'] == {'tipo': 'site', 'id': None, 'nome': 'Cliente, pelo site', 'chave': 'site'}
    assert itens[0]['rotulo'] == '07/01/2030 14:00 · Ana Souza'


def test_cliente_existente_pelo_telefone_ganha_o_canal_site(cliente, engine_dono, clinica):
    h = clinica.lt.h_admin
    existente = cliente.post(
        '/api/loja/clientes',
        json={'nome': 'Carla', 'sobrenome': 'Lima', 'telefone': '11977776666', 'canais': ['whatsapp']},
        headers=h,
    ).json()
    criado = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, nome='Outro', sobrenome='Nome')).json()
    # A resposta não revela o nome cadastrado
    assert criado['cliente_nome'] == 'Outro'
    ficha = cliente.get(f'/api/loja/clientes/{existente["id"]}', headers=h).json()
    assert ficha['canais'] == ['whatsapp', 'site']
    assert (ficha['nome'], ficha['sobrenome']) == ('Carla', 'Lima')
    agendamento = cliente.get(f'/api/loja/agendamentos/{criado["id"]}', headers=h).json()
    assert agendamento['cliente_id'] == existente['id']
    total = consultar(
        engine_dono, 'SELECT count(*) AS n FROM clientes WHERE loja_id = :l', l=clinica.lt.loja.id
    )
    assert total[0]['n'] == 3  # Maria, João e Carla


@pytest.mark.parametrize(
    ('extra', 'campo'),
    [
        ({'telefone': '1234'}, 'telefone'),
        ({'telefone': '(01) 99999-9999'}, 'telefone'),
        ({'nome': '   '}, 'nome'),
        ({'nome': 'x' * 61}, 'nome'),
        ({'email': 'nao-e-email'}, 'email'),
        ({'status': 'confirmado'}, 'status'),  # campo desconhecido é recusado
        ({'cliente_id': '00000000-0000-0000-0000-000000000000'}, 'cliente_id'),
        ({'inicio': 'amanhã'}, 'inicio'),
    ],
)
def test_pedido_valida_os_dados(cliente, clinica, extra, campo):
    resposta = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, **extra))
    assert resposta.status_code == 422
    assert campo in {e['campo'] for e in resposta.json()['erros']}


@pytest.mark.parametrize(
    ('extra', 'codigo', 'mensagem'),
    [
        (
            {'inicio': f'{SEGUNDA}T14:10'},
            409,
            'Este horário não está mais disponível. Escolha outro horário.',
        ),
        (
            {'inicio': f'{SEGUNDA}T12:00'},
            409,
            'Este horário não está mais disponível. Escolha outro horário.',
        ),
        ({'inicio': f'{TERCA}T09:00'}, 409, 'Este horário não está mais disponível. Escolha outro horário.'),
        (
            {'inicio': '2020-01-06T09:00'},
            409,
            'Este horário não está mais disponível. Escolha outro horário.',
        ),
        ({'servico_id': None}, 422, 'Escolha o serviço.'),
        ({'local_id': 'SALA2'}, 422, 'Local não encontrado para este serviço.'),
        ({'funcionario_id': 'RECEPCAO'}, 422, 'Profissional não encontrado para este serviço.'),
    ],
)
def test_pedido_respeita_as_regras_de_agendamento(cliente, clinica, extra, codigo, mensagem):
    if extra.get('local_id') == 'SALA2':
        extra = {'local_id': clinica.sala2}
    if extra.get('funcionario_id') == 'RECEPCAO':
        extra = {'funcionario_id': str(clinica.lt.recepcao.id)}
    resposta = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, **extra))
    assert resposta.status_code == codigo, resposta.json()
    assert resposta.json()['detail'] == mensagem


def test_pedido_com_local_escolhido(cliente, clinica):
    criado = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, local_id=clinica.sala1)).json()
    assert criado['local']['nome'] == 'Sala 1'
    # Outro profissional no mesmo horário e local: o local está ocupado
    resposta = cliente.post(
        f'{SITE}/agendamentos',
        json=pedido(
            clinica, funcionario_id=str(clinica.lt.admin.id), local_id=clinica.sala1, telefone='11944443333'
        ),
    )
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == 'Este local já está ocupado nesse horário. Escolha outro horário.'


# --- Isolamento entre lojas ---------------------------------------------------------------------


def test_site_de_uma_loja_nao_enxerga_a_outra(cliente, clinica):
    # loja-b (vazia) não lista os serviços nem os locais da loja-a
    assert cliente.get('/api/site/loja-b/servicos').json() == []
    assert cliente.get('/api/site/loja-b/locais').json() == []
    # Serviço, profissional e local da loja-a pelo site da loja-b
    servico = cliente.get(
        '/api/site/loja-b/horarios', params={'servico_id': clinica.limpeza, 'inicio': SEGUNDA}
    )
    assert servico.status_code == 422
    assert servico.json()['detail'] == 'Serviço não encontrado.'
    resposta = cliente.post('/api/site/loja-b/agendamentos', json=pedido(clinica))
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == 'Serviço não encontrado.'


def test_pedido_na_outra_loja_nao_reaproveita_cliente_da_primeira(cliente, engine_dono, clinica):
    """O mesmo telefone em duas lojas gera dois cadastros independentes (estrutura.md, 2.7)."""
    assert cliente.post(f'{SITE}/agendamentos', json=pedido(clinica)).status_code == 201
    por_loja = consultar(
        engine_dono,
        'SELECT l.slug, count(c.id) AS n FROM lojas l LEFT JOIN clientes c ON c.loja_id = l.id'
        ' GROUP BY l.slug ORDER BY l.slug',
    )
    assert [(r['slug'], r['n']) for r in por_loja] == [('loja-a', 3), ('loja-b', 0)]


def test_corrida_entre_dois_pedidos_o_banco_recusa(cliente, clinica, monkeypatch):
    """Se outro pedido ocupar o horário entre a consulta e a gravação, o EXCLUDE do banco recusa."""
    from app.services.horarios_livres import Agenda

    assert cliente.post(f'{SITE}/agendamentos', json=pedido(clinica)).status_code == 201
    # Simula a corrida: a consulta não enxerga a ocupação gravada pelo primeiro pedido
    monkeypatch.setattr(Agenda, '_sobrepoe', staticmethod(lambda *_: False))
    resposta = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica, telefone='11933332222'))
    assert resposta.status_code == 409
    assert resposta.json()['detail'] in (
        'O profissional já tem um agendamento nesse horário.',
        'Este local já está ocupado nesse horário.',
    )


def test_pedido_em_loja_suspensa_responde_404(cliente, engine_dono, clinica):
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE lojas SET status = 'suspensa' WHERE slug = 'loja-a'"))
    resposta = cliente.post(f'{SITE}/agendamentos', json=pedido(clinica))
    assert resposta.status_code == 404
