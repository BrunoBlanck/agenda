"""Migrações: reversíveis, catálogo coerente, modelos iguais ao banco e regras ligadas em toda tabela."""

from alembic import command
from sqlalchemy import create_engine, inspect, select, text

from app.auth.catalogo import MODULOS, RECURSOS
from app.models import Base, Funcionalidade, Recurso
from tests.conftest import URL_DONO, config_alembic, recriar_banco
from tests.fabricas import criar_loja, sessao

TABELAS_LOJA_SEM_ID = {
    'perfil_acessos',
    'servico_funcionarios',
    'servico_materiais',
    'servico_locais',
    'agendamento_materiais',
    'loja_configuracoes',
}


def _tabelas(conexao) -> set[str]:
    return set(inspect(conexao).get_table_names()) - {'alembic_version'}


def test_migracao_e_reversivel():
    url = URL_DONO.set(database=f'{URL_DONO.database}_migracao')
    recriar_banco(url)
    config = config_alembic(url)
    engine = create_engine(url)
    try:
        command.upgrade(config, 'head')
        # Com dados de loja (perfis usando o catálogo), o caminho até a base também funciona
        criar_loja(engine, 'loja-com-dados')
        command.downgrade(config, '0001')
        with engine.connect() as conexao:
            # Itens do catálogo em uso ficam; os demais saem
            assert conexao.execute(text('SELECT count(*) FROM recursos')).scalar() == 12
        command.upgrade(config, 'head')
        command.downgrade(config, 'base')
        with engine.connect() as conexao:
            assert _tabelas(conexao) == set()
            tipos = conexao.execute(
                text(
                    'SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace'
                    " WHERE n.nspname = 'public' AND t.typtype = 'e'"
                )
            ).scalar()
            funcoes = conexao.execute(
                text(
                    'SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace'
                    " WHERE n.nspname = 'public'"
                )
            ).scalar()
        assert (tipos, funcoes) == (0, 0)
        command.upgrade(config, 'head')
        with engine.connect() as conexao:
            assert _tabelas(conexao) == set(Base.metadata.tables)
    finally:
        engine.dispose()
        servidor = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
        with servidor.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        servidor.dispose()


def test_catalogo_do_codigo_bate_com_o_banco(engine_dono):
    with sessao(engine_dono) as db:
        modulos = dict(db.execute(select(Funcionalidade.codigo, Funcionalidade.opcional)).all())
        recursos = dict(
            db.execute(
                select(Recurso.codigo, Funcionalidade.codigo).join(
                    Funcionalidade, Funcionalidade.id == Recurso.funcionalidade_id
                )
            ).all()
        )
    assert modulos == MODULOS
    assert recursos == RECURSOS


def test_modelos_tem_as_mesmas_colunas_do_banco(engine_dono):
    inspetor = inspect(engine_dono)
    assert set(inspetor.get_table_names()) - {'alembic_version'} == set(Base.metadata.tables)
    for nome, tabela in Base.metadata.tables.items():
        banco = {c['name']: c['nullable'] for c in inspetor.get_columns(nome)}
        modelo = {c.name: c.nullable for c in tabela.columns}
        assert set(banco) == set(modelo), nome
        # Coluna obrigatória no banco precisa ser obrigatória no modelo (e vice-versa)
        diferentes = {c for c in banco if banco[c] != modelo[c] and not tabela.columns[c].primary_key}
        assert diferentes == set(), f'{nome}: {diferentes}'


def test_toda_tabela_tem_triggers_de_controle(engine_dono):
    with engine_dono.connect() as conexao:
        linhas = conexao.execute(
            text(
                'SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid'
                ' WHERE NOT t.tgisinternal'
            )
        ).all()
    por_tabela: dict[str, set[str]] = {}
    for tabela, trigger in linhas:
        por_tabela.setdefault(tabela, set()).add(trigger)
    for tabela in set(Base.metadata.tables) - {'auditoria'}:
        esperados = {f'{tabela}_alteracao', f'{tabela}_excluir', f'{tabela}_auditoria'}
        assert esperados <= por_tabela.get(tabela, set()), tabela
    assert 'auditoria_somente_insercao' in por_tabela['auditoria']


