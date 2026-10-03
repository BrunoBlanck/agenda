"""Controle de Tempo: ação explícita no registrar e nenhum período sobreposto (PON-01, LOG-01)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import RegistroPonto
from tests.fabricas import inserir, sessao

URL = '/api/loja/ponto'
MSG_SOBREPOSTO = 'Este funcionário já tem um registro de ponto nesse período.'


def _registro(engine, lt, funcionario, entrada, saida=None):
    return inserir(
        engine, RegistroPonto(loja_id=lt.loja.id, funcionario_id=funcionario.id, entrada=entrada, saida=saida)
    )


def _manual(cliente, lt, funcionario, entrada, saida=None):
    corpo = {'funcionario_id': str(funcionario.id), 'entrada': entrada.isoformat(), 'justificativa': 'Papel'}
    if saida is not None:
        corpo['saida'] = saida.isoformat()
    return cliente.post(URL, json=corpo, headers=lt.h_admin)


def _base():
    return (datetime.now(UTC) - timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0)


def test_registrar_exige_a_acao_e_confere_com_a_situacao(cliente, lojas):
    a, _ = lojas
    url = f'{URL}/registrar'
    assert cliente.post(url, headers=a.h_prof).status_code == 422  # sem corpo
    assert cliente.post(url, json={}, headers=a.h_prof).status_code == 422
    assert cliente.post(url, json={'acao': 'pausa'}, headers=a.h_prof).status_code == 422

    sem_entrada = cliente.post(url, json={'acao': 'saida'}, headers=a.h_prof)
    assert sem_entrada.status_code == 409
    assert sem_entrada.json()['detail'] == 'Não há entrada em aberto. Registre a entrada primeiro.'

    assert cliente.post(url, json={'acao': 'entrada'}, headers=a.h_prof).json()['acao'] == 'entrada'
    de_novo = cliente.post(url, json={'acao': 'entrada'}, headers=a.h_prof)
    assert de_novo.status_code == 409
    assert de_novo.json()['detail'] == 'A entrada já foi registrada. Para encerrar, registre a saída.'

    assert cliente.post(url, json={'acao': 'saida'}, headers=a.h_prof).json()['acao'] == 'saida'
    assert cliente.post(url, json={'acao': 'saida'}, headers=a.h_prof).status_code == 409


def test_lancamento_manual_sobreposto_e_recusado(cliente, lojas):
    a, _ = lojas
    base = _base()
    assert _manual(cliente, a, a.prof, base.replace(hour=8), base.replace(hour=12)).status_code == 201
    for entrada, saida in (
        (base.replace(hour=9), base.replace(hour=11)),  # dentro
        (base.replace(hour=7), base.replace(hour=9)),  # cruza o início
        (base.replace(hour=11), base.replace(hour=13)),  # cruza o fim
        (base.replace(hour=7), base.replace(hour=13)),  # cobre tudo
        (base.replace(hour=10), None),  # em aberto a partir do meio
    ):
        resposta = _manual(cliente, a, a.prof, entrada, saida)
        assert resposta.status_code == 409, (entrada, saida)
        assert resposta.json()['detail'] == MSG_SOBREPOSTO
    # Encostado (12:00 → 13:00) não sobrepõe
    assert _manual(cliente, a, a.prof, base.replace(hour=12), base.replace(hour=13)).status_code == 201
    # Outro funcionário no mesmo horário pode
    assert _manual(cliente, a, a.recepcao, base.replace(hour=9), base.replace(hour=11)).status_code == 201


def test_correcao_sobreposta_e_recusada(cliente, lojas, engine_dono):
    a, _ = lojas
    base = _base()
    manha = _registro(engine_dono, a, a.prof, base.replace(hour=8), base.replace(hour=12))
    tarde = _registro(engine_dono, a, a.prof, base.replace(hour=13), base.replace(hour=17))
    invade = cliente.put(
        f'{URL}/{tarde.id}',
        json={
            'entrada': base.replace(hour=11).isoformat(),
            'saida': base.replace(hour=17).isoformat(),
            'justificativa': 'x',
        },
        headers=a.h_admin,
    )
    assert invade.status_code == 409
    assert invade.json()['detail'] == MSG_SOBREPOSTO
    # Corrigir o próprio registro dentro do seu período não conflita com ele mesmo
    proprio = cliente.put(
        f'{URL}/{manha.id}',
        json={
            'entrada': base.replace(hour=8, minute=30).isoformat(),
            'saida': base.replace(hour=12).isoformat(),
            'justificativa': 'x',
        },
        headers=a.h_admin,
    )
    assert proprio.status_code == 200
    # Reabrir um registro antigo (sem saída) cobriria o seguinte
    reabrir = cliente.put(
        f'{URL}/{manha.id}',
        json={'entrada': base.replace(hour=8).isoformat(), 'justificativa': 'x'},
        headers=a.h_admin,
    )
    assert reabrir.status_code == 409


def test_registrar_entrada_nao_invade_lancamento_que_termina_depois_de_agora(cliente, lojas, engine_dono):
    a, _ = lojas
    agora = datetime.now(UTC)
    _registro(engine_dono, a, a.prof, agora - timedelta(hours=1), agora + timedelta(seconds=40))
    resposta = cliente.post(f'{URL}/registrar', json={'acao': 'entrada'}, headers=a.h_prof)
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == MSG_SOBREPOSTO


def test_banco_recusa_sobreposicao_mesmo_sem_passar_pela_api(lojas, engine_dono):
    a, _ = lojas
    base = _base()
    _registro(engine_dono, a, a.prof, base.replace(hour=8), base.replace(hour=12))
    with pytest.raises(IntegrityError) as erro, sessao(engine_dono) as db:
        db.execute(
            text(
                'INSERT INTO registros_ponto (loja_id, funcionario_id, entrada, saida)'
                ' VALUES (:l, :f, :e, :s)'
            ),
            {'l': a.loja.id, 'f': a.prof.id, 'e': base.replace(hour=10), 's': base.replace(hour=14)},
        )
    assert 'registros_ponto_sem_sobreposicao' in str(erro.value)
    # Registro excluído (logicamente) não conta
    with sessao(engine_dono) as db:
        db.execute(
            text('UPDATE registros_ponto SET excluido_em = now() WHERE funcionario_id = :f'), {'f': a.prof.id}
        )
    _registro(engine_dono, a, a.prof, base.replace(hour=10), base.replace(hour=14))
