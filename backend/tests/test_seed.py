"""Seed de desenvolvimento: reproduz o mock e pode rodar várias vezes."""

from sqlalchemy import text

from scripts import seed
from tests.fabricas import login_loja, login_superadmin


def _contagens(engine) -> dict[str, int]:
    with engine.connect() as conexao:
        tabelas = (
            conexao.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        return {t: conexao.execute(text(f'SELECT count(*) FROM {t}')).scalar() for t in tabelas}


def test_seed_e_idempotente(engine_app, engine_dono):
    seed.executar(engine_app)
    primeira = _contagens(engine_dono)
    seed.executar(engine_app)
    assert _contagens(engine_dono) == primeira
    assert primeira['lojas'] == 5
    assert primeira['funcionarios'] == 11
    assert primeira['agendamentos'] == 10
    assert primeira['clientes'] == 3
    assert primeira['superadmin_usuarios'] == 2
    with engine_dono.connect() as conexao:
        estoque = dict(conexao.execute(text('SELECT nome, quantidade_atual FROM materiais')).all())
    assert estoque['Gaze estéril'] == 3


def test_senhas_de_desenvolvimento_funcionam(engine_app, cliente):
    seed.executar(engine_app)
    login_loja(cliente, 'clinica-sorriso', 'ana@clinica.com', seed.SENHA_FUNCIONARIO)
    login_loja(cliente, 'escola-harmonia', 'paula@harmonia.com', seed.SENHA_FUNCIONARIO)
    login_superadmin(cliente, 'rafael@agendaplataforma.com', seed.SENHA_SUPERADMIN)
    eu = cliente.get(
        '/api/loja/eu', headers=login_loja(cliente, 'barbearia-navalha', 'diego@navalha.com', 'senha123')
    )
    assert eu.json()['loja']['rotulo_local_plural'] == 'Cadeiras'
    assert eu.json()['modulos']['materiais'] is False
