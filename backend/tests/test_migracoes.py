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
    assert len(tabelas_loja) == 19
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
