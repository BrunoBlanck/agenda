"""Corridas reais (servidor uvicorn + requisições simultâneas): estoque, último Administrador e ponto.

Cada teste dispara várias requisições ao mesmo tempo contra a API de verdade, cada uma na sua
transação. Sem as travas (FOR UPDATE / advisory lock), estes cenários davam baixa dupla no estoque,
deixavam a loja sem Administrador e duplicavam batidas de ponto.
"""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import text

from tests.clinica import SEGUNDA
from tests.concorrencia import rajada
from tests.fabricas import cabecalho, cabecalho_superadmin, criar_funcionario, criar_superadmin, sessao

API = '/api/loja'
N = 6


def _um(engine, sql, **params):
    with engine.connect() as conexao:
        return conexao.execute(text(sql), params).scalar()


def _saidas(engine, agendamento_id) -> int:
    return _um(
        engine,
        "SELECT count(*) FROM movimentacoes_estoque WHERE agendamento_id = :i AND tipo = 'saida_atendimento'",
        i=agendamento_id,
    )


def _estornos(engine, agendamento_id) -> int:
    return _um(
        engine,
        "SELECT count(*) FROM movimentacoes_estoque WHERE agendamento_id = :i AND tipo = 'ajuste'",
        i=agendamento_id,
    )


def _luvas(engine, clinica):
    return _um(engine, 'SELECT quantidade_atual FROM materiais WHERE id = :i', i=clinica.luvas)


def _pagamentos_ativos(engine, agendamento_id) -> int:
    return _um(
        engine,
        'SELECT count(*) FROM agendamento_pagamentos WHERE agendamento_id = :i AND excluido_em IS NULL',
        i=agendamento_id,
    )


PIX = {'forma': 'pix', 'valor': 200}


# --- A2: baixa e estorno de estoque ---------------------------------------------------------------


def test_pagar_ao_mesmo_tempo_grava_um_pagamento_e_baixa_o_estoque_uma_vez(
    cliente, clinica, engine_dono, servidor
):
    """AGE-26/27: o FOR UPDATE põe os registros em fila; o segundo vê o atendimento pago (409)."""
    h = clinica.lt.h_admin
    ag = cliente.post(f'{API}/agendamentos', json=clinica.dados(status='confirmado'), headers=h).json()
    url = f'{API}/agendamentos/{ag["id"]}/pagamento'

    respostas = rajada(servidor, [('POST', url, PIX, h)] * N)

    assert sorted(r.status_code for r in respostas) == [200] + [409] * (N - 1)
    assert {r.json()['detail'] for r in respostas if r.status_code == 409} == {
        'Este atendimento já está pago.'
    }
    assert _pagamentos_ativos(engine_dono, ag['id']) == 1
    assert _saidas(engine_dono, ag['id']) == 1
    assert _luvas(engine_dono, clinica) == 8  # 10 - 2 do serviço Limpeza, uma vez só


def test_reabrir_ao_mesmo_tempo_estorna_uma_vez(cliente, clinica, engine_dono, servidor):
    h = clinica.lt.h_admin
    ag = cliente.post(f'{API}/agendamentos', json=clinica.dados(status='confirmado'), headers=h).json()
    url = f'{API}/agendamentos/{ag["id"]}/status'
    assert cliente.post(f'{API}/agendamentos/{ag["id"]}/pagamento', json=PIX, headers=h).status_code == 200

    respostas = rajada(servidor, [('POST', url, {'status': 'confirmado'}, h)] * N)

    assert {r.status_code for r in respostas} == {200}
    assert _estornos(engine_dono, ag['id']) == 1
    assert _luvas(engine_dono, clinica) == 10
    assert _pagamentos_ativos(engine_dono, ag['id']) == 0  # AGE-28


