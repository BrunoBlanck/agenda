"""Triggers de controle: atualizado_por, exclusão lógica e auditoria (estrutura.md, 1.9)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.models import Auditoria, Cliente, Plano, Servico, ServicoFuncionario
from app.models.enums import OperacaoAuditoria, OrigemAuditoria
from tests.fabricas import criar_funcionario, criar_loja, criar_superadmin, sessao


@pytest.fixture
def loja(engine_dono):
    loja, perfis = criar_loja(engine_dono, 'loja-a')
    admin = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'admin@a.com')
    recepcao = criar_funcionario(engine_dono, loja, perfis['Recepção'], 'recepcao@a.com')
    return loja, admin, recepcao


def _auditoria(db, tabela, registro_id):
    return db.scalars(
        select(Auditoria)
        .where(Auditoria.tabela == tabela, Auditoria.registro_id == str(registro_id))
        .order_by(Auditoria.id)
    ).all()


def _criar_cliente(engine, loja, funcionario, **dados):
    with sessao(engine, 'painel', funcionario_id=funcionario.id, loja_id=loja.id) as db:
        cliente = Cliente(
            loja_id=loja.id, nome='Maria', sobrenome='Oliveira', telefone='(11) 90000-0000', **dados
        )
        db.add(cliente)
    return cliente


def test_insert_e_update_preenchem_atualizado_por_com_o_funcionario_do_contexto(engine_app, loja):
    loja, admin, recepcao = loja
    cliente = _criar_cliente(engine_app, loja, admin)
    assert cliente.atualizado_por == admin.id
    criado_em = cliente.criado_em

    with sessao(engine_app, 'painel', funcionario_id=recepcao.id, loja_id=loja.id) as db:
        registro = db.get(Cliente, cliente.id)
        registro.nome = 'Mariana'
        db.flush()
        assert registro.atualizado_por == recepcao.id
        assert registro.criado_em == criado_em
        assert registro.atualizado_em >= criado_em


def test_python_nao_consegue_forjar_colunas_de_controle(engine_app, loja):
    loja, admin, recepcao = loja
    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        db.execute(
            text(
                'INSERT INTO clientes (loja_id, nome, sobrenome, telefone, atualizado_por, criado_em, excluido_em)'
                " VALUES (:l, 'Ana', 'Lima', '1', :r, '2000-01-01', now())"
            ),
            {'l': loja.id, 'r': recepcao.id},
        )
        linha = db.execute(
            text("SELECT atualizado_por, criado_em, excluido_em FROM clientes WHERE nome = 'Ana'")
        ).one()
    assert linha.atualizado_por == admin.id
    assert linha.criado_em.year > 2000
    assert linha.excluido_em is None


def test_delete_vira_exclusao_logica(engine_app, loja):
    loja, admin, recepcao = loja
    cliente = _criar_cliente(engine_app, loja, admin)

    with sessao(engine_app, 'painel', funcionario_id=recepcao.id, loja_id=loja.id) as db:
        resultado = db.execute(text('DELETE FROM clientes WHERE id = :id'), {'id': cliente.id})
        assert resultado.rowcount == 0  # o DELETE físico foi cancelado

    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        linha = db.execute(
            text('SELECT excluido_em, excluido_por FROM clientes WHERE id = :id'), {'id': cliente.id}
        ).one()
        assert linha.excluido_em is not None
        assert linha.excluido_por == recepcao.id
        # O ORM esconde a linha excluída, a menos que peça explicitamente
        assert db.scalar(select(Cliente).where(Cliente.id == cliente.id)) is None
        assert (
            db.scalar(
                select(Cliente).where(Cliente.id == cliente.id).execution_options(incluir_excluidos=True)
            )
            is not None
        )


def test_delete_em_tabela_de_ligacao_usa_a_chave_composta(engine_app, loja):
    loja, admin, _ = loja
    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        s1 = Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=60)
        s2 = Servico(loja_id=loja.id, nome='Avaliação', duracao_minutos=30)
        db.add_all([s1, s2])
        db.flush()
        db.add_all(
            [
                ServicoFuncionario(loja_id=loja.id, servico_id=s1.id, funcionario_id=admin.id),
                ServicoFuncionario(loja_id=loja.id, servico_id=s2.id, funcionario_id=admin.id),
            ]
        )
        db.flush()
        db.execute(
            text('DELETE FROM servico_funcionarios WHERE servico_id = :s AND funcionario_id = :f'),
            {'s': s1.id, 'f': admin.id},
        )
        excluidos = (
            db.execute(text('SELECT servico_id FROM servico_funcionarios WHERE excluido_em IS NOT NULL'))
            .scalars()
            .all()
        )
    assert excluidos == [s1.id]


def test_auditoria_registra_inserir_alterar_excluir_e_restaurar(engine_app, loja):
    loja, admin, recepcao = loja
    cliente = _criar_cliente(engine_app, loja, admin, cpf='123.456.789-00')

    with sessao(engine_app, 'painel', funcionario_id=recepcao.id, loja_id=loja.id, ip='10.0.0.7') as db:
        db.get(Cliente, cliente.id).telefone = '(11) 91111-1111'
    with sessao(engine_app, 'painel', funcionario_id=recepcao.id, loja_id=loja.id) as db:
        db.execute(text('DELETE FROM clientes WHERE id = :id'), {'id': cliente.id})
    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        db.execute(text('UPDATE clientes SET excluido_em = NULL WHERE id = :id'), {'id': cliente.id})

    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        linhas = _auditoria(db, 'clientes', cliente.id)

    assert [a.operacao for a in linhas] == [
        OperacaoAuditoria.inserir,
        OperacaoAuditoria.alterar,
        OperacaoAuditoria.excluir,
        OperacaoAuditoria.restaurar,
    ]
    inserir, alterar, excluir, restaurar = linhas
    assert all(a.loja_id == loja.id and a.origem == OrigemAuditoria.painel for a in linhas)
    assert inserir.antes is None
    assert inserir.depois['nome'] == 'Maria'
    assert inserir.funcionario_id == admin.id
    assert alterar.funcionario_id == recepcao.id
    assert alterar.campos_alterados == ['telefone']
    assert alterar.antes['telefone'] == '(11) 90000-0000'
    assert alterar.depois['telefone'] == '(11) 91111-1111'
    assert str(alterar.ip) == '10.0.0.7'
    assert excluir.depois['excluido_em'] is not None
    assert excluir.depois['excluido_por'] == str(recepcao.id)
    assert restaurar.depois['excluido_em'] is None
    assert restaurar.depois['excluido_por'] is None
    assert restaurar.funcionario_id == admin.id


def test_update_sem_mudanca_nao_gera_auditoria(engine_app, loja):
    loja, admin, _ = loja
    cliente = _criar_cliente(engine_app, loja, admin)
    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        db.execute(text('UPDATE clientes SET nome = nome WHERE id = :id'), {'id': cliente.id})
        assert len(_auditoria(db, 'clientes', cliente.id)) == 1


def test_religar_vinculo_restaura_a_linha_existente(engine_app, loja):
    loja, admin, _ = loja
    contexto = {'funcionario_id': admin.id, 'loja_id': loja.id}
    with sessao(engine_app, 'painel', **contexto) as db:
        servico = Servico(loja_id=loja.id, nome='Limpeza', duracao_minutos=60)
        db.add(servico)
        db.flush()
        db.add(ServicoFuncionario(loja_id=loja.id, servico_id=servico.id, funcionario_id=admin.id))
    chave = {'s': servico.id, 'f': admin.id}
    with sessao(engine_app, 'painel', **contexto) as db:
        db.execute(
            text('DELETE FROM servico_funcionarios WHERE servico_id = :s AND funcionario_id = :f'), chave
        )
    with sessao(engine_app, 'painel', **contexto) as db:
        # Religar: o mesmo INSERT, desfazendo a exclusão quando a linha já existe
        db.execute(
            text(
                'INSERT INTO servico_funcionarios (loja_id, servico_id, funcionario_id) VALUES (:l, :s, :f)'
                ' ON CONFLICT (servico_id, funcionario_id) DO UPDATE SET excluido_em = NULL'
            ),
            {**chave, 'l': loja.id},
        )
        total = db.execute(text('SELECT count(*) FROM servico_funcionarios')).scalar()
        ativos = db.execute(
            text('SELECT count(*) FROM servico_funcionarios WHERE excluido_em IS NULL')
        ).scalar()
        operacoes = [a.operacao for a in _auditoria(db, 'servico_funcionarios', f'{servico.id}:{admin.id}')]
    assert (total, ativos) == (1, 1)
    assert operacoes == [OperacaoAuditoria.inserir, OperacaoAuditoria.excluir, OperacaoAuditoria.restaurar]


def test_auditoria_nao_guarda_senha_hash(engine_app, engine_dono, loja):
    loja, admin, _ = loja
    with sessao(engine_app, 'painel', funcionario_id=admin.id, loja_id=loja.id) as db:
        db.execute(text("UPDATE funcionarios SET senha_hash = 'outro-hash' WHERE id = :id"), {'id': admin.id})
        linhas = _auditoria(db, 'funcionarios', admin.id)
    assert all('senha_hash' not in (a.depois or {}) and 'senha_hash' not in (a.antes or {}) for a in linhas)
    assert linhas[-1].campos_alterados == ['senha_hash']


def test_auditoria_e_somente_insercao(engine_app, engine_dono, loja):
    loja, admin, _ = loja
    contexto = {'funcionario_id': admin.id, 'loja_id': loja.id}
    # Usuário da aplicação: sem permissão de UPDATE/DELETE (REVOKE)
    for comando in ("UPDATE auditoria SET tabela = 'x'", 'DELETE FROM auditoria'):
        with (
            pytest.raises(ProgrammingError, match='permission denied'),
            sessao(engine_app, 'painel', **contexto) as db,
        ):
            db.execute(text(comando))
    # Nem o dono do schema consegue (trigger)
    for comando in ("UPDATE auditoria SET tabela = 'x'", 'DELETE FROM auditoria'):
        with pytest.raises(DBAPIError, match='não pode ser alterada'), sessao(engine_dono) as db:
            db.execute(text(comando))


def test_tabela_da_plataforma_registra_superadmin(engine_app, engine_dono):
    superadmin = criar_superadmin(engine_dono)
    with sessao(engine_app, 'superadmin', superadmin_id=superadmin.id) as db:
        plano = Plano(nome='Básico', preco_mensal=89.9)
        db.add(plano)
        db.flush()
        db.execute(text('DELETE FROM planos WHERE id = :id'), {'id': plano.id})
        excluido_por = db.execute(
            text('SELECT excluido_por FROM planos WHERE id = :id'), {'id': plano.id}
        ).scalar()
        linhas = _auditoria(db, 'planos', plano.id)
    assert excluido_por == superadmin.id
    assert [a.operacao for a in linhas] == [OperacaoAuditoria.inserir, OperacaoAuditoria.excluir]
    assert all(a.superadmin_id == superadmin.id and a.loja_id is None for a in linhas)
    assert linhas[0].origem == OrigemAuditoria.superadmin


def test_superadmin_alterando_tabela_da_loja_deixa_atualizado_por_nulo(engine_app, engine_dono, loja):
    loja, admin, _ = loja
    superadmin = criar_superadmin(engine_dono)
    cliente = _criar_cliente(engine_app, loja, admin)
    with sessao(engine_app, 'superadmin', superadmin_id=superadmin.id) as db:
        registro = db.get(Cliente, cliente.id)
        registro.nome = 'Outro'
        db.flush()
        assert registro.atualizado_por is None
        ultima = _auditoria(db, 'clientes', cliente.id)[-1]
    assert ultima.superadmin_id == superadmin.id
    assert ultima.funcionario_id is None
