"""Notificações: eventos da agenda (NOT-01 a NOT-04) e o sino do painel (NOT-06).

Usa a loja de tests/clinica.py: Maria (11) 98888-1111 sem e-mail; Limpeza (60 min) com Admin e Profissional,
locais Sala 1 e Online; jornada às segundas (2030-01-07 é segunda).
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.auth.tokens import criar_token
from app.services import agendamentos as servico_agendamentos
from app.services.notificacoes import MSG_SEM_EMAIL, MSG_SEM_SMTP, MSG_WHATSAPP, hora, quando
from tests.clinica import SEGUNDA

SITE = '/api/site/loja-a'
MOTIVO = 'Profissional doente'


# --- Ajudantes ------------------------------------------------------------------------------------


def avisos(engine, **filtro) -> list[dict]:
    """Notificações gravadas (todas as lojas), na ordem de criação."""
    with engine.connect() as conexao:
        linhas = (
            conexao.execute(
                text(
                    'SELECT id, loja_id, tipo, evento, cliente_id, funcionario_id, agendamento_id, titulo, mensagem,'
                    ' status_site, visualizada_em, status_email, email_destino, email_erro, status_whatsapp,'
                    ' whatsapp_erro FROM notificacoes ORDER BY criado_em, evento, id'
                )
            )
            .mappings()
            .all()
        )
    return [dict(linha) for linha in linhas if all(linha[k] == v for k, v in filtro.items())]


def ligar_smtp(engine, loja_id) -> None:
    with engine.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE loja_configuracoes SET smtp_ativo = true, smtp_servidor = 'smtp.exemplo.com',"
                " smtp_porta = 587, smtp_seguranca = 'starttls', smtp_remetente_email = 'avisos@loja.com'"
                ' WHERE loja_id = :l'
            ),
            {'l': loja_id},
        )


def dar_email(engine, cliente_id, email='maria@example.com') -> None:
    with engine.begin() as conexao:
        conexao.execute(text('UPDATE clientes SET email = :e WHERE id = :c'), {'e': email, 'c': cliente_id})


def criar_no_painel(cliente, clinica, **extra) -> dict:
    resposta = cliente.post('/api/loja/agendamentos', json=clinica.dados(**extra), headers=clinica.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def mudar(cliente, clinica, ag_id, situacao, motivo=None, headers=None):
    corpo = {'status': situacao, **({'motivo_cancelamento': motivo} if motivo else {})}
    return cliente.post(
        f'/api/loja/agendamentos/{ag_id}/status', json=corpo, headers=headers or clinica.lt.h_admin
    )


def pedir_pelo_site(cliente, clinica, **extra) -> str:
    corpo = {
        'servico_id': clinica.limpeza,
        'funcionario_id': str(clinica.lt.prof.id),
        'local_id': clinica.sala1,
        'inicio': f'{SEGUNDA}T14:00',
        'nome': 'Ana',
        'sobrenome': 'Souza',
        'telefone': '(11) 97777-6666',
        'email': 'ana@example.com',
        **extra,
    }
    resposta = cliente.post(f'{SITE}/agendamentos', json=corpo)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()['id']


# --- Textos ---------------------------------------------------------------------------------------


def test_hora_no_padrao_do_painel():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    sp = ZoneInfo('America/Sao_Paulo')
    assert hora(datetime(2030, 1, 7, 9, 0)) == '9h'
    assert hora(datetime(2030, 1, 7, 9, 30)) == '9h30'
    assert hora(datetime(2030, 1, 7, 14, 5)) == '14h05'
    # 12:30 UTC = 9h30 em São Paulo (fuso da loja, GER-15)
    assert quando(datetime.fromisoformat('2030-10-15T12:30:00+00:00'), sp) == 'ter 15/10 às 9h30'


# --- Eventos do painel (NOT-02) -------------------------------------------------------------------


def test_criar_no_painel_avisa_o_cliente_sem_email(cliente, clinica, engine_dono):
    ag = criar_no_painel(cliente, clinica)
    [aviso] = avisos(engine_dono)
    assert aviso['tipo'] == 'cliente'
    assert aviso['evento'] == 'agendamento_criado'
    assert str(aviso['cliente_id']) == clinica.maria
    assert aviso['funcionario_id'] is None
    assert str(aviso['agendamento_id']) == ag['id']
    assert aviso['titulo'] == 'Horário agendado'
    assert aviso['mensagem'] == 'Loja loja-a agendou Limpeza para seg 07/01 às 9h com Profissional (Sala 1).'
    assert (aviso['status_site'], aviso['visualizada_em']) == (1, None)
    assert (aviso['status_email'], aviso['email_destino'], aviso['email_erro']) == (4, None, MSG_SEM_EMAIL)
    assert (aviso['status_whatsapp'], aviso['whatsapp_erro']) == (4, MSG_WHATSAPP)


def test_canal_de_email_conforme_o_cadastro_e_o_smtp_da_loja(cliente, clinica, engine_dono):
    dar_email(engine_dono, clinica.maria)
    criar_no_painel(cliente, clinica)
    [sem_smtp] = avisos(engine_dono)
    assert (sem_smtp['status_email'], sem_smtp['email_destino'], sem_smtp['email_erro']) == (
        3,
        'maria@example.com',
        MSG_SEM_SMTP,
    )
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T10:00')
    com_smtp = avisos(engine_dono)[-1]
    assert (com_smtp['status_email'], com_smtp['email_destino'], com_smtp['email_erro']) == (
        1,
        'maria@example.com',
        None,
    )


def test_sem_os_modulos_servicos_e_locais_a_mensagem_usa_atendimento_e_nao_cita_local(
    cliente, clinica, engine_dono
):
    from tests.fabricas import mudar_modulo

    loja_id = clinica.lt.loja.id
    mudar_modulo(engine_dono, loja_id, 'servicos', habilitado=False)
    mudar_modulo(engine_dono, loja_id, 'locais', habilitado=False)
    corpo = {
        'cliente_id': clinica.maria,
        'funcionario_id': str(clinica.lt.prof.id),
        'inicio': f'{SEGUNDA}T09:30',
        'duracao_minutos': 30,
    }
    resposta = cliente.post('/api/loja/agendamentos', json=corpo, headers=clinica.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    [aviso] = avisos(engine_dono)
    assert aviso['mensagem'] == 'Loja loja-a agendou Atendimento para seg 07/01 às 9h30 com Profissional.'


def test_confirmar_e_cancelar_avisam_sem_o_motivo(cliente, clinica, engine_dono):
    ag = criar_no_painel(cliente, clinica)
    assert mudar(cliente, clinica, ag['id'], 'confirmado').status_code == 200
    assert mudar(cliente, clinica, ag['id'], 'cancelado', MOTIVO).status_code == 200
    eventos = [(a['evento'], a['titulo']) for a in avisos(engine_dono)]
    assert eventos == [
        ('agendamento_criado', 'Horário agendado'),
        ('confirmado', 'Horário confirmado'),
        ('cancelado', 'Horário cancelado'),
    ]
    cancelado = avisos(engine_dono, evento='cancelado')[0]
    assert MOTIVO not in cancelado['mensagem']
    assert (
        cancelado['mensagem']
        == 'Loja loja-a cancelou Limpeza de seg 07/01 às 9h. Para remarcar, fale com a loja.'
    )


def test_concluir_nao_compareceu_e_reabrir_nao_avisam(cliente, clinica, engine_dono):
    concluido = criar_no_painel(cliente, clinica)
    faltou = criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T10:00')
    assert mudar(cliente, clinica, concluido['id'], 'confirmado').status_code == 200
    antes = len(avisos(engine_dono))
    pagar = cliente.post(
        f'/api/loja/agendamentos/{concluido["id"]}/pagamento',
        json={'forma': 'pix', 'valor': 200},
        headers=clinica.lt.h_admin,
    )
    assert pagar.status_code == 200  # concluir = registrar o pagamento (AGE-26)
    assert mudar(cliente, clinica, concluido['id'], 'confirmado').status_code == 200  # reabrir
    assert mudar(cliente, clinica, faltou['id'], 'nao_compareceu').status_code == 200
    assert mudar(cliente, clinica, faltou['id'], 'confirmado').status_code == 200  # reabrir (Administrador)
    assert len(avisos(engine_dono)) == antes


def test_editar_horario_avisa_e_editar_observacoes_nao(cliente, clinica, engine_dono):
    ag = criar_no_painel(cliente, clinica)
    h = clinica.lt.h_admin
    resposta = cliente.put(
        f'/api/loja/agendamentos/{ag["id"]}', json=clinica.dados(observacoes='Trazer exames'), headers=h
    )
    assert resposta.status_code == 200
    assert [a['evento'] for a in avisos(engine_dono)] == ['agendamento_criado']
    resposta = cliente.put(
        f'/api/loja/agendamentos/{ag["id"]}', json=clinica.dados(inicio=f'{SEGUNDA}T11:00'), headers=h
    )
    assert resposta.status_code == 200
    alterado = avisos(engine_dono, evento='horario_alterado')
    assert len(alterado) == 1
    assert alterado[0]['mensagem'] == (
        'Loja loja-a alterou o seu horário de Limpeza: agora é seg 07/01 às 11h com Profissional (Sala 1).'
    )
    # Trocar o local também avisa; cancelar junto com a troca, não (agendamento final)
    cliente.put(
        f'/api/loja/agendamentos/{ag["id"]}',
        json=clinica.dados(inicio=f'{SEGUNDA}T11:00', local_id=clinica.online),
        headers=h,
    )
    assert len(avisos(engine_dono, evento='horario_alterado')) == 2
    resposta = cliente.put(
        f'/api/loja/agendamentos/{ag["id"]}',
        json=clinica.dados(inicio=f'{SEGUNDA}T15:00', status='cancelado', motivo_cancelamento=MOTIVO),
        headers=h,
    )
    assert resposta.status_code == 200, resposta.json()
    assert len(avisos(engine_dono, evento='horario_alterado')) == 2
    assert len(avisos(engine_dono, evento='cancelado')) == 1


def test_aceitar_e_recusar_pedido_do_site(cliente, clinica, engine_dono):
    aceito = pedir_pelo_site(cliente, clinica)
    recusado = pedir_pelo_site(cliente, clinica, inicio=f'{SEGUNDA}T15:00', telefone='(11) 97777-5555')
    h = clinica.lt.h_admin
    assert cliente.post(f'/api/loja/agendamentos/{aceito}/aceitar', headers=h).status_code == 200
    resposta = cliente.post(
        f'/api/loja/agendamentos/{recusado}/recusar', json={'motivo_cancelamento': MOTIVO}, headers=h
    )
    assert resposta.status_code == 200
    [confirmado] = avisos(engine_dono, evento='confirmado')
    assert str(confirmado['agendamento_id']) == aceito
    assert (
        confirmado['mensagem']
        == 'Loja loja-a confirmou Limpeza em seg 07/01 às 14h com Profissional (Sala 1).'
    )
    [recusa] = avisos(engine_dono, evento='cancelado')
    assert str(recusa['agendamento_id']) == recusado
    assert recusa['titulo'] == 'Pedido não confirmado'
    assert MOTIVO not in recusa['mensagem']


def test_mudanca_de_status_desfeita_nao_deixa_notificacao(cliente, clinica, engine_dono, monkeypatch):
    ag = criar_no_painel(cliente, clinica)
    original = servico_agendamentos.avisar_mudanca_de_status

    def avisar_e_falhar(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(409, 'Falha depois do aviso.')

    monkeypatch.setattr(servico_agendamentos, 'avisar_mudanca_de_status', avisar_e_falhar)
    assert mudar(cliente, clinica, ag['id'], 'confirmado').status_code == 409
    assert [a['evento'] for a in avisos(engine_dono)] == ['agendamento_criado']
    assert cliente.get(f'/api/loja/agendamentos/{ag["id"]}', headers=clinica.lt.h_admin).json()['status'] == (
        'agendado'
    )


# --- Eventos do site (NOT-02, NOT-03) ---------------------------------------------------------------


def test_pedido_do_site_avisa_o_cliente_e_so_o_profissional(cliente, clinica, engine_dono):
    ag = pedir_pelo_site(cliente, clinica)
    [para_cliente] = avisos(engine_dono, tipo='cliente')
    assert para_cliente['evento'] == 'pedido_recebido'
    assert para_cliente['mensagem'] == (
        'Recebemos o seu pedido de Limpeza para seg 07/01 às 14h com Profissional (Sala 1). '
        'Loja loja-a vai confirmar o horário.'
    )
    assert (para_cliente['status_email'], para_cliente['email_erro']) == (3, MSG_SEM_SMTP)
    [para_loja] = avisos(engine_dono, tipo='loja')
    assert para_loja['evento'] == 'novo_pedido'
    assert para_loja['funcionario_id'] == clinica.lt.prof.id
    assert str(para_loja['agendamento_id']) == ag
    assert para_loja['titulo'] == 'Novo pedido pelo site'
    assert para_loja['mensagem'] == 'Ana Souza pediu Limpeza para seg 07/01 às 14h.'
    assert (para_loja['status_whatsapp'], para_loja['status_email']) == (4, 3)


def test_pedido_do_site_com_smtp_deixa_os_emails_pendentes(cliente, clinica, engine_dono):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    pedir_pelo_site(cliente, clinica)
    destinos = {a['tipo']: (a['status_email'], a['email_destino']) for a in avisos(engine_dono)}
    assert destinos == {'cliente': (1, 'ana@example.com'), 'loja': (1, 'prof@loja-a.com')}


# --- Sino do painel (NOT-06) --------------------------------------------------------------------------


def sino(cliente, headers, **params):
    resposta = cliente.get('/api/loja/notificacoes', params=params, headers=headers)
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def test_sino_lista_so_as_do_funcionario(cliente, clinica, lojas, engine_dono):
    ag = pedir_pelo_site(cliente, clinica)
    lt = clinica.lt
    lista = sino(cliente, lt.h_prof)
    assert (lista['total'], lista['pagina'], lista['por_pagina'], lista['nao_visualizadas']) == (1, 1, 20, 1)
    [item] = lista['itens']
    assert set(item) == {
        'id',
        'evento',
        'titulo',
        'mensagem',
        'agendamento_id',
        'inicio_agendamento',
        'visualizada',
        'visualizada_em',
        'status_email',
        'status_whatsapp',
        'criado_em',
    }
    assert item['evento'] == 'novo_pedido'
    assert item['agendamento_id'] == ag
    assert item['inicio_agendamento'] == f'{SEGUNDA}T14:00:00-03:00'
    assert (item['visualizada'], item['visualizada_em']) == (False, None)
    assert (item['status_email'], item['status_whatsapp']) == (3, 4)
    assert item['criado_em'].endswith('-03:00')
    # Outros funcionários da loja e a loja B não veem
    for headers in (lt.h_admin, lt.h_recepcao, lojas[1].h_admin):
        vazio = sino(cliente, headers)
        assert (vazio['itens'], vazio['total'], vazio['nao_visualizadas']) == ([], 0, 0)
        assert cliente.get('/api/loja/notificacoes/resumo', headers=headers).json() == {'nao_visualizadas': 0}
    assert cliente.get('/api/loja/notificacoes/resumo', headers=lt.h_prof).json() == {'nao_visualizadas': 1}


def test_visualizar_marca_so_as_suas_e_e_idempotente(cliente, clinica, lojas, engine_dono):
    pedir_pelo_site(cliente, clinica)
    lt = clinica.lt
    [item] = sino(cliente, lt.h_prof)['itens']
    # De outro funcionário, de outra loja ou inexistente: ignorado em silêncio
    for headers in (lt.h_admin, lt.h_recepcao, lojas[1].h_admin):
        resposta = cliente.post(
            '/api/loja/notificacoes/visualizar', json={'ids': [item['id']]}, headers=headers
        )
        assert resposta.status_code == 200
        assert resposta.json() == {'marcadas': 0, 'nao_visualizadas': 0}
    assert avisos(engine_dono, tipo='loja')[0]['status_site'] == 1

    corpo = {'ids': [item['id'], str(uuid4())]}
    resposta = cliente.post('/api/loja/notificacoes/visualizar', json=corpo, headers=lt.h_prof)
    assert resposta.json() == {'marcadas': 1, 'nao_visualizadas': 0}
    marcada = avisos(engine_dono, tipo='loja')[0]
    assert (marcada['status_site'], marcada['visualizada_em'] is not None) == (2, True)
    de_novo = cliente.post('/api/loja/notificacoes/visualizar', json=corpo, headers=lt.h_prof)
    assert de_novo.json() == {'marcadas': 0, 'nao_visualizadas': 0}
    assert avisos(engine_dono, tipo='loja')[0]['visualizada_em'] == marcada['visualizada_em']
    [lida] = sino(cliente, lt.h_prof)['itens']
    assert lida['visualizada'] is True
    assert lida['visualizada_em'].endswith('-03:00')


def test_marcar_so_as_mostradas_a_que_chegou_depois_continua(cliente, clinica, engine_dono):
    pedir_pelo_site(cliente, clinica)
    [mostrada] = sino(cliente, clinica.lt.h_prof)['itens']
    pedir_pelo_site(cliente, clinica, inicio=f'{SEGUNDA}T15:00', telefone='(11) 97777-5555')  # chega depois
    resposta = cliente.post(
        '/api/loja/notificacoes/visualizar', json={'ids': [mostrada['id']]}, headers=clinica.lt.h_prof
    )
    assert resposta.json() == {'marcadas': 1, 'nao_visualizadas': 1}


def test_acesso_de_suporte_nao_marca(cliente, clinica, engine_dono):
    pedir_pelo_site(cliente, clinica, funcionario_id=str(clinica.lt.admin.id))
    admin = clinica.lt.admin
    token, _ = criar_token(admin.id, 'funcionario', admin.loja_id, suporte=True)
    suporte = {'Authorization': f'Bearer {token}'}
    [item] = sino(cliente, suporte)['itens']
    resposta = cliente.post('/api/loja/notificacoes/visualizar', json={'ids': [item['id']]}, headers=suporte)
    assert resposta.status_code == 200
    assert resposta.json() == {'marcadas': 0, 'nao_visualizadas': 1}
    assert avisos(engine_dono, tipo='loja')[0]['status_site'] == 1


@pytest.mark.parametrize(
    'corpo',
    [{'ids': []}, {'ids': [str(uuid4()) for _ in range(101)]}, {'ids': ['nao-e-uuid']}, {}],
)
def test_visualizar_valida_a_lista(cliente, clinica, corpo):
    resposta = cliente.post('/api/loja/notificacoes/visualizar', json=corpo, headers=clinica.lt.h_prof)
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == 'Verifique os dados informados.'
    assert resposta.json()['erros'][0]['campo'].startswith('ids')


@pytest.mark.parametrize('params', [{'por_pagina': 51}, {'pagina': 0}, {'por_pagina': 'x'}])
def test_paginacao_do_sino_invalida(cliente, clinica, params):
    resposta = cliente.get('/api/loja/notificacoes', params=params, headers=clinica.lt.h_prof)
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == 'Verifique os dados informados.'


def test_paginacao_mais_novas_primeiro_e_agendamento_excluido_sem_link(cliente, clinica, engine_dono):
    primeiro = pedir_pelo_site(cliente, clinica)
    pedir_pelo_site(cliente, clinica, inicio=f'{SEGUNDA}T15:00', telefone='(11) 97777-5555')
    with engine_dono.begin() as conexao:  # o primeiro aviso fica mais antigo
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text(
                "UPDATE notificacoes SET criado_em = criado_em - interval '1 hour' WHERE agendamento_id = :a"
            ),
            {'a': primeiro},
        )
    h = clinica.lt.h_prof
    pagina1 = sino(cliente, h, por_pagina=1)
    pagina2 = sino(cliente, h, por_pagina=1, pagina=2)
    assert (pagina1['total'], pagina2['total']) == (2, 2)
    assert pagina1['itens'][0]['mensagem'].endswith('às 15h.')
    assert pagina2['itens'][0]['agendamento_id'] == primeiro
    assert sino(cliente, h, pagina=3)['itens'] == []

    assert cliente.delete(f'/api/loja/agendamentos/{primeiro}', headers=clinica.lt.h_admin).status_code == 204
    excluido = sino(cliente, h, por_pagina=1, pagina=2)['itens'][0]
    assert (excluido['agendamento_id'], excluido['inicio_agendamento']) == (None, None)


def test_profissional_inativo_nao_recebe(cliente, clinica, engine_dono):
    ag = criar_no_painel(cliente, clinica)
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE funcionarios SET ativo = false WHERE id = :f'), {'f': clinica.lt.prof.id}
        )
    from app.models import Agendamento, Loja
    from app.services.notificacoes import LojaAviso, avisar_cancelamento_do_site
    from tests.fabricas import sessao

    with sessao(engine_dono, origem='site', loja_id=clinica.lt.loja.id) as db:
        loja = db.get(Loja, clinica.lt.loja.id)
        agendamento = db.get(Agendamento, ag['id'])
        avisar_cancelamento_do_site(db, LojaAviso.de(loja, {'servicos': True, 'locais': True}), agendamento)
    assert avisos(engine_dono, tipo='loja') == []


def test_status_de_um_canal_so_avanca(cliente, clinica, engine_dono):
    from sqlalchemy.exc import IntegrityError

    criar_no_painel(cliente, clinica)  # e-mail 4 e WhatsApp 4 (finais)
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE notificacoes SET status_site = 2, visualizada_em = now()'))
    for sql in (
        "UPDATE notificacoes SET status_email = 1, email_destino = 'x@y.com', email_erro = NULL",
        'UPDATE notificacoes SET status_whatsapp = 2',
        'UPDATE notificacoes SET status_site = 1, visualizada_em = NULL',
    ):
        with pytest.raises(IntegrityError, match='não volta atrás'), engine_dono.begin() as conexao:
            conexao.execute(text(sql))
