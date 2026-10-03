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

    @router.get('/estouro-python')
    def estouro_python(ctx: ContextoLoja = Depends(exigir('clientes'))):
        from datetime import date, timedelta

        return {'data': date.max + timedelta(days=1)}

    @router.get('/estouro-numero')
    def estouro_numero(ctx: ContextoLoja = Depends(exigir('clientes'))):
        ctx.db.execute(text('SELECT 123456789012::numeric(10,2)'))

    @router.get('/estouro-data')
    def estouro_data(ctx: ContextoLoja = Depends(exigir('clientes'))):
        ctx.db.execute(text("SELECT '294276-12-31'::timestamp + interval '1 year'"))

    @router.get('/disputa/{codigo}')
    def disputa(codigo: str, ctx: ContextoLoja = Depends(exigir('clientes'))):
        if codigo not in ('40P01', '40001'):
            return {}
        ctx.db.execute(text(f"DO $$ BEGIN RAISE EXCEPTION 'disputa' USING ERRCODE = '{codigo}'; END $$"))

    app = criar_app()
    app.include_router(router)
    with TestClient(app) as c:
        yield c, login_loja(c, 'loja-a', 'admin@a.com')


def test_unicidade_vira_409_sem_mostrar_o_cpf(cliente_erros):
    cliente, cabecalho = cliente_erros
    resposta = cliente.post('/api/loja/teste/cliente-duplicado', headers=cabecalho)
    assert resposta.status_code == 409
    assert resposta.json() == {'detail': 'Já existe um cliente com este CPF.'}
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
    assert resposta.json() == {'detail': 'Já existe um cliente com este CPF.'}
    with engine_dono.connect() as conexao:
        assert conexao.execute(text('SELECT count(*) FROM clientes')).scalar() == 0


def test_estouro_de_valor_ou_data_vira_422_e_nao_500(cliente_erros):
    """Rede de segurança (A8): a validação de entrada já barra, mas um estouro não vira 500."""
    cliente, cabecalho = cliente_erros
    esperado = {
        '/api/loja/teste/estouro-python': 'Valor fora do limite permitido.',
        '/api/loja/teste/estouro-numero': 'Valor fora do limite permitido.',
        '/api/loja/teste/estouro-data': 'Data fora do limite permitido.',
    }
    for url, mensagem in esperado.items():
        resposta = cliente.get(url, headers=cabecalho)
        assert resposta.status_code == 422, url
        assert resposta.json() == {'detail': mensagem}


def test_deadlock_e_falha_de_serializacao_viram_409(cliente_erros):
    """A22: transações disputando as mesmas linhas respondem 409 pedindo para tentar de novo."""
    cliente, cabecalho = cliente_erros
    for codigo in ('40P01', '40001'):
        resposta = cliente.get(f'/api/loja/teste/disputa/{codigo}', headers=cabecalho)
        assert resposta.status_code == 409
        assert resposta.json() == {
            'detail': 'Outra alteração foi feita ao mesmo tempo e esta não foi salva. Tente novamente.'
        }
