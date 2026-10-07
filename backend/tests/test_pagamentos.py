"""Pagamento do atendimento (AGE-26 a AGE-29, SIT-26): concluir só registrando o pagamento.

Usa a loja de tests/clinica.py: Limpeza (60 min, R$ 200, 2 luvas, Admin e Profissional, Sala 1 e Online),
10 luvas no estoque, jornada às segundas (2030-01-07 é segunda).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Agendamento, AgendamentoPagamento
from app.models.enums import FormaPagamento, OrigemAgendamento, StatusAgendamento
from app.routers.site.conta import NBSP, situacao_no_site
from app.services import agendamentos as regras
from app.services.conta_cliente import MeuAgendamento
from tests.clinica import SEGUNDA, Clinica
from tests.concorrencia import rajada
from tests.fabricas import inserir, mudar_modulo, sessao, usuario_com
from tests.test_conta_cliente import criar_conta, minha_conta

URL = '/api/loja/agendamentos'
PIX = {'forma': 'pix', 'valor': 50}
MSG_CONCLUIR = 'Para concluir o atendimento, registre o pagamento.'
MSG_JA_PAGO = 'Este atendimento já está pago.'
S = StatusAgendamento


def _criar(cliente, c: Clinica, cab=None, **extra) -> dict:
    resposta = cliente.post(URL, json=c.dados(**extra), headers=cab or c.lt.h_admin)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def _confirmado(cliente, c: Clinica, **extra) -> dict:
    return _criar(cliente, c, status='confirmado', **extra)


def _pagar(cliente, c: Clinica, ag_id, corpo=None, cab=None):
    return cliente.post(f'{URL}/{ag_id}/pagamento', json=corpo or PIX, headers=cab or c.lt.h_admin)


def _erro(resposta, codigo) -> str:
    assert resposta.status_code == codigo, resposta.json()
    return resposta.json()['detail']


def _um(engine, sql, **params):
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).scalar()


def _luvas(engine, c: Clinica) -> Decimal:
    return _um(engine, 'SELECT quantidade_atual FROM materiais WHERE id = :i', i=c.luvas)


def _pagamentos(engine, ag_id) -> list:
    with engine.connect() as conexao:
        return conexao.execute(
            select(AgendamentoPagamento)
            .where(AgendamentoPagamento.agendamento_id == ag_id)
            .order_by(AgendamentoPagamento.criado_em)
            .execution_options(incluir_excluidos=True)
        ).all()


def _inserir_agendamento(engine, c: Clinica, hora: str, status: StatusAgendamento, **extra):
    inicio = datetime.fromisoformat(f'{SEGUNDA}T{hora}-03:00').astimezone(UTC)
    return inserir(
        engine,
        Agendamento(
            loja_id=c.lt.loja.id,
            cliente_id=c.maria,
            servico_id=c.limpeza,
            funcionario_id=c.lt.prof.id,
            local_id=c.sala1,
            inicio=inicio,
            fim=inicio + timedelta(hours=1),
            preco=200,
            status=status,
            **extra,
        ),
    ).id


# --- AGE-26 e AGE-27: registrar o pagamento conclui --------------------------------------------------


def test_recepcao_registra_pagamento_e_conclui_com_baixa(cliente, clinica, engine_dono):
    c = clinica
    ag = _confirmado(cliente, c)
    resposta = _pagar(cliente, c, ag['id'], cab=c.lt.h_recepcao)
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert corpo['status'] == 'concluido'
    assert corpo['preco'] == 200  # o preço do agendamento não muda (AGE-27)
    assert corpo['materiais'] == [{'material_id': c.luvas, 'nome': 'Luvas', 'unidade': 'un', 'quantidade': 2}]
    pagamento = corpo['pagamento']
    assert set(pagamento) == {'id', 'forma', 'valor', 'pago_em', 'registrado_por_nome'}
    assert (pagamento['forma'], pagamento['valor'], pagamento['registrado_por_nome']) == (
        'pix',
        50,
        'Recepção',
    )
    assert pagamento['pago_em'].endswith('-03:00')  # fuso da loja
    pago_em = datetime.fromisoformat(pagamento['pago_em'])
    assert abs(datetime.now(UTC) - pago_em) < timedelta(minutes=1)  # hora do servidor
    assert _luvas(engine_dono, c) == 8  # AGE-20: baixa na mesma operação

    [linha] = _pagamentos(engine_dono, ag['id'])
    assert (linha.forma, linha.valor, linha.criado_por) == (
        FormaPagamento.pix,
        Decimal('50.00'),
        c.lt.recepcao.id,
    )
    assert linha.excluido_em is None
    auditoria = _um(
        engine_dono,
        "SELECT origem::text || ':' || funcionario_id::text FROM auditoria"
        " WHERE tabela = 'agendamento_pagamentos' AND operacao = 'inserir'",
    )
    assert auditoria == f'painel:{c.lt.recepcao.id}'

    detalhe = cliente.get(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).json()
    assert detalhe['pagamento'] == pagamento


@pytest.mark.parametrize('forma', ['credito', 'debito', 'dinheiro', 'pix'])
def test_todas_as_formas(cliente, clinica, forma):
    ag = _confirmado(cliente, clinica)
    resposta = _pagar(cliente, clinica, ag['id'], {'forma': forma, 'valor': 200})
    assert resposta.json()['pagamento']['forma'] == forma


@pytest.mark.parametrize(('valor', 'esperado'), [(0, 0), ('99999999.99', 99999999.99), (12.5, 12.5)])
def test_valor_zero_e_limite_aceitos(cliente, clinica, valor, esperado):
    ag = _confirmado(cliente, clinica)
    resposta = _pagar(cliente, clinica, ag['id'], {'forma': 'dinheiro', 'valor': valor})
    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()['pagamento']['valor'] == esperado


@pytest.mark.parametrize(
    ('corpo', 'campo', 'mensagem'),
    [
        ({'forma': 'boleto', 'valor': 50}, 'forma', 'Opção inválida.'),
        ({'forma': None, 'valor': 50}, 'forma', 'Opção inválida.'),
        ({'valor': 50}, 'forma', 'Campo obrigatório.'),
        ({'forma': 'pix'}, 'valor', 'Campo obrigatório.'),
        ({'forma': 'pix', 'valor': None}, 'valor', 'Informe um número.'),
        ({'forma': 'pix', 'valor': -0.01}, 'valor', 'O valor deve ser maior ou igual a 0.'),
        ({'forma': 'pix', 'valor': 50.123}, 'valor', 'Use no máximo 2 casas decimais.'),
        ({'forma': 'pix', 'valor': 100000000}, 'valor', 'Valor fora do limite permitido.'),
        ({'forma': 'pix', 'valor': 'abc'}, 'valor', 'Informe um número.'),
        ({'forma': 'pix', 'valor': True}, 'valor', 'Informe um número.'),
    ],
)
def test_forma_e_valor_invalidos(cliente, clinica, engine_dono, corpo, campo, mensagem):
    c = clinica
    ag = _confirmado(cliente, c)
    resposta = _pagar(cliente, c, ag['id'], corpo)
    assert _erro(resposta, 422) == 'Verifique os dados informados.'
    assert {'campo': campo, 'mensagem': mensagem} in resposta.json()['erros']
    assert cliente.get(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).json()['status'] == 'confirmado'
    assert _pagamentos(engine_dono, ag['id']) == []


def test_corpo_vazio_e_campos_extras(cliente, clinica):
    c = clinica
    ag = _confirmado(cliente, c)
    vazio = cliente.post(f'{URL}/{ag["id"]}/pagamento', headers=c.lt.h_admin)
    assert _erro(vazio, 422) == 'Verifique os dados informados.'
    # Campos fora do contrato são ignorados (sem atribuição em massa: só forma e valor são lidos)
    extra = _pagar(cliente, c, ag['id'], {**PIX, 'criado_por': str(c.lt.admin.id), 'pago_em': '2000-01-01'})
    assert extra.status_code == 200
    assert extra.json()['pagamento']['registrado_por_nome'] == 'Admin'
    assert not extra.json()['pagamento']['pago_em'].startswith('2000')


# --- AGE-26: só a partir de confirmado; /status e PUT não concluem ----------------------------------


def test_status_e_put_com_concluido_dao_422(cliente, clinica, engine_dono):
    c = clinica
    ag = _confirmado(cliente, c)
    url = f'{URL}/{ag["id"]}'
    assert _erro(cliente.post(f'{url}/status', json={'status': 'concluido'}, headers=c.lt.h_admin), 422) == (
        MSG_CONCLUIR
    )
    put = cliente.put(url, json=c.dados(status='concluido'), headers=c.lt.h_admin)
    assert _erro(put, 422) == MSG_CONCLUIR
    agendado = _criar(cliente, c, inicio=f'{SEGUNDA}T13:00')
    pular = cliente.post(f'{URL}/{agendado["id"]}/status', json={'status': 'concluido'}, headers=c.lt.h_admin)
    assert _erro(pular, 422) == MSG_CONCLUIR  # antes de olhar a transição
    assert cliente.get(url, headers=c.lt.h_admin).json()['status'] == 'confirmado'
    assert _luvas(engine_dono, c) == 10

    # Já concluído: continua 422 (nunca vira "mesmo status, nada a fazer")
    assert _pagar(cliente, c, ag['id']).status_code == 200
    de_novo = cliente.post(f'{url}/status', json={'status': 'concluido'}, headers=c.lt.h_admin)
    assert _erro(de_novo, 422) == MSG_CONCLUIR
    assert (
        _erro(cliente.put(url, json=c.dados(status='concluido'), headers=c.lt.h_admin), 422) == MSG_CONCLUIR
    )


def test_pagamento_so_a_partir_de_confirmado(cliente, clinica, engine_dono):
    c = clinica
    agendado = _criar(cliente, c)
    pendente = _inserir_agendamento(engine_dono, c, '10:00', S.pendente, origem=OrigemAgendamento.site)
    cancelado = _inserir_agendamento(engine_dono, c, '13:00', S.cancelado, motivo_cancelamento='Desistiu')
    faltou = _inserir_agendamento(engine_dono, c, '14:00', S.nao_compareceu)
    for ag_id, rotulo in (
        (agendado['id'], 'Agendado'),
        (pendente, 'Aguardando aceite'),
        (cancelado, 'Cancelado'),
        (faltou, 'Não compareceu'),
    ):
        resposta = _pagar(cliente, c, ag_id)
        assert _erro(resposta, 409) == f'Não é possível passar de "{rotulo}" para "Concluído".'
        assert _pagamentos(engine_dono, ag_id) == []
    assert _luvas(engine_dono, c) == 10


def test_ja_concluido_responde_ja_pago(cliente, clinica, engine_dono):
    c = clinica
    ag = _confirmado(cliente, c)
    assert _pagar(cliente, c, ag['id']).status_code == 200
    segundo = _pagar(cliente, c, ag['id'], {'forma': 'dinheiro', 'valor': 10})
    assert _erro(segundo, 409) == MSG_JA_PAGO
    assert len(_pagamentos(engine_dono, ag['id'])) == 1
    assert _luvas(engine_dono, c) == 8  # sem segunda baixa


# --- AGE-29: concluídos antigos sem pagamento ------------------------------------------------------


def test_concluido_antigo_sem_pagamento(cliente, clinica, engine_dono):
    c = clinica
    antigo = _inserir_agendamento(engine_dono, c, '09:00', S.concluido)
    detalhe = cliente.get(f'{URL}/{antigo}', headers=c.lt.h_admin).json()
    assert (detalhe['status'], detalhe['pagamento']) == ('concluido', None)
    lista = cliente.get(URL, headers=c.lt.h_admin).json()
    assert lista['itens'][0]['pagamento'] is None
    assert _erro(_pagar(cliente, c, antigo), 409) == MSG_JA_PAGO  # reabra para registrar


# --- AGE-28: reabrir exclui o pagamento --------------------------------------------------------------


def test_reabrir_exclui_o_pagamento_e_concluir_de_novo_exige_outro(cliente, clinica, engine_dono):
    c = clinica
    ag = _confirmado(cliente, c)
    primeiro = _pagar(cliente, c, ag['id']).json()['pagamento']
    status = f'{URL}/{ag["id"]}/status'

    recepcao = cliente.post(status, json={'status': 'confirmado'}, headers=c.lt.h_recepcao)
    assert _erro(recepcao, 403) == 'Só o Administrador pode reabrir um agendamento "Concluído".'
    assert len([p for p in _pagamentos(engine_dono, ag['id']) if p.excluido_em is None]) == 1

    reaberto = cliente.post(status, json={'status': 'confirmado'}, headers=c.lt.h_admin).json()
    assert (reaberto['status'], reaberto['pagamento']) == ('confirmado', None)
    assert _luvas(engine_dono, c) == 10  # estorno (AGE-20)
    [excluido] = _pagamentos(engine_dono, ag['id'])
    assert excluido.excluido_em is not None
    assert excluido.excluido_por == c.lt.admin.id
    assert (
        _um(
            engine_dono,
            "SELECT count(*) FROM auditoria WHERE tabela = 'agendamento_pagamentos' AND operacao = 'excluir'"
            ' AND registro_id = :r',
            r=primeiro['id'],
        )
        == 1
    )

    segundo = _pagar(cliente, c, ag['id'], {'forma': 'dinheiro', 'valor': 180})
    assert segundo.status_code == 200
    novo = segundo.json()['pagamento']
    assert novo['id'] != primeiro['id']
    assert (novo['forma'], novo['valor']) == ('dinheiro', 180)
    assert _luvas(engine_dono, c) == 8
    assert len(_pagamentos(engine_dono, ag['id'])) == 2  # o antigo fica (excluído logicamente)


def test_reabrir_pela_edicao_tambem_exclui_o_pagamento(cliente, clinica, engine_dono):
    c = clinica
    ag = _confirmado(cliente, c)
    assert _pagar(cliente, c, ag['id']).status_code == 200
    editado = cliente.put(f'{URL}/{ag["id"]}', json=c.dados(status='confirmado'), headers=c.lt.h_admin)
    assert editado.status_code == 200, editado.json()
    assert editado.json()['pagamento'] is None
    assert [p.excluido_em is not None for p in _pagamentos(engine_dono, ag['id'])] == [True]


def test_concluido_nao_e_editado_nem_excluido(cliente, clinica):
    c = clinica
    ag = _confirmado(cliente, c)
    assert _pagar(cliente, c, ag['id']).status_code == 200
    editar = cliente.put(f'{URL}/{ag["id"]}', json=c.dados(observacoes='x'), headers=c.lt.h_admin)
    assert 'não pode ser editado' in _erro(editar, 409)
    assert 'não pode ser excluído' in _erro(cliente.delete(f'{URL}/{ag["id"]}', headers=c.lt.h_admin), 409)


# --- Módulos ---------------------------------------------------------------------------------------


def test_sem_servicos_preco_nulo_e_sem_materiais_sem_baixa(cliente, clinica, engine_dono):
    c = clinica
    mudar_modulo(engine_dono, c.lt.loja.id, 'servicos', habilitado=False)
    mudar_modulo(engine_dono, c.lt.loja.id, 'materiais', habilitado=False)
    ag = _confirmado(cliente, c, servico_id=None, duracao_minutos=30)
    assert ag['preco'] is None
    pago = _pagar(cliente, c, ag['id'], {'forma': 'credito', 'valor': 80}).json()
    assert (pago['status'], pago['preco'], pago['pagamento']['valor']) == ('concluido', None, 80)
    assert _luvas(engine_dono, c) == 10


# --- Permissões (AGE-22) e isolamento entre lojas ---------------------------------------------------


def test_profissional_paga_os_proprios_e_nao_os_dos_outros(cliente, clinica, engine_dono):
    c = clinica
    proprio = _confirmado(cliente, c)
    do_admin = _confirmado(cliente, c, funcionario_id=str(c.lt.admin.id), inicio=f'{SEGUNDA}T13:00')

    pago = _pagar(cliente, c, proprio['id'], cab=c.lt.h_prof)
    assert pago.status_code == 200
    assert pago.json()['pagamento']['registrado_por_nome'] == 'Profissional'
    # Só Minha agenda: o do outro nem é visível (404)
    assert _erro(_pagar(cliente, c, do_admin['id'], cab=c.lt.h_prof), 404) == 'Agendamento não encontrado.'

    # Vê a equipe, mas só escreve na própria agenda: 403
    ve_equipe = usuario_com(engine_dono, c.lt.loja, {'agenda_equipe': 'leitura', 'agenda_propria': 'escrita'})
    outro = _pagar(cliente, c, do_admin['id'], cab=ve_equipe)
    assert _erro(outro, 403) == 'Você só pode alterar os seus próprios agendamentos.'
    so_leitura = usuario_com(
        engine_dono, c.lt.loja, {'agenda_equipe': 'leitura', 'agenda_propria': 'leitura'}
    )
    assert _erro(_pagar(cliente, c, do_admin['id'], cab=so_leitura), 403) == (
        'Você só tem permissão de leitura aqui.'
    )
    sem_token = cliente.post(f'{URL}/{do_admin["id"]}/pagamento', json=PIX)
    assert _erro(sem_token, 401) == 'Faça login para continuar.'
    assert _pagamentos(engine_dono, do_admin['id']) == []


def test_inexistente_ou_excluido_da_404(cliente, clinica, engine_dono):
    c = clinica
    assert (
        _erro(_pagar(cliente, c, '00000000-0000-0000-0000-000000000000'), 404)
        == 'Agendamento não encontrado.'
    )
    ag = _confirmado(cliente, c)
    assert cliente.delete(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).status_code == 204
    assert _erro(_pagar(cliente, c, ag['id']), 404) == 'Agendamento não encontrado.'
    assert _pagar(cliente, c, 'nao-e-uuid').status_code == 422


def test_loja_b_nao_registra_nem_ve_pagamento_da_loja_a(cliente, lojas, clinica, engine_dono):
    c = clinica
    _, b = lojas
    ag = _confirmado(cliente, c)
    assert _erro(_pagar(cliente, c, ag['id'], cab=b.h_admin), 404) == 'Agendamento não encontrado.'
    assert _pagamentos(engine_dono, ag['id']) == []
    assert _pagar(cliente, c, ag['id']).status_code == 200
    assert cliente.get(f'{URL}/{ag["id"]}', headers=b.h_admin).status_code == 404
    assert cliente.get(URL, headers=b.h_admin).json()['total'] == 0
    reabrir = cliente.post(f'{URL}/{ag["id"]}/status', json={'status': 'confirmado'}, headers=b.h_admin)
    assert reabrir.status_code == 404
    assert cliente.get(f'{URL}/{ag["id"]}', headers=c.lt.h_admin).json()['pagamento'] is not None


# --- Banco: invariantes (LOG-01) -----------------------------------------------------------------------


def test_banco_garante_um_ativo_valor_nao_negativo_e_mesma_loja(cliente, lojas, clinica, engine_dono):
    c = clinica
    _, b = lojas
    ag = _confirmado(cliente, c)
    assert _pagar(cliente, c, ag['id']).status_code == 200

    def gravar(**valores):
        with sessao(engine_dono) as db:
            db.add(AgendamentoPagamento(agendamento_id=ag['id'], forma=FormaPagamento.pix, **valores))

    with pytest.raises(IntegrityError, match='agendamento_pagamentos_ativo_uk'):
        gravar(loja_id=c.lt.loja.id, valor=10)
    with pytest.raises(IntegrityError, match='ck_agendamento_pagamentos_valor'):
        gravar(loja_id=c.lt.loja.id, valor=-1)
    with pytest.raises(IntegrityError, match='agendamento_pagamentos_agendamento_fk'):
        gravar(loja_id=b.loja.id, valor=10)  # agendamento de outra loja


# --- Lista e detalhe sem N+1 ----------------------------------------------------------------------------


def test_lista_traz_o_pagamento_sem_consulta_por_item(cliente, clinica, engine_app):
    c = clinica
    horas = ('08:00', '09:00', '10:00', '13:00', '14:00')
    ids = [_confirmado(cliente, c, inicio=f'{SEGUNDA}T{h}', local_id=c.online)['id'] for h in horas]
    assert _pagar(cliente, c, ids[0]).status_code == 200

    consultas: list[str] = []

    def contar(_conn, _cursor, sql, *_args):
        consultas.append(sql)

    def listar() -> tuple[dict, int]:
        consultas.clear()
        event.listen(engine_app, 'before_cursor_execute', contar)
        try:
            corpo = cliente.get(URL, headers=c.lt.h_admin).json()
        finally:
            event.remove(engine_app, 'before_cursor_execute', contar)
        return corpo, len(consultas)

    _, com_um = listar()
    for ag_id in ids[1:4]:
        assert _pagar(cliente, c, ag_id, {'forma': 'debito', 'valor': 200}).status_code == 200
    corpo, com_quatro = listar()
    assert com_quatro == com_um
    pagamentos = {i['id']: i['pagamento'] for i in corpo['itens']}
    assert pagamentos[ids[0]]['forma'] == 'pix'
    assert [pagamentos[i]['forma'] for i in ids[1:4]] == ['debito'] * 3
    assert pagamentos[ids[4]] is None


# --- Concorrência: sem a trava, o índice único segura (LOG-02) ------------------------------------------


def test_sem_a_trava_o_indice_unico_impede_dois_pagamentos(
    cliente, clinica, engine_dono, servidor, monkeypatch
):
    """A trava (FOR UPDATE) é a primeira barreira; aqui ela é desligada para provar a segunda."""
    original = regras.buscar_visivel
    monkeypatch.setattr(regras, 'buscar_visivel', lambda ctx, ag_id, travar=False: original(ctx, ag_id))
    c = clinica
    ag = _confirmado(cliente, c)
    url = f'{URL}/{ag["id"]}/pagamento'

    respostas = rajada(servidor, [('POST', url, PIX, c.lt.h_admin)] * 6)

    assert sorted(r.status_code for r in respostas) == [200] + [409] * 5
    assert {r.json()['detail'] for r in respostas if r.status_code == 409} == {MSG_JA_PAGO}
    assert len(_pagamentos(engine_dono, ag['id'])) == 1
    assert _luvas(engine_dono, c) == 8


# --- SIT-26: Minha conta do site -----------------------------------------------------------------------


def _item_do_site(status: StatusAgendamento, forma=None, valor=None) -> MeuAgendamento:
    return MeuAgendamento(
        id=None,  # type: ignore[arg-type]
        inicio=datetime.now(UTC),
        fim=datetime.now(UTC),
        status=status,
        preco=None,
        servico_nome='Limpeza',
        funcionario_nome='Profissional',
        local_nome=None,
        alteravel=False,
        servico_id=None,
        funcionario_id=None,  # type: ignore[arg-type]
        pagamento_forma=forma,
        pagamento_valor=valor,
    )


@pytest.mark.parametrize(
    ('forma', 'valor', 'texto'),
    [
        (FormaPagamento.credito, Decimal('1234.5'), 'Concluído · pago no crédito · R$ 1.234,50'),
        (FormaPagamento.debito, Decimal('0'), 'Concluído · pago no débito · R$ 0,00'),
        (FormaPagamento.dinheiro, Decimal('80'), 'Concluído · pago em dinheiro · R$ 80,00'),
        (FormaPagamento.pix, Decimal('50'), 'Concluído · pago no Pix · R$ 50,00'),
        (None, None, 'Concluído'),
    ],
)
def test_texto_da_situacao_no_site(forma, valor, texto):
    # "R$" e o número ficam juntos (espaço inseparável) para não quebrar a linha no celular
    assert situacao_no_site(_item_do_site(S.concluido, forma, valor)) == texto.replace('R$ ', f'R${NBSP}')
    assert situacao_no_site(_item_do_site(S.cancelado)) == 'Cancelado'


def test_minha_conta_mostra_forma_e_valor_sem_quem_registrou(cliente, navegador, clinica, engine_dono):
    c = clinica
    registradora = usuario_com(
        engine_dono,
        c.lt.loja,
        {'agenda_equipe': 'escrita', 'agenda_propria': 'escrita'},
        nome='Zelinda Caixa',
    )
    pago = _confirmado(cliente, c)
    assert _pagar(cliente, c, pago['id'], cab=registradora).status_code == 200
    _inserir_agendamento(engine_dono, c, '13:00', S.concluido)  # antigo, sem pagamento (AGE-29)
    reaberto = _confirmado(cliente, c, inicio=f'{SEGUNDA}T14:00')
    assert _pagar(cliente, c, reaberto['id'], {'forma': 'credito', 'valor': 70}).status_code == 200
    reabrir = cliente.post(
        f'{URL}/{reaberto["id"]}/status', json={'status': 'confirmado'}, headers=c.lt.h_admin
    )
    assert reabrir.status_code == 200

    nav = navegador()
    criar_conta(nav, engine_dono)
    pagina = minha_conta(nav)
    assert pagina.count(f'Concluído · pago no Pix · R${NBSP}50,00') == 1
    assert pagina.count('>Concluído</p>') == 1  # o antigo, sem forma
    assert 'no crédito' not in pagina  # pagamento excluído ao reabrir não aparece
    assert 'Zelinda' not in pagina  # nada de quem registrou
    assert '/painel' not in pagina  # DIR-003
    assert 'superadmin' not in pagina.lower()
