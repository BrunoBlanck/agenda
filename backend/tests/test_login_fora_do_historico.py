"""Migração 0004: o login (último acesso e novo hash da mesma senha) não entra na auditoria nem muda a
"última alteração"; a troca de senha de verdade continua auditada."""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import select, text

from app.models import Auditoria, Funcionario, SuperadminUsuario
from tests.fabricas import SENHA, criar_superadmin, login_loja, login_superadmin, sessao

# Hash com parâmetros mais fracos que os atuais: o login pede um novo hash (verify_and_update)
HASH_ANTIGO = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1),)).hash(SENHA)


def _linha(engine, tabela: str, id_):
    with engine.connect() as conexao:
        return conexao.execute(
            text(f'SELECT senha_hash, ultimo_login_em, atualizado_em FROM {tabela} WHERE id = :id'),
            {'id': id_},
        ).one()


def _ids(registros: list[Auditoria]) -> list[int]:
    return [r.id for r in registros]


def _auditoria(engine, tabela: str, id_) -> list[Auditoria]:
    with sessao(engine) as db:
        return list(
            db.scalars(
                select(Auditoria)
                .where(Auditoria.tabela == tabela, Auditoria.registro_id == str(id_))
                .order_by(Auditoria.id)
            )
        )


def test_login_do_funcionario_com_novo_hash_fica_fora_do_historico(cliente, lojas, engine_dono):
    a, _ = lojas
    with sessao(engine_dono) as db:
        db.get(Funcionario, a.admin.id).senha_hash = HASH_ANTIGO
    antes = _linha(engine_dono, 'funcionarios', a.admin.id)
    auditoria_antes = _auditoria(engine_dono, 'funcionarios', a.admin.id)

    login_loja(cliente, 'loja-a', a.admin.email)

    depois = _linha(engine_dono, 'funcionarios', a.admin.id)
    assert depois.senha_hash != HASH_ANTIGO  # o hash foi atualizado...
    assert depois.ultimo_login_em is not None
    assert depois.atualizado_em == antes.atualizado_em  # ...sem virar "última alteração"
    assert _ids(_auditoria(engine_dono, 'funcionarios', a.admin.id)) == _ids(auditoria_antes)
    ficha = cliente.get(f'/api/loja/funcionarios/{a.admin.id}', headers=a.h_admin).json()
    assert ficha['ultimo_login_em'] is not None
    # O novo hash vale para os próximos logins
    login_loja(cliente, 'loja-a', a.admin.email)


def test_login_do_superadmin_fica_fora_do_historico(cliente, engine_dono):
    admin = criar_superadmin(engine_dono)
    with sessao(engine_dono) as db:
        db.get(SuperadminUsuario, admin.id).senha_hash = HASH_ANTIGO
    antes = _linha(engine_dono, 'superadmin_usuarios', admin.id)
    auditoria_antes = _auditoria(engine_dono, 'superadmin_usuarios', admin.id)

    login_superadmin(cliente, admin.email)

    depois = _linha(engine_dono, 'superadmin_usuarios', admin.id)
    assert depois.senha_hash != HASH_ANTIGO
    assert depois.ultimo_login_em is not None
    assert depois.atualizado_em == antes.atualizado_em
    assert _ids(_auditoria(engine_dono, 'superadmin_usuarios', admin.id)) == _ids(auditoria_antes)


def test_troca_de_senha_de_verdade_continua_auditada(cliente, lojas, engine_dono):
    a, _ = lojas
    antes = _linha(engine_dono, 'funcionarios', a.prof.id)
    ficha = cliente.get(f'/api/loja/funcionarios/{a.prof.id}', headers=a.h_admin).json()
    corpo = {
        'nome': ficha['nome'],
        'email': ficha['email'],
        'perfil_id': ficha['perfil_id'],
        'senha': 'outra-senha-123',
    }
    resposta = cliente.put(f'/api/loja/funcionarios/{a.prof.id}', json=corpo, headers=a.h_admin)
    assert resposta.status_code == 200, resposta.json()
    assert resposta.json()['atualizado_por'] == str(a.admin.id)

    depois = _linha(engine_dono, 'funcionarios', a.prof.id)
    assert depois.atualizado_em > antes.atualizado_em
    ultima = _auditoria(engine_dono, 'funcionarios', a.prof.id)[-1]
    assert (ultima.operacao, ultima.campos_alterados) == ('alterar', ['senha_hash'])
    assert ultima.funcionario_id == a.admin.id
    assert 'senha_hash' not in (ultima.depois or {})


def test_marca_de_login_nao_esconde_outras_alteracoes(engine_app, engine_dono, lojas):
    """Com app.login ligado, mudar qualquer outra coluna junto é alteração normal (auditada)."""
    a, _ = lojas
    contexto = {'funcionario_id': a.admin.id, 'loja_id': a.loja.id, 'login': True}
    with sessao(engine_app, 'painel', **contexto) as db:
        antes = db.execute(text('SELECT atualizado_em FROM funcionarios WHERE id = :id'), {'id': a.admin.id})
        antes = antes.scalar()
        db.execute(
            text("UPDATE funcionarios SET ultimo_login_em = now(), nome = 'Outro nome' WHERE id = :id"),
            {'id': a.admin.id},
        )
    with sessao(engine_app, 'painel', **contexto) as db:
        depois = db.execute(
            text('SELECT atualizado_em, atualizado_por FROM funcionarios WHERE id = :id'), {'id': a.admin.id}
        ).one()
    ultima = _auditoria(engine_dono, 'funcionarios', a.admin.id)[-1]
    assert ultima.campos_alterados == ['nome', 'ultimo_login_em']
    assert depois.atualizado_em > antes
    assert depois.atualizado_por == a.admin.id


def test_sem_a_marca_de_login_o_ultimo_acesso_e_auditado(engine_app, engine_dono, lojas):
    """A marca vale só para a transação do login: fora dela, nada muda no comportamento antigo."""
    a, _ = lojas
    with sessao(engine_app, 'painel', funcionario_id=a.admin.id, loja_id=a.loja.id) as db:
        db.execute(text('UPDATE funcionarios SET ultimo_login_em = now() WHERE id = :id'), {'id': a.admin.id})
    assert _auditoria(engine_dono, 'funcionarios', a.admin.id)[-1].campos_alterados == ['ultimo_login_em']