def test_concluir_e_cancelar_ao_mesmo_tempo_ficam_coerentes(cliente, clinica, engine_dono, servidor):
    h = clinica.lt.h_admin
    ag = cliente.post(f'{API}/agendamentos', json=clinica.dados(status='confirmado'), headers=h).json()
    base = f'{API}/agendamentos/{ag["id"]}'
    concluir = ('POST', f'{base}/pagamento', PIX, h)
    cancelar = ('POST', f'{base}/status', {'status': 'cancelado', 'motivo_cancelamento': 'Desistiu'}, h)

    respostas = rajada(servidor, [concluir, cancelar] * (N // 2))

    final = _um(engine_dono, 'SELECT status::text FROM agendamentos WHERE id = :i', i=ag['id'])
    pagamentos = [r.status_code for r in respostas if r.request.url.path.endswith('/pagamento')]
    cancelamentos = [r.status_code for r in respostas if r.request.url.path.endswith('/status')]
    if final == 'concluido':  # um pagamento passou; os outros e todos os cancelamentos foram recusados
        assert (sorted(pagamentos), set(cancelamentos)) == ([200] + [409] * (N // 2 - 1), {409})
        assert (_saidas(engine_dono, ag['id']), _luvas(engine_dono, clinica)) == (1, 8)
        assert _pagamentos_ativos(engine_dono, ag['id']) == 1
    else:  # o cancelamento repetido é ignorado (mesmo status); nenhum pagamento passa
        assert (set(pagamentos), set(cancelamentos)) == ({409}, {200})
        assert (_saidas(engine_dono, ag['id']), _luvas(engine_dono, clinica)) == (0, 10)
        assert _pagamentos_ativos(engine_dono, ag['id']) == 0


def test_atendimentos_com_os_mesmos_materiais_concluidos_ao_mesmo_tempo(
    cliente, clinica, engine_dono, servidor
):
    """A22: as baixas travam os materiais sempre na mesma ordem (sem deadlock nem saldo errado)."""
    h = clinica.lt.h_admin
    gaze = cliente.post(
        f'{API}/materiais', json={'nome': 'Gaze', 'quantidade_inicial': 10}, headers=h
    ).json()['id']
    materiais = {
        'materiais': [{'material_id': gaze, 'quantidade': 1}, {'material_id': clinica.luvas, 'quantidade': 1}]
    }
    invertidos = {'materiais': list(reversed(materiais['materiais']))}
    ids = []
    for i, hora in enumerate(('08:00', '09:00', '10:00', '13:00', '14:00', '15:00')):
        ag = cliente.post(
            f'{API}/agendamentos',
            json=clinica.dados(inicio=f'{SEGUNDA}T{hora}', status='confirmado'),
            headers=h,
        ).json()
        corpo = materiais if i % 2 else invertidos
        assert (
            cliente.put(f'{API}/agendamentos/{ag["id"]}/materiais', json=corpo, headers=h).status_code == 200
        )
        ids.append(ag['id'])

    respostas = rajada(servidor, [('POST', f'{API}/agendamentos/{i}/pagamento', PIX, h) for i in ids])

    assert {r.status_code for r in respostas} == {200}
    assert _luvas(engine_dono, clinica) == 10 - len(ids)
    assert _um(engine_dono, 'SELECT quantidade_atual FROM materiais WHERE id = :i', i=gaze) == 10 - len(ids)


# --- A3: último Administrador ativo ---------------------------------------------------------------


def _reativar(engine, *ids) -> None:
    with sessao(engine) as db:
        db.execute(text('UPDATE funcionarios SET ativo = true WHERE id = ANY(:ids)'), {'ids': list(ids)})


def _admins_ativos(engine, loja_id) -> int:
    return _um(
        engine,
        'SELECT count(*) FROM funcionarios f JOIN perfis p ON p.id = f.perfil_id'
        ' WHERE f.loja_id = :l AND f.ativo AND p.acesso_total AND f.excluido_em IS NULL',
        l=loja_id,
    )


def test_dois_admins_se_desativando_ao_mesmo_tempo(lojas, engine_dono, servidor):
    a, _ = lojas
    admin2 = criar_funcionario(
        engine_dono, a.loja, a.perfis['Administrador'], 'admin2@loja-a.com', nome='Admin2'
    )
    perfil = str(a.perfis['Administrador'].id)
    desativa_2 = {'nome': 'Admin2', 'email': 'admin2@loja-a.com', 'perfil_id': perfil, 'ativo': False}
    desativa_1 = {'nome': 'Admin', 'email': 'admin@loja-a.com', 'perfil_id': perfil, 'ativo': False}
    for _ in range(5):
        _reativar(engine_dono, a.admin.id, admin2.id)
        respostas = rajada(
            servidor,
            [
                ('PUT', f'{API}/funcionarios/{admin2.id}', desativa_2, cabecalho(a.admin)),
                ('PUT', f'{API}/funcionarios/{a.admin.id}', desativa_1, cabecalho(admin2)),
            ],
        )
        assert _admins_ativos(engine_dono, a.loja.id) == 1
        assert sorted(r.status_code for r in respostas) in ([200, 401], [200, 409])


def test_superadmin_e_loja_desativando_admins_ao_mesmo_tempo(lojas, engine_dono, servidor):
    a, _ = lojas
    admin2 = criar_funcionario(
        engine_dono, a.loja, a.perfis['Administrador'], 'admin2@loja-a.com', nome='Admin2'
    )
    h_super = cabecalho_superadmin(criar_superadmin(engine_dono))
    perfil = str(a.perfis['Administrador'].id)
    for _ in range(5):
        _reativar(engine_dono, a.admin.id, admin2.id)
        rajada(
            servidor,
            [
                (
                    'PUT',
                    f'/api/superadmin/lojas/{a.loja.id}/funcionarios/{admin2.id}',
                    {'nome': 'Admin2', 'email': 'admin2@loja-a.com', 'perfil_id': perfil, 'ativo': False},
                    h_super,
                ),
                (
                    'PUT',
                    f'{API}/funcionarios/{a.admin.id}',
                    {'nome': 'Admin', 'email': 'admin@loja-a.com', 'perfil_id': perfil, 'ativo': False},
                    cabecalho(a.admin),
                ),
            ],
        )
        assert _admins_ativos(engine_dono, a.loja.id) == 1


# --- A11: ponto ------------------------------------------------------------------------------------


def _registros(engine, funcionario_id):
    with engine.connect() as conexao:
        return conexao.execute(
            text('SELECT id, saida FROM registros_ponto WHERE funcionario_id = :f AND excluido_em IS NULL'),
            {'f': funcionario_id},
        ).all()


def test_registrar_entrada_e_saida_com_cliques_simultaneos(lojas, engine_dono, servidor):
    a, _ = lojas
    url = f'{API}/ponto/registrar'

    entradas = rajada(servidor, [('POST', url, {'acao': 'entrada'}, a.h_prof)] * N)
    assert sorted(r.status_code for r in entradas) == [200] + [409] * (N - 1)
    assert {r.json()['detail'] for r in entradas if r.status_code == 409} == {
        'A entrada já foi registrada. Para encerrar, registre a saída.'
    }
    registros = _registros(engine_dono, a.prof.id)
    assert len(registros) == 1
    assert registros[0].saida is None

    saidas = rajada(servidor, [('POST', url, {'acao': 'saida'}, a.h_prof)] * N)
    assert sorted(r.status_code for r in saidas) == [200] + [409] * (N - 1)
    assert {r.json()['detail'] for r in saidas if r.status_code == 409} == {
        'Não há entrada em aberto. Registre a entrada primeiro.'
    }
    registros = _registros(engine_dono, a.prof.id)
    assert len(registros) == 1
    assert registros[0].saida is not None


def test_lancamentos_manuais_sobrepostos_ao_mesmo_tempo(lojas, engine_dono, servidor):
    a, _ = lojas
    ontem = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)
    pedidos = [
        (
            'POST',
            f'{API}/ponto',
            {
                'funcionario_id': str(a.prof.id),
                'entrada': (ontem + timedelta(minutes=10 * i)).isoformat(),
                'saida': (ontem + timedelta(hours=2, minutes=10 * i)).isoformat(),
                'justificativa': 'Ponto em papel',
            },
            a.h_admin,
        )
        for i in range(N)
    ]
    respostas = rajada(servidor, pedidos)
    assert sorted(r.status_code for r in respostas) == [201] + [409] * (N - 1)
    assert len(_registros(engine_dono, a.prof.id)) == 1


# --- A4: pedidos pendentes por telefone no site ----------------------------------------------------


def test_pedidos_simultaneos_do_mesmo_telefone_respeitam_o_limite(
    clinica, engine_dono, servidor, monkeypatch
):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), 'site_pendentes_por_telefone', 2)
    horas = ['08:00', '09:00', '10:00', '13:00', '14:00']
    telefones = ['(11) 97777-6666', '11977776666', '11 97777 6666', '(11)97777-6666', '+11 97777-6666']
    pedidos = [
        (
            'POST',
            '/api/site/loja-a/agendamentos',
            {
                'servico_id': clinica.limpeza,
                'funcionario_id': str(clinica.lt.prof.id),
                'inicio': f'{SEGUNDA}T{hora}',
                'nome': 'Ana',
                'sobrenome': 'Souza',
                'telefone': telefone,
            },
            None,
        )
        for hora, telefone in zip(horas, telefones, strict=True)
    ]
    respostas = rajada(servidor, pedidos)
    assert sorted(r.status_code for r in respostas) == [201, 201, 409, 409, 409]
    assert _um(engine_dono, "SELECT count(*) FROM agendamentos WHERE status = 'pendente'") == 2
    # O cliente novo foi cadastrado uma vez só (o telefone fica travado durante o pedido)
    assert _um(engine_dono, "SELECT count(*) FROM clientes WHERE telefone = '(11) 97777-6666'") == 1


def test_servidor_responde(servidor):
    assert httpx.get(f'{servidor}/api/saude').json() == {'status': 'ok'}


# --- LOG-02: excluir serviço x marcar agendamento com ele -----------------------------------------


def test_excluir_servico_e_agendar_com_ele_ao_mesmo_tempo(cliente, clinica, engine_dono, servidor):
    """Nunca sobra agendamento futuro com serviço excluído: ou a exclusão espera e é recusada (409),
    ou o agendamento espera e não acha mais o serviço (422)."""
    c = clinica
    h = c.lt.h_admin
    for rodada, hora in enumerate((8, 9, 10, 11, 13, 14)):  # dentro da jornada (8-12 e 13-18)
        servico = cliente.post(
            f'{API}/servicos',
            json={
                'nome': f'Corrida {rodada}',
                'duracao_minutos': 30,
                'preco': 50,
                'funcionario_ids': [str(c.lt.prof.id)],
            },
            headers=h,
        ).json()['id']
        dados = c.dados(servico_id=servico, inicio=f'{SEGUNDA}T{hora:02d}:00', local_id=c.sala2)

        excluir, agendar = rajada(
            servidor,
            [('DELETE', f'{API}/servicos/{servico}', None, h), ('POST', f'{API}/agendamentos', dados, h)],
        )

        resultado = (excluir.status_code, agendar.status_code)
        assert resultado in {(204, 422), (409, 201)}, (resultado, excluir.text, agendar.text)
        if resultado == (204, 422):
            assert agendar.json()['detail'] == 'Serviço não encontrado.'
        orfaos = _um(
            engine_dono,
            'SELECT count(*) FROM agendamentos a JOIN servicos s ON s.id = a.servico_id'
            ' WHERE s.id = :s AND s.excluido_em IS NOT NULL AND a.excluido_em IS NULL',
            s=servico,
        )
        assert orfaos == 0


# --- LOC-06: vínculos de serviços pela tela de Locais --------------------------------------------


def test_vincular_servicos_ao_mesmo_tempo_no_mesmo_local(clinica, engine_dono, servidor):
    """Duas telas salvando o mesmo local com os mesmos serviços: sem o FOR UPDATE do local, as duas
    tentavam inserir o mesmo vínculo e uma recebia 409 de chave duplicada."""
    c, h = clinica, clinica.lt.h_admin
    corpo = {'nome': 'Sala 2', 'servico_ids': [c.limpeza, c.avaliacao]}

    respostas = rajada(servidor, [('PUT', f'{API}/locais/{c.sala2}', corpo, h)] * N)

    assert {r.status_code for r in respostas} == {200}, [r.text for r in respostas]
    vinculos = _um(
        engine_dono,
        'SELECT count(*) FROM servico_locais WHERE local_id = :l AND excluido_em IS NULL',
        l=c.sala2,
    )
    assert vinculos == 2