def test_toda_tabela_da_loja_tem_isolamento(engine_dono):
    tabelas_loja = {
        n for n, t in Base.metadata.tables.items() if 'atualizado_por' in t.columns and 'loja_id' in t.columns
    }
    tabelas_loja.discard('loja_funcionalidades')  # tabela da plataforma (atualizado_por = superadmin)
    assert len(tabelas_loja) == 21
    with engine_dono.connect() as conexao:
        com_rls = set(
            conexao.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity")
            ).scalars()
        )
        politicas = set(conexao.execute(text('SELECT tablename FROM pg_policies')).scalars())
        restricoes = set(
            conexao.execute(text("SELECT conname FROM pg_constraint WHERE contype IN ('u', 'f')")).scalars()
        )
    assert tabelas_loja == com_rls == politicas
    for tabela in tabelas_loja:
        assert {f'{tabela}_atualizado_por_fk', f'{tabela}_excluido_por_fk'} <= restricoes, tabela
        if tabela not in TABELAS_LOJA_SEM_ID:
            assert f'{tabela}_loja_id_uk' in restricoes, tabela


def test_unicidade_usa_indices_parciais(engine_dono):
    with engine_dono.connect() as conexao:
        unicos_comuns = (
            conexao.execute(
                text(
                    "SELECT conrelid::regclass::text FROM pg_constraint WHERE contype = 'u'"
                    " AND connamespace = 'public'::regnamespace AND conname NOT LIKE '%_loja_id_uk'"
                )
            )
            .scalars()
            .all()
        )
        indices = conexao.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE '%_uk'"
            )
        ).all()
    assert unicos_comuns == []
    assert indices
    for nome, definicao in indices:
        # UNIQUE (loja_id, id) é alvo das FKs compostas e não pode ser parcial (o id nunca se repete)
        if nome.endswith('_loja_id_uk'):
            continue
        assert 'excluido_em IS NULL' in definicao, nome


def test_0003_normaliza_cpf_e_telefone_e_exige_ponto_sem_sobreposicao():
    """Dados gravados antes da validação (A7) são normalizados; ponto sobreposto impede a migração (A11)."""
    import pytest

    from tests.fabricas import criar_funcionario

    url = URL_DONO.set(database=f'{URL_DONO.database}_migracao3')
    recriar_banco(url)
    config = config_alembic(url)
    engine = create_engine(url)
    try:
        # A loja nasce pelo ORM (modelos da versão atual) e o banco volta à 0002 com ela
        command.upgrade(config, 'head')
        loja, perfis = criar_loja(engine, 'loja-x')
        funcionario = criar_funcionario(engine, loja, perfis['Profissional'], 'p@x.com')
        command.downgrade(config, '0002')
        with sessao(engine) as db:
            for nome, cpf, telefone in (
                ('sem_mascara', '52998224725', '11988881111'),
                ('ja_canonico', '123.456.789-09', '(21) 3222-1010'),
                ('colide', '12345678909', '2132221010'),
                ('lixo', 'xyz', 'abc'),
            ):
                db.execute(
                    text(
                        'INSERT INTO clientes (loja_id, nome, sobrenome, cpf, telefone)'
                        " VALUES (:l, :n, 'X', :c, :t)"
                    ),
                    {'l': loja.id, 'n': nome, 'c': cpf, 't': telefone},
                )
            db.execute(
                text("UPDATE funcionarios SET cpf = '52998224725', telefone = '11 99999 0001' WHERE id = :f"),
                {'f': funcionario.id},
            )
            for entrada, saida in (('2026-01-05 08:00', '2026-01-05 12:00'), ('2026-01-05 11:00', None)):
                db.execute(
                    text(
                        'INSERT INTO registros_ponto (loja_id, funcionario_id, entrada, saida)'
                        ' VALUES (:l, :f, :e, :s)'
                    ),
                    {'l': loja.id, 'f': funcionario.id, 'e': entrada, 's': saida},
                )

        with pytest.raises(RuntimeError, match='registros de ponto sobrepostos'):
            command.upgrade(config, 'head')
        with sessao(engine) as db:  # exclusão lógica (trigger) já resolve
            db.execute(text('DELETE FROM registros_ponto WHERE saida IS NULL'))
        command.upgrade(config, 'head')

        with engine.connect() as conexao:
            clientes = dict(
                (nome, (cpf, telefone))
                for nome, cpf, telefone in conexao.execute(text('SELECT nome, cpf, telefone FROM clientes'))
            )
            func = conexao.execute(
                text('SELECT cpf, telefone FROM funcionarios WHERE id = :f'), {'f': funcionario.id}
            ).one()
            auditoria = conexao.execute(
                text(
                    "SELECT count(*) FROM auditoria WHERE tabela = 'clientes' AND operacao = 'alterar'"
                    " AND origem = 'sistema'"
                )
            ).scalar()
        assert clientes['sem_mascara'] == ('529.982.247-25', '(11) 98888-1111')
        assert clientes['ja_canonico'] == ('123.456.789-09', '(21) 3222-1010')
        assert clientes['colide'] == ('12345678909', '(21) 3222-1010')  # CPF repetido: conferência manual
        assert clientes['lixo'] == ('xyz', 'abc')  # não dá para normalizar: fica como está
        assert tuple(func) == ('529.982.247-25', '(11) 99999-0001')
        assert auditoria == 3  # CPF e telefone da 1ª e telefone da 3ª, como alteração do sistema
        command.downgrade(config, '0002')
        command.upgrade(config, 'head')
    finally:
        engine.dispose()
        servidor = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
        with servidor.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        servidor.dispose()


