"""Regras garantidas pelo banco: unicidade parcial, FKs compostas, RLS e restrições de negócio."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import (
    Agendamento,
    Cliente,
    Funcionalidade,
    Local,
    LojaFuncionalidade,
    Material,
    MovimentacaoEstoque,
    Servico,
)
from app.models.enums import StatusAgendamento, TipoMovimentacao
from tests.fabricas import criar_funcionario, criar_loja, sessao


@pytest.fixture
def lojas(engine_dono):
    loja_a, perfis_a = criar_loja(engine_dono, 'loja-a')
    loja_b, perfis_b = criar_loja(engine_dono, 'loja-b')
    admin_a = criar_funcionario(engine_dono, loja_a, perfis_a['Administrador'], 'admin@a.com')
    admin_b = criar_funcionario(engine_dono, loja_b, perfis_b['Administrador'], 'admin@b.com')
    return (loja_a, admin_a), (loja_b, admin_b)


def _ctx(loja, funcionario):
    return {'funcionario_id': funcionario.id, 'loja_id': loja.id}


def _cliente(db, loja, nome='Maria'):
    cliente = Cliente(loja_id=loja.id, nome=nome, sobrenome='Silva', telefone='(11) 90000-0000')
    db.add(cliente)
    db.flush()
    return cliente


# --- Índices únicos parciais --------------------------------------------------------------------


def test_nome_repetido_na_mesma_loja_e_recusado(engine_app, lojas):
    (loja, admin), _ = lojas
    with (
        pytest.raises(IntegrityError, match='servicos_nome_uk'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        db.add(Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=60))
        db.flush()
        db.add(Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=30))
        db.flush()


def test_recadastro_permitido_depois_da_exclusao(engine_app, lojas):
    (loja, admin), _ = lojas
    with sessao(engine_app, 'painel', **_ctx(loja, admin)) as db:
        servico = Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=60)
        db.add(servico)
        db.flush()
        db.execute(text('DELETE FROM servicos WHERE id = :id'), {'id': servico.id})
        db.add(Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=45))
        db.flush()
        total = db.scalar(
            select(func.count())
            .select_from(Servico)
            .where(Servico.nome == 'Limpeza')
            .execution_options(incluir_excluidos=True)
        )
    assert total == 2


def test_mesmo_nome_em_lojas_diferentes_e_permitido(engine_dono, lojas):
    (loja_a, _), (loja_b, _) = lojas
    with sessao(engine_dono) as db:
        db.add(Servico(loja_id=loja_a.id, nome='Limpeza', duracao_minutos=60))
        db.add(Servico(loja_id=loja_b.id, nome='Limpeza', duracao_minutos=60))


def test_email_do_funcionario_e_unico_por_loja_sem_diferenciar_maiusculas(engine_dono, lojas):
    (loja, _), _ = lojas
    with sessao(engine_dono) as db:
        perfil_id = db.execute(
            text('SELECT perfil_id FROM funcionarios WHERE email = :e'), {'e': 'admin@a.com'}
        ).scalar()
    with pytest.raises(IntegrityError, match='funcionarios_email_uk'), sessao(engine_dono) as db:
        db.execute(
            text(
                "INSERT INTO funcionarios (loja_id, perfil_id, nome, email, senha_hash) VALUES (:l, :p, 'X', 'ADMIN@a.com', 'h')"
            ),
            {'l': loja.id, 'p': perfil_id},
        )


# --- FKs compostas: nada aponta para outra loja -------------------------------------------------


def test_agendamento_nao_aponta_para_cliente_de_outra_loja(engine_dono, lojas):
    (loja_a, admin_a), (loja_b, _) = lojas
    with sessao(engine_dono) as db:
        cliente_b = _cliente(db, loja_b)
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    with pytest.raises(IntegrityError, match='agendamentos_cliente_fk'), sessao(engine_dono) as db:
        db.add(
            Agendamento(
                loja_id=loja_a.id,
                cliente_id=cliente_b.id,
                funcionario_id=admin_a.id,
                inicio=inicio,
                fim=inicio + timedelta(hours=1),
            )
        )
        db.flush()


def test_funcionario_nao_usa_perfil_de_outra_loja(engine_dono, lojas):
    (loja_a, _), (_, admin_b) = lojas
    with pytest.raises(IntegrityError, match='funcionarios_perfil_fk'), sessao(engine_dono) as db:
        db.execute(
            text(
                "INSERT INTO funcionarios (loja_id, perfil_id, nome, email, senha_hash) VALUES (:l, :p, 'X', 'x@a.com', 'h')"
            ),
            {'l': loja_a.id, 'p': admin_b.perfil_id},
        )


def test_atualizado_por_precisa_ser_funcionario_da_mesma_loja(engine_dono, lojas):
    (loja_a, _), (_, admin_b) = lojas
    # Funcionário da loja B "agindo" sobre dado da loja A: a FK composta recusa
    with (
        pytest.raises(IntegrityError, match='atualizado_por_fk'),
        sessao(engine_dono, 'painel', funcionario_id=admin_b.id) as db,
    ):
        _cliente(db, loja_a)


# --- RLS: segunda camada de isolamento ----------------------------------------------------------


def test_rls_so_mostra_dados_da_loja_do_contexto(engine_dono, engine_app, lojas):
    (loja_a, admin_a), (loja_b, _) = lojas
    with sessao(engine_dono) as db:
        _cliente(db, loja_a, 'Cliente A')
        _cliente(db, loja_b, 'Cliente B')

    with sessao(engine_app, 'painel', **_ctx(loja_a, admin_a)) as db:
        # Mesmo sem filtrar por loja_id, só vem a loja A
        assert db.scalars(select(Cliente.nome)).all() == ['Cliente A']
    with sessao(engine_app, 'painel') as db:
        # Sem loja no contexto: nada
        assert db.scalars(select(Cliente.nome)).all() == []


def test_rls_impede_gravar_em_outra_loja(engine_app, lojas):
    (loja_a, admin_a), (loja_b, _) = lojas
    with (
        pytest.raises(DBAPIError, match='row-level security'),
        sessao(engine_app, 'painel', **_ctx(loja_a, admin_a)) as db,
    ):
        _cliente(db, loja_b)


def test_rls_impede_alterar_dados_de_outra_loja(engine_dono, engine_app, lojas):
    (loja_a, admin_a), (loja_b, _) = lojas
    with sessao(engine_dono) as db:
        cliente_b = _cliente(db, loja_b)
    with sessao(engine_app, 'painel', **_ctx(loja_a, admin_a)) as db:
        alterados = db.execute(
            text("UPDATE clientes SET nome = 'invadido' WHERE id = :id"), {'id': cliente_b.id}
        )
        assert alterados.rowcount == 0


def test_usuario_da_aplicacao_nao_e_dono_nem_ignora_rls(engine_app):
    with engine_app.connect() as conexao:
        papel = conexao.execute(
            text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user')
        ).one()
        dono = conexao.execute(
            text("SELECT tableowner = current_user FROM pg_tables WHERE tablename = 'clientes'")
        ).scalar()
    assert tuple(papel) == (False, False)
    assert dono is False


# --- Regras de negócio no banco -----------------------------------------------------------------


def _agendamento(loja, cliente, funcionario, inicio, minutos=60, **extra):
    """funcionario: objeto Funcionario ou id."""
    return Agendamento(
        loja_id=loja.id,
        cliente_id=cliente.id,
        funcionario_id=getattr(funcionario, 'id', funcionario),
        inicio=inicio,
        fim=inicio + timedelta(minutes=minutos),
        **extra,
    )


def test_profissional_nao_tem_dois_agendamentos_sobrepostos(engine_app, lojas):
    (loja, admin), _ = lojas
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    with (
        pytest.raises(IntegrityError, match='agendamentos_sem_conflito'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        cliente = _cliente(db, loja)
        db.add(_agendamento(loja, cliente, admin, inicio))
        db.flush()
        db.add(_agendamento(loja, cliente, admin, inicio + timedelta(minutes=30)))
        db.flush()


def test_agendamento_cancelado_ou_excluido_libera_o_horario(engine_app, lojas):
    (loja, admin), _ = lojas
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    with sessao(engine_app, 'painel', **_ctx(loja, admin)) as db:
        cliente = _cliente(db, loja)
        cancelado = _agendamento(
            loja, cliente, admin, inicio, status=StatusAgendamento.cancelado, motivo_cancelamento='Desistiu'
        )
        excluido = _agendamento(loja, cliente, admin, inicio)
        db.add(cancelado)
        db.flush()
        db.add(excluido)
        db.flush()
        db.execute(text('DELETE FROM agendamentos WHERE id = :id'), {'id': excluido.id})
        db.add(_agendamento(loja, cliente, admin, inicio))
        db.flush()


def test_local_nao_recebe_dois_agendamentos_ao_mesmo_tempo(engine_app, engine_dono, lojas):
    (loja, admin), _ = lojas
    perfil_id = admin.perfil_id
    with sessao(engine_dono) as db:
        outro_id = db.execute(
            text(
                "INSERT INTO funcionarios (loja_id, perfil_id, nome, email, senha_hash) VALUES (:l, :p, 'Outro', 'o@a.com', 'h') RETURNING id"
            ),
            {'l': loja.id, 'p': perfil_id},
        ).scalar()
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    with (
        pytest.raises(IntegrityError, match='agendamentos_local_sem_conflito'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        cliente = _cliente(db, loja)
        sala = Local(loja_id=loja.id, nome='Sala 101')
        db.add(sala)
        db.flush()
        db.add(_agendamento(loja, cliente, admin, inicio, local_id=sala.id))
        db.flush()
        db.add(_agendamento(loja, cliente, outro_id, inicio, local_id=sala.id))
        db.flush()


def test_cancelamento_exige_motivo(engine_app, lojas):
    (loja, admin), _ = lojas
    inicio = datetime(2030, 1, 7, 12, tzinfo=UTC)
    with (
        pytest.raises(IntegrityError, match='motivo_cancelamento'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        cliente = _cliente(db, loja)
        db.add(_agendamento(loja, cliente, admin, inicio, status=StatusAgendamento.cancelado))
        db.flush()


def test_estoque_so_muda_por_movimentacao(engine_app, lojas):
    (loja, admin), _ = lojas
    with sessao(engine_app, 'painel', **_ctx(loja, admin)) as db:
        material = Material(loja_id=loja.id, nome='Luvas', unidade='cx')
        db.add(material)
        db.flush()
        db.add(
            MovimentacaoEstoque(
                loja_id=loja.id, material_id=material.id, tipo=TipoMovimentacao.entrada, quantidade=10
            )
        )
        db.add(
            MovimentacaoEstoque(
                loja_id=loja.id,
                material_id=material.id,
                tipo=TipoMovimentacao.perda,
                quantidade=-3,
                motivo='Vencido',
            )
        )
        db.flush()
        quantidade = db.execute(
            text('SELECT quantidade_atual FROM materiais WHERE id = :id'), {'id': material.id}
        ).scalar()
        assert quantidade == 7
        movimentacao = db.scalar(select(MovimentacaoEstoque.funcionario_id).limit(1))
        assert movimentacao == admin.id

    with (
        pytest.raises(DBAPIError, match='só muda por uma movimentação'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        db.execute(text('UPDATE materiais SET quantidade_atual = 100 WHERE id = :id'), {'id': material.id})

    with (
        pytest.raises(DBAPIError, match='não podem ser excluídas'),
        sessao(engine_app, 'painel', **_ctx(loja, admin)) as db,
    ):
        db.execute(text('DELETE FROM movimentacoes_estoque'))


def test_loja_funcionalidades_aceita_so_modulo_opcional(engine_dono, lojas):
    (loja, _), _ = lojas
    with pytest.raises(DBAPIError, match='Só módulos opcionais'), sessao(engine_dono) as db:
        agenda = db.scalar(select(Funcionalidade).where(Funcionalidade.codigo == 'agenda'))
        db.add(LojaFuncionalidade(loja_id=loja.id, funcionalidade_id=agenda.id, habilitado=False))
        db.flush()
