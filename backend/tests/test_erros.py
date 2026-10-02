"""Erros do banco viram respostas em português, sem expor valores enviados."""

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth.dependencias import ContextoLoja, exigir
from app.main import criar_app
from app.models import Cliente
from tests.fabricas import criar_funcionario, criar_loja, login_loja


@pytest.fixture
def cliente_erros(engine_dono):
    loja, perfis = criar_loja(engine_dono, 'loja-a')
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@a.com')
    router = APIRouter(prefix='/api/loja/teste')

    @router.post('/cliente-duplicado')
    def duplicado(ctx: ContextoLoja = Depends(exigir('clientes', 'escrita'))):
        for _ in range(2):
            ctx.db.execute(
                text(
                    "INSERT INTO clientes (loja_id, nome, sobrenome, telefone, cpf) VALUES (:l, 'A', 'B', '1', '123.456.789-00')"
                ),
                {'l': ctx.loja_id},
            )
        return {'ok': True}

    @router.post('/estoque-direto')
    def estoque(ctx: ContextoLoja = Depends(exigir('materiais', 'escrita'))):
        ctx.db.execute(
            text(
                "INSERT INTO materiais (loja_id, nome, unidade, quantidade_atual) VALUES (:l, 'X', 'un', 5)"
            ),
            {'l': ctx.loja_id},
        )
        return {'ok': True}

    @router.post('/duplicado-no-commit')
    def duplicado_no_commit(ctx: ContextoLoja = Depends(exigir('clientes', 'escrita'))):
        # Sem flush: o erro só aparece no commit, ao fim da dependência da sessão
        for _ in range(2):
            ctx.db.add(
                Cliente(loja_id=ctx.loja_id, nome='A', sobrenome='B', telefone='1', cpf='111.111.111-11')
            )
        return {'ok': True}

    app = criar_app()
    app.include_router(router)
    with TestClient(app) as c:
        yield c, login_loja(c, 'loja-a', 'admin@a.com')


def test_unicidade_vira_409_sem_mostrar_o_cpf(cliente_erros):
    cliente, cabecalho = cliente_erros
    resposta = cliente.post('/api/loja/teste/cliente-duplicado', headers=cabecalho)
    assert resposta.status_code == 409
    assert resposta.json() == {'detail': 'Já existe um cadastro com esses dados.'}
    assert '123.456.789-00' not in resposta.text


def test_mensagem_das_regras_do_banco_chega_ao_usuario(cliente_erros):
    cliente, cabecalho = cliente_erros
    resposta = cliente.post('/api/loja/teste/estoque-direto', headers=cabecalho)
    assert resposta.status_code == 422
    assert resposta.json() == {'detail': 'O estoque inicial deve ser lançado como uma entrada de estoque.'}


def test_erro_no_commit_tambem_vira_resposta_em_portugues(cliente_erros, engine_dono):
    cliente, cabecalho = cliente_erros
    resposta = cliente.post('/api/loja/teste/duplicado-no-commit', headers=cabecalho)
    assert resposta.status_code == 409
    assert resposta.json() == {'detail': 'Já existe um cadastro com esses dados.'}
    with engine_dono.connect() as conexao:
        assert conexao.execute(text('SELECT count(*) FROM clientes')).scalar() == 0