def test_0004_login_fora_do_historico_e_textos_dos_recursos():
    """0004: textos de leitura/escrita separados e login fora da auditoria; o downgrade volta ao da 0003."""
    from app.db import definir_contexto
    from tests.fabricas import criar_funcionario

    url = URL_DONO.set(database=f'{URL_DONO.database}_migracao4')
    recriar_banco(url)
    config = config_alembic(url)
    engine = create_engine(url)

    def logar(funcionario) -> list[list[str]]:
        """UPDATE de login (com a marca); devolve as alterações do funcionário na auditoria."""
        with sessao(engine) as db:
            definir_contexto(
                db, origem='painel', funcionario_id=funcionario.id, loja_id=funcionario.loja_id, login=True
            )
            db.execute(
                text(
                    'UPDATE funcionarios SET ultimo_login_em = now(), senha_hash = gen_random_uuid()::text WHERE id = :f'
                ),
                {'f': funcionario.id},
            )
            return list(
                db.execute(
                    text(
                        "SELECT campos_alterados FROM auditoria WHERE tabela = 'funcionarios'"
                        " AND registro_id = :f AND operacao = 'alterar' ORDER BY id"
                    ),
                    {'f': str(funcionario.id)},
                ).scalars()
            )

    try:
        command.upgrade(config, 'head')
        loja, perfis = criar_loja(engine, 'loja-x')
        funcionario = criar_funcionario(engine, loja, perfis['Profissional'], 'p@x.com')
        with engine.connect() as conexao:
            textos = {
                c: (leitura, escrita)
                for c, leitura, escrita in conexao.execute(
                    text('SELECT codigo, leitura, escrita FROM recursos')
                )
            }
        assert len(textos) == 12
        assert textos['clientes'] == ('Ver lista e ficha', 'Cadastrar, editar, inativar')
        assert textos['locais'] == (
            'Ver salas, cadeiras, links online...',
            'Cadastrar, editar, inativar e definir como a loja chama os locais',
        )
        assert logar(funcionario) == []  # o login ficou fora da auditoria

        command.downgrade(config, '0003')
        with engine.connect() as conexao:
            colunas = {c['name'] for c in inspect(conexao).get_columns('recursos')}
            funcao = conexao.execute(text("SELECT count(*) FROM pg_proc WHERE proname = 'so_dados_de_login'"))
            assert funcao.scalar() == 0
        assert {'leitura', 'escrita'}.isdisjoint(colunas)
        assert logar(funcionario) == [['senha_hash', 'ultimo_login_em']]  # comportamento da 0003

        command.upgrade(config, 'head')
        assert len(logar(funcionario)) == 1  # o novo login não entrou
    finally:
        engine.dispose()
        servidor = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
        with servidor.connect() as conexao:
            conexao.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        servidor.dispose()
