"""Catálogos fixos: módulos (funcionalidades) e recursos com nível de acesso.

Mudam junto com o código, por migração (estrutura.md, 1.4 e 1.8). Os mesmos códigos estão em
app/auth/catalogo.py; um teste garante que os dois batem.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (codigo, nome, opcional)
FUNCIONALIDADES = [
    ('inicio', 'Início', False),
    ('agenda', 'Agenda e Agendamentos', False),
    ('clientes', 'Clientes', False),
    ('funcionarios', 'Funcionários', False),
    ('configuracoes', 'Configurações', False),
    ('servicos', 'Serviços', True),
    ('materiais', 'Materiais', True),
    ('controle_tempo', 'Controle de Tempo', True),
    ('locais', 'Locais (salas, cadeiras, macas, links online...)', True),
]

# (codigo, nome, modulo, leitura permite, escrita permite)
RECURSOS = [
    (
        'agenda_propria',
        'Minha agenda',
        'agenda',
        'Ver os próprios agendamentos',
        'Criar, remarcar, mudar status e cancelar os próprios',
    ),
    (
        'agenda_equipe',
        'Agenda da equipe',
        'agenda',
        'Ver agendamentos de todos',
        'Criar, remarcar, mudar status e cancelar de qualquer profissional',
    ),
    (
        'config_agendamentos',
        'Horários e bloqueios',
        'agenda',
        'Ver a jornada dos perfis e os bloqueios',
        'Editar a jornada dos perfis, bloqueios, folgas e feriados',
    ),
    ('clientes', 'Clientes', 'clientes', 'Ver lista e ficha', 'Cadastrar, editar, inativar'),
    (
        'funcionarios',
        'Funcionários',
        'funcionarios',
        'Ver lista',
        'Cadastrar, editar, inativar, definir cargo e perfil',
    ),
    (
        'perfis_acesso',
        'Perfis de acesso',
        'funcionarios',
        'Ver perfis e seus níveis',
        'Criar e editar perfis e níveis',
    ),
    (
        'servicos',
        'Serviços',
        'servicos',
        'Ver serviços',
        'Cadastrar, editar, vincular profissionais e materiais',
    ),
    (
        'materiais',
        'Materiais',
        'materiais',
        'Ver estoque e movimentações',
        'Cadastrar, editar, lançar entradas, ajustes e perdas',
    ),
    (
        'locais',
        'Locais',
        'locais',
        'Ver salas, cadeiras, links online...',
        'Cadastrar, editar, inativar e definir como a loja chama os locais',
    ),
    (
        'ponto_proprio',
        'Meu ponto',
        'controle_tempo',
        'Ver os próprios registros',
        'Registrar entrada e saída',
    ),
    (
        'ponto_equipe',
        'Ponto da equipe',
        'controle_tempo',
        'Ver registros de todos',
        'Corrigir registros (com justificativa)',
    ),
    (
        'config_loja',
        'Dados da loja',
        'configuracoes',
        'Ver logo, nome, contato, endereço e CNPJ',
        'Editar esses dados',
    ),
]


def upgrade() -> None:
    # ON CONFLICT: um downgrade parcial mantém os itens que ainda estão em uso (ver downgrade)
    conexao = op.get_bind()
    conexao.execute(sa.text("SELECT set_config('app.origem', 'sistema', true)"))
    for codigo, nome, opcional in FUNCIONALIDADES:
        conexao.execute(
            sa.text(
                'INSERT INTO funcionalidades (codigo, nome, opcional) VALUES (:c, :n, :o)'
                ' ON CONFLICT (codigo) WHERE excluido_em IS NULL DO NOTHING'
            ),
            {'c': codigo, 'n': nome, 'o': opcional},
        )
    for ordem, (codigo, nome, modulo, leitura, escrita) in enumerate(RECURSOS, start=1):
        conexao.execute(
            sa.text(
                'INSERT INTO recursos (funcionalidade_id, codigo, nome, descricao, ordem)'
                ' SELECT id, :c, :n, :d, :o FROM funcionalidades WHERE codigo = :m AND excluido_em IS NULL'
                ' ON CONFLICT (codigo) WHERE excluido_em IS NULL DO NOTHING'
            ),
            {
                'c': codigo,
                'n': nome,
                'd': f'Leitura: {leitura}. Escrita: {escrita}.',
                'o': ordem,
                'm': modulo,
            },
        )


def downgrade() -> None:
    """Remove os itens do catálogo que nenhuma loja usa.

    Itens referenciados (perfil_acessos, loja_funcionalidades) ficam, para não apagar dados das
    lojas; num downgrade até a base, a 0001 apaga as tabelas inteiras logo em seguida. O DELETE
    físico é liberado desligando os triggers do usuário só nesta transação.
    """
    recursos = ', '.join(f"'{r[0]}'" for r in RECURSOS)
    funcionalidades = ', '.join(f"'{f[0]}'" for f in FUNCIONALIDADES)
    op.execute(f"""
        ALTER TABLE recursos DISABLE TRIGGER USER;
        ALTER TABLE funcionalidades DISABLE TRIGGER USER;
        DELETE FROM recursos r
         WHERE r.codigo IN ({recursos})
           AND NOT EXISTS (SELECT 1 FROM perfil_acessos pa WHERE pa.recurso_id = r.id);
        DELETE FROM funcionalidades f
         WHERE f.codigo IN ({funcionalidades})
           AND NOT EXISTS (SELECT 1 FROM recursos r WHERE r.funcionalidade_id = f.id)
           AND NOT EXISTS (SELECT 1 FROM loja_funcionalidades lf WHERE lf.funcionalidade_id = f.id);
        ALTER TABLE recursos ENABLE TRIGGER USER;
        ALTER TABLE funcionalidades ENABLE TRIGGER USER;
    """)
