"""Schema inicial: enums, funções de controle, tabelas da plataforma e do painel da loja.

Segue o estrutura.md (seções 1, 2 e 3). Tabelas marcadas como (removida) não existem.

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.config import get_settings
from migrations.auxiliares import (
    CONTROLE_LOJA,
    CONTROLE_PLATAFORMA,
    fks_controle_loja,
    ligar_triggers,
    tabela_loja,
)

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas do Painel da Loja (seção 2), na ordem de criação
TABELAS_LOJA = [
    'perfis',
    'perfil_acessos',
    'cargos',
    'funcionarios',
    'perfil_horarios',
    'bloqueios_agenda',
    'clientes',
    'servicos',
    'servico_funcionarios',
    'categorias_material',
    'materiais',
    'servico_materiais',
    'locais',
    'servico_locais',
    'agendamentos',
    'agendamento_materiais',
    'movimentacoes_estoque',
    'registros_ponto',
    'loja_configuracoes',
]

TABELAS_PLATAFORMA = [
    'superadmin_usuarios',
    'planos',
    'funcionalidades',
    'recursos',
    'lojas',
    'loja_funcionalidades',
    'auditoria',
]

ENUMS = {
    'status_loja': ('ativa', 'suspensa', 'cancelada'),
    'status_agendamento': ('pendente', 'agendado', 'confirmado', 'concluido', 'cancelado', 'nao_compareceu'),
    'origem_agendamento': ('painel', 'site'),
    'canal_cliente': ('loja', 'whatsapp', 'site'),
    'tipo_movimentacao': ('entrada', 'saida_atendimento', 'ajuste', 'perda'),
    'origem_ponto': ('sistema', 'manual'),
    'nivel_acesso': ('nenhum', 'leitura', 'escrita'),
    'tipo_local': ('presencial', 'online'),
    'tipo_loja': ('clinica', 'barbearia', 'escola'),
    'operacao_auditoria': ('inserir', 'alterar', 'excluir', 'restaurar'),
    'origem_auditoria': ('painel', 'superadmin', 'site', 'sistema'),
}


# ---------------------------------------------------------------------------------------------
# Funções
# ---------------------------------------------------------------------------------------------


def _corpo_alteracao(quem_exclui: str, atualizacao: str) -> str:
    """Corpo comum das funções de alteração.

    - INSERT: criado_em/atualizado_em = now(); a linha nasce não excluída.
    - UPDATE: criado_em nunca muda; atualizado_em = now().
    - Exclusão (excluido_em passa a ter valor): grava excluido_em = now() e quem excluiu.
    - Restauração (excluido_em volta a NULL): limpa excluido_por.
    quem_exclui: expressão SQL com o id de quem está agindo.
    atualizacao: comandos extras (ex.: preencher atualizado_por).
    """
    return f"""
BEGIN
  NEW.atualizado_em := now();
  IF TG_OP = 'INSERT' THEN
    NEW.criado_em := now();
    NEW.excluido_em := NULL;
    NEW.excluido_por := NULL;
  ELSE
    NEW.criado_em := OLD.criado_em;
    IF OLD.excluido_em IS NULL AND NEW.excluido_em IS NOT NULL THEN
      NEW.excluido_em := now();
      NEW.excluido_por := {quem_exclui};
    ELSIF NEW.excluido_em IS NULL THEN
      NEW.excluido_por := NULL;
    ELSE
      NEW.excluido_em := OLD.excluido_em;
      NEW.excluido_por := OLD.excluido_por;
    END IF;
  END IF;
  {atualizacao}
  RETURN NEW;
END
"""


FUNCIONARIO = "contexto_uuid('app.funcionario_id')"
SUPERADMIN = "contexto_uuid('app.superadmin_id')"


def criar_funcoes() -> None:
    op.execute("""
        -- Lê um id gravado no contexto da transação (set_config). Vazio ou ausente = NULL.
        CREATE FUNCTION contexto_uuid(nome text) RETURNS uuid
          LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting(nome, true), '')::uuid $$;

        -- RLS das tabelas da loja: loja do contexto, ou superadmin (enxerga todas)
        CREATE FUNCTION pode_acessar_loja(alvo uuid) RETURNS boolean
          LANGUAGE sql STABLE AS
        $$ SELECT alvo = contexto_uuid('app.loja_id') OR contexto_uuid('app.superadmin_id') IS NOT NULL $$;
    """)

    funcoes = {
        # Tabelas da plataforma: quem exclui é o superadmin
        'registrar_alteracao': (SUPERADMIN, ''),
        # Tabelas da loja: atualizado_por e excluido_por são o funcionário logado
        'registrar_alteracao_loja': (FUNCIONARIO, f'NEW.atualizado_por := {FUNCIONARIO};'),
        # loja_funcionalidades: atualizado_por é o superadmin
        'registrar_alteracao_superadmin': (SUPERADMIN, f'NEW.atualizado_por := {SUPERADMIN};'),
        # lojas: guarda a última edição da loja e a do superadmin separadamente
        'registrar_alteracao_lojas': (
            SUPERADMIN,
            f"""IF {FUNCIONARIO} IS NOT NULL THEN NEW.atualizado_por_funcionario := {FUNCIONARIO}; END IF;
  IF {SUPERADMIN} IS NOT NULL THEN NEW.atualizado_por_superadmin := {SUPERADMIN}; END IF;""",
        ),
    }
    for nome, (quem_exclui, atualizacao) in funcoes.items():
        op.execute(
            f'CREATE FUNCTION {nome}() RETURNS trigger LANGUAGE plpgsql AS $$'
            f'{_corpo_alteracao(quem_exclui, atualizacao)}$$;'
        )

    op.execute("""
        -- Converte DELETE em exclusão lógica. Argumentos: colunas da chave primária.
        -- A função de alteração (BEFORE UPDATE) preenche excluido_em e excluido_por.
        CREATE FUNCTION excluir_logicamente() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          condicao text := '';
          coluna text;
        BEGIN
          FOREACH coluna IN ARRAY TG_ARGV LOOP
            condicao := condicao || format(' AND %I = ($1).%I', coluna, coluna);
          END LOOP;
          EXECUTE format('UPDATE %I.%I SET excluido_em = now() WHERE excluido_em IS NULL',
                         TG_TABLE_SCHEMA, TG_TABLE_NAME) || condicao
            USING OLD;
          RETURN NULL; -- cancela o DELETE físico
        END $$;

        -- Auditoria genérica. Argumentos: colunas da chave primária.
        -- Não guarda senha_hash (só indica em campos_alterados que a senha mudou).
        -- UPDATE sem nenhuma mudança real não gera linha.
        CREATE FUNCTION registrar_auditoria() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          novo jsonb := to_jsonb(NEW);
          velho jsonb;
          op operacao_auditoria;
          campos text[];
          chave text;
        BEGIN
          IF TG_OP = 'UPDATE' THEN
            velho := to_jsonb(OLD);
            SELECT array_agg(n.key ORDER BY n.key) INTO campos
              FROM jsonb_each(novo) n
             WHERE n.value IS DISTINCT FROM velho -> n.key
               AND n.key NOT IN ('atualizado_em', 'atualizado_por',
                                 'atualizado_por_funcionario', 'atualizado_por_superadmin');
            IF campos IS NULL THEN
              RETURN NULL;
            END IF;
          END IF;

          op := CASE
            WHEN TG_OP = 'INSERT' THEN 'inserir'
            WHEN OLD.excluido_em IS NULL AND NEW.excluido_em IS NOT NULL THEN 'excluir'
            WHEN OLD.excluido_em IS NOT NULL AND NEW.excluido_em IS NULL THEN 'restaurar'
            ELSE 'alterar'
          END;

          SELECT string_agg(novo ->> a.coluna, ':' ORDER BY a.ordem) INTO chave
            FROM unnest(TG_ARGV) WITH ORDINALITY AS a(coluna, ordem);

          INSERT INTO auditoria (loja_id, tabela, registro_id, operacao, antes, depois,
                                 campos_alterados, funcionario_id, superadmin_id, origem, ip)
          VALUES (
            CASE WHEN TG_TABLE_NAME = 'lojas' THEN (novo ->> 'id')::uuid
                 ELSE (novo ->> 'loja_id')::uuid END,
            TG_TABLE_NAME,
            chave,
            op,
            velho - 'senha_hash',
            novo - 'senha_hash',
            CASE WHEN op = 'alterar' THEN campos END,
            contexto_uuid('app.funcionario_id'),
            contexto_uuid('app.superadmin_id'),
            coalesce(nullif(current_setting('app.origem', true), ''), 'sistema')::origem_auditoria,
            nullif(current_setting('app.ip', true), '')::inet
          );
          RETURN NULL;
        END $$;

        -- A auditoria só recebe inserções (além do REVOKE, protege até do dono do schema)
        CREATE FUNCTION bloquear_alteracao_auditoria() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'A auditoria não pode ser alterada nem excluída.'
            USING ERRCODE = 'insufficient_privilege';
        END $$;

        -- loja_funcionalidades só aceita módulos opcionais (estrutura.md, 1.7)
        CREATE FUNCTION validar_modulo_opcional() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM funcionalidades
                          WHERE id = NEW.funcionalidade_id AND opcional) THEN
            RAISE EXCEPTION 'Só módulos opcionais podem ser ligados ou desligados por loja.'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END $$;

        -- Estoque: quantidade_atual só muda por movimentacoes_estoque (estrutura.md, 2.11)
        CREATE FUNCTION aplicar_movimentacao_estoque() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          UPDATE materiais SET quantidade_atual = quantidade_atual + NEW.quantidade
           WHERE loja_id = NEW.loja_id AND id = NEW.material_id;
          RETURN NULL;
        END $$;

        CREATE FUNCTION proteger_quantidade_material() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' AND NEW.quantidade_atual <> 0 THEN
            RAISE EXCEPTION 'O estoque inicial deve ser lançado como uma entrada de estoque.'
              USING ERRCODE = 'check_violation';
          END IF;
          -- pg_trigger_depth() >= 2: a alteração veio do trigger de movimentação
          IF TG_OP = 'UPDATE' AND NEW.quantidade_atual IS DISTINCT FROM OLD.quantidade_atual
             AND pg_trigger_depth() < 2 THEN
            RAISE EXCEPTION 'A quantidade do material só muda por uma movimentação de estoque.'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END $$;

        -- Movimentação é histórico: não muda nem é excluída (corrige-se com um ajuste)
        CREATE FUNCTION proteger_movimentacao() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.excluido_em IS NOT NULL AND OLD.excluido_em IS NULL THEN
            RAISE EXCEPTION 'Movimentações de estoque não podem ser excluídas. Lance um ajuste.'
              USING ERRCODE = 'check_violation';
          END IF;
          IF (NEW.material_id, NEW.tipo, NEW.quantidade, NEW.agendamento_id)
             IS DISTINCT FROM (OLD.material_id, OLD.tipo, OLD.quantidade, OLD.agendamento_id) THEN
            RAISE EXCEPTION 'Movimentações de estoque não podem ser alteradas. Lance um ajuste.'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END $$;
    """)


# ---------------------------------------------------------------------------------------------
# Plataforma (seção 1)
# ---------------------------------------------------------------------------------------------


def criar_tabelas_plataforma() -> None:
    op.execute(f"""
        CREATE TABLE superadmin_usuarios (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          nome            varchar(150) NOT NULL,
          email           varchar(150) NOT NULL,
          senha_hash      varchar(255) NOT NULL,
          ativo           boolean NOT NULL DEFAULT true,
          ultimo_login_em timestamptz,
          criado_em       timestamptz NOT NULL DEFAULT now(),
          atualizado_em   timestamptz NOT NULL DEFAULT now(),
          excluido_em     timestamptz,
          excluido_por    uuid REFERENCES superadmin_usuarios (id)
        );
        CREATE UNIQUE INDEX superadmin_usuarios_email_uk
          ON superadmin_usuarios (lower(email)) WHERE excluido_em IS NULL;

        CREATE TABLE planos (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          nome          varchar(80) NOT NULL,
          descricao     text,
          preco_mensal  numeric(10,2) NOT NULL CHECK (preco_mensal >= 0),
          ativo         boolean NOT NULL DEFAULT true,
          {CONTROLE_PLATAFORMA}
        );
        CREATE UNIQUE INDEX planos_nome_uk ON planos (nome) WHERE excluido_em IS NULL;

        CREATE TABLE funcionalidades (
          id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          codigo     varchar(50) NOT NULL,
          nome       varchar(100) NOT NULL,
          descricao  text,
          opcional   boolean NOT NULL,
          ativo      boolean NOT NULL DEFAULT true,
          {CONTROLE_PLATAFORMA}
        );
        CREATE UNIQUE INDEX funcionalidades_codigo_uk ON funcionalidades (codigo) WHERE excluido_em IS NULL;

        CREATE TABLE recursos (
          id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          funcionalidade_id  uuid NOT NULL REFERENCES funcionalidades (id),
          codigo             varchar(50) NOT NULL,
          nome               varchar(100) NOT NULL,
          descricao          text,
          ordem              smallint,
          {CONTROLE_PLATAFORMA}
        );
        CREATE UNIQUE INDEX recursos_codigo_uk ON recursos (codigo) WHERE excluido_em IS NULL;

        CREATE TABLE lojas (
          id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tipo                        tipo_loja NOT NULL,
          nome                        varchar(150) NOT NULL,
          nome_fantasia               varchar(150),
          cnpj                        varchar(18),
          logo_url                    varchar(500),
          slug                        varchar(60) NOT NULL
                                        CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
          email                       varchar(150),
          telefone                    varchar(20),
          cep                         varchar(9),
          logradouro                  varchar(150),
          numero                      varchar(10),
          complemento                 varchar(80),
          bairro                      varchar(80),
          cidade                      varchar(80),
          uf                          char(2),
          fuso_horario                varchar(50) NOT NULL DEFAULT 'America/Sao_Paulo',
          plano_id                    uuid REFERENCES planos (id),
          status                      status_loja NOT NULL DEFAULT 'ativa',
          criado_por                  uuid REFERENCES superadmin_usuarios (id)
                                        DEFAULT contexto_uuid('app.superadmin_id'),
          atualizado_por_funcionario  uuid,
          atualizado_por_superadmin   uuid REFERENCES superadmin_usuarios (id),
          {CONTROLE_PLATAFORMA}
        );
        CREATE UNIQUE INDEX lojas_slug_uk ON lojas (slug) WHERE excluido_em IS NULL;
        CREATE UNIQUE INDEX lojas_cnpj_uk ON lojas (cnpj)
          WHERE cnpj IS NOT NULL AND excluido_em IS NULL;

        CREATE TABLE loja_funcionalidades (
          loja_id            uuid NOT NULL REFERENCES lojas (id),
          funcionalidade_id  uuid NOT NULL REFERENCES funcionalidades (id),
          habilitado         boolean NOT NULL,
          observacao         text,
          expira_em          timestamptz,
          atualizado_por     uuid REFERENCES superadmin_usuarios (id),
          {CONTROLE_PLATAFORMA},
          PRIMARY KEY (loja_id, funcionalidade_id)
        );
        CREATE TRIGGER loja_funcionalidades_modulo_opcional
          BEFORE INSERT OR UPDATE OF funcionalidade_id ON loja_funcionalidades
          FOR EACH ROW EXECUTE FUNCTION validar_modulo_opcional();

        -- Somente inserção: sem colunas de controle. FK de funcionario_id é criada depois de funcionarios.
        CREATE TABLE auditoria (
          id                bigserial PRIMARY KEY,
          loja_id           uuid REFERENCES lojas (id),
          tabela            varchar(60) NOT NULL,
          registro_id       text NOT NULL,
          operacao          operacao_auditoria NOT NULL,
          antes             jsonb,
          depois            jsonb,
          campos_alterados  text[],
          funcionario_id    uuid,
          superadmin_id     uuid REFERENCES superadmin_usuarios (id),
          origem            origem_auditoria NOT NULL,
          ip                inet,
          criado_em         timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX auditoria_loja_tabela_criado_idx ON auditoria (loja_id, tabela, criado_em DESC);
        CREATE TRIGGER auditoria_somente_insercao BEFORE UPDATE OR DELETE ON auditoria
          FOR EACH ROW EXECUTE FUNCTION bloquear_alteracao_auditoria();
    """)

    for tabela in ('superadmin_usuarios', 'planos', 'funcionalidades', 'recursos'):
        ligar_triggers(tabela, 'plataforma')
    ligar_triggers('lojas', 'lojas')
    ligar_triggers('loja_funcionalidades', 'loja_funcionalidades', ('loja_id', 'funcionalidade_id'))


# ---------------------------------------------------------------------------------------------
# Painel da Loja (seção 2)
# ---------------------------------------------------------------------------------------------


def criar_tabelas_loja() -> None:
    op.execute(f"""
        CREATE TABLE perfis (
          id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id       uuid NOT NULL REFERENCES lojas (id),
          nome          varchar(60) NOT NULL,
          descricao     text,
          padrao        boolean NOT NULL DEFAULT false,
          acesso_total  boolean NOT NULL DEFAULT false,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX perfis_nome_uk ON perfis (loja_id, nome) WHERE excluido_em IS NULL;
    """)
    tabela_loja('perfis')

    op.execute(f"""
        CREATE TABLE perfil_acessos (
          loja_id     uuid NOT NULL REFERENCES lojas (id),
          perfil_id   uuid NOT NULL,
          recurso_id  uuid NOT NULL REFERENCES recursos (id),
          nivel       nivel_acesso NOT NULL,
          {CONTROLE_LOJA},
          PRIMARY KEY (perfil_id, recurso_id),
          CONSTRAINT perfil_acessos_perfil_fk FOREIGN KEY (loja_id, perfil_id) REFERENCES perfis (loja_id, id)
        );
    """)
    tabela_loja('perfil_acessos', ('perfil_id', 'recurso_id'))

    op.execute(f"""
        CREATE TABLE cargos (
          id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id  uuid NOT NULL REFERENCES lojas (id),
          nome     varchar(80) NOT NULL,
          ativo    boolean NOT NULL DEFAULT true,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX cargos_nome_uk ON cargos (loja_id, nome) WHERE excluido_em IS NULL;
    """)
    tabela_loja('cargos')

    op.execute(f"""
        CREATE TABLE funcionarios (
          id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id                 uuid NOT NULL REFERENCES lojas (id),
          perfil_id               uuid NOT NULL,
          cargo_id                uuid,
          nome                    varchar(150) NOT NULL,
          cpf                     varchar(14),
          email                   varchar(150) NOT NULL,
          senha_hash              varchar(255) NOT NULL,
          telefone                varchar(20),
          cor_agenda              varchar(7) CHECK (cor_agenda ~ '^#[0-9a-fA-F]{{6}}$'),
          ativo                   boolean NOT NULL DEFAULT true,
          ultimo_login_em         timestamptz,
          criado_por_funcionario  uuid DEFAULT contexto_uuid('app.funcionario_id'),
          criado_por_superadmin   uuid REFERENCES superadmin_usuarios (id)
                                    DEFAULT contexto_uuid('app.superadmin_id'),
          {CONTROLE_LOJA},
          CONSTRAINT funcionarios_perfil_fk FOREIGN KEY (loja_id, perfil_id) REFERENCES perfis (loja_id, id),
          CONSTRAINT funcionarios_cargo_fk FOREIGN KEY (loja_id, cargo_id) REFERENCES cargos (loja_id, id),
          CONSTRAINT funcionarios_um_criador_ck
            CHECK (num_nonnulls(criado_por_funcionario, criado_por_superadmin) <= 1)
        );
        CREATE UNIQUE INDEX funcionarios_email_uk ON funcionarios (loja_id, lower(email)) WHERE excluido_em IS NULL;
        CREATE UNIQUE INDEX funcionarios_cpf_uk ON funcionarios (loja_id, cpf)
          WHERE cpf IS NOT NULL AND excluido_em IS NULL;
    """)
    tabela_loja('funcionarios')
    op.execute("""
        ALTER TABLE funcionarios ADD CONSTRAINT funcionarios_criado_por_funcionario_fk
          FOREIGN KEY (loja_id, criado_por_funcionario) REFERENCES funcionarios (loja_id, id);
        ALTER TABLE lojas ADD CONSTRAINT lojas_atualizado_por_funcionario_fk
          FOREIGN KEY (id, atualizado_por_funcionario) REFERENCES funcionarios (loja_id, id);
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_funcionario_fk
          FOREIGN KEY (loja_id, funcionario_id) REFERENCES funcionarios (loja_id, id);
    """)

    op.execute(f"""
        CREATE TABLE perfil_horarios (
          id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id      uuid NOT NULL REFERENCES lojas (id),
          perfil_id    uuid NOT NULL,
          dia_semana   smallint NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
          hora_inicio  time NOT NULL,
          hora_fim     time NOT NULL,
          {CONTROLE_LOJA},
          CONSTRAINT perfil_horarios_perfil_fk FOREIGN KEY (loja_id, perfil_id)
            REFERENCES perfis (loja_id, id) ON DELETE CASCADE,
          CONSTRAINT perfil_horarios_faixa_ck CHECK (hora_fim > hora_inicio)
        );
        CREATE INDEX perfil_horarios_perfil_idx ON perfil_horarios (loja_id, perfil_id, dia_semana);
    """)
    tabela_loja('perfil_horarios')

    op.execute(f"""
        CREATE TABLE bloqueios_agenda (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          perfil_id       uuid,
          funcionario_id  uuid,
          inicio          timestamptz NOT NULL,
          fim             timestamptz NOT NULL,
          motivo          varchar(150),
          criado_por      uuid DEFAULT contexto_uuid('app.funcionario_id'),
          {CONTROLE_LOJA},
          CONSTRAINT bloqueios_agenda_perfil_fk FOREIGN KEY (loja_id, perfil_id)
            REFERENCES perfis (loja_id, id) ON DELETE CASCADE,
          CONSTRAINT bloqueios_agenda_funcionario_fk FOREIGN KEY (loja_id, funcionario_id)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT bloqueios_agenda_criado_por_fk FOREIGN KEY (loja_id, criado_por)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT bloqueios_agenda_periodo_ck CHECK (fim > inicio),
          CONSTRAINT bloqueios_agenda_alvo_ck CHECK (perfil_id IS NULL OR funcionario_id IS NULL)
        );
        CREATE INDEX bloqueios_agenda_periodo_idx ON bloqueios_agenda (loja_id, inicio);
    """)
    tabela_loja('bloqueios_agenda')

    op.execute(f"""
        CREATE TABLE clientes (
          id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id          uuid NOT NULL REFERENCES lojas (id),
          nome             varchar(60) NOT NULL,
          sobrenome        varchar(100) NOT NULL,
          cpf              varchar(14),
          telefone         varchar(20) NOT NULL,
          email            varchar(150),
          data_nascimento  date,
          observacoes      text,
          canais           canal_cliente[] NOT NULL DEFAULT '{{}}',
          ativo            boolean NOT NULL DEFAULT true,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX clientes_cpf_uk ON clientes (loja_id, cpf)
          WHERE cpf IS NOT NULL AND excluido_em IS NULL;
        CREATE INDEX clientes_telefone_idx ON clientes (loja_id, telefone);
        CREATE INDEX clientes_nome_idx ON clientes (loja_id, nome, sobrenome);
    """)
    tabela_loja('clientes')

    op.execute(f"""
        CREATE TABLE servicos (
          id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id          uuid NOT NULL REFERENCES lojas (id),
          nome             varchar(120) NOT NULL,
          descricao        text,
          duracao_minutos  integer NOT NULL CHECK (duracao_minutos > 0),
          preco            numeric(10,2) CHECK (preco >= 0),
          ativo            boolean NOT NULL DEFAULT true,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX servicos_nome_uk ON servicos (loja_id, nome) WHERE excluido_em IS NULL;

    """)
    tabela_loja('servicos')
    op.execute(f"""
        CREATE TABLE servico_funcionarios (
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          servico_id      uuid NOT NULL,
          funcionario_id  uuid NOT NULL,
          {CONTROLE_LOJA},
          PRIMARY KEY (servico_id, funcionario_id),
          CONSTRAINT servico_funcionarios_servico_fk FOREIGN KEY (loja_id, servico_id)
            REFERENCES servicos (loja_id, id),
          CONSTRAINT servico_funcionarios_funcionario_fk FOREIGN KEY (loja_id, funcionario_id)
            REFERENCES funcionarios (loja_id, id)
        );
    """)
    tabela_loja('servico_funcionarios', ('servico_id', 'funcionario_id'))

    op.execute(f"""
        CREATE TABLE categorias_material (
          id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id  uuid NOT NULL REFERENCES lojas (id),
          nome     varchar(80) NOT NULL,
          {CONTROLE_LOJA}
        );
        CREATE UNIQUE INDEX categorias_material_nome_uk ON categorias_material (loja_id, nome)
          WHERE excluido_em IS NULL;

    """)
    tabela_loja('categorias_material')
    op.execute(f"""
        CREATE TABLE materiais (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id           uuid NOT NULL REFERENCES lojas (id),
          categoria_id      uuid,
          nome              varchar(150) NOT NULL,
          unidade           varchar(10) NOT NULL,
          quantidade_atual  numeric(10,2) NOT NULL DEFAULT 0,
          estoque_minimo    numeric(10,2) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
          ativo             boolean NOT NULL DEFAULT true,
          {CONTROLE_LOJA},
          CONSTRAINT materiais_categoria_fk FOREIGN KEY (loja_id, categoria_id)
            REFERENCES categorias_material (loja_id, id)
        );
        CREATE UNIQUE INDEX materiais_nome_uk ON materiais (loja_id, nome) WHERE excluido_em IS NULL;
        CREATE TRIGGER materiais_quantidade BEFORE INSERT OR UPDATE ON materiais
          FOR EACH ROW EXECUTE FUNCTION proteger_quantidade_material();

    """)
    tabela_loja('materiais')
    op.execute(f"""
        CREATE TABLE servico_materiais (
          loja_id      uuid NOT NULL REFERENCES lojas (id),
          servico_id   uuid NOT NULL,
          material_id  uuid NOT NULL,
          quantidade   numeric(10,2) NOT NULL CHECK (quantidade > 0),
          {CONTROLE_LOJA},
          PRIMARY KEY (servico_id, material_id),
          CONSTRAINT servico_materiais_servico_fk FOREIGN KEY (loja_id, servico_id)
            REFERENCES servicos (loja_id, id),
          CONSTRAINT servico_materiais_material_fk FOREIGN KEY (loja_id, material_id)
            REFERENCES materiais (loja_id, id)
        );
    """)
    tabela_loja('servico_materiais', ('servico_id', 'material_id'))

    op.execute(f"""
        CREATE TABLE locais (
          id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id      uuid NOT NULL REFERENCES lojas (id),
          nome         varchar(80) NOT NULL,
          tipo         tipo_local NOT NULL DEFAULT 'presencial',
          link_padrao  varchar(500),
          descricao    text,
          ativo        boolean NOT NULL DEFAULT true,
          {CONTROLE_LOJA},
          CONSTRAINT locais_link_so_online_ck CHECK (tipo = 'online' OR link_padrao IS NULL)
        );
        CREATE UNIQUE INDEX locais_nome_uk ON locais (loja_id, nome) WHERE excluido_em IS NULL;

    """)
    tabela_loja('locais')
    op.execute(f"""
        CREATE TABLE servico_locais (
          loja_id     uuid NOT NULL REFERENCES lojas (id),
          servico_id  uuid NOT NULL,
          local_id    uuid NOT NULL,
          {CONTROLE_LOJA},
          PRIMARY KEY (servico_id, local_id),
          CONSTRAINT servico_locais_servico_fk FOREIGN KEY (loja_id, servico_id)
            REFERENCES servicos (loja_id, id),
          CONSTRAINT servico_locais_local_fk FOREIGN KEY (loja_id, local_id)
            REFERENCES locais (loja_id, id)
        );
    """)
    tabela_loja('servico_locais', ('servico_id', 'local_id'))

    op.execute(f"""
        CREATE TABLE agendamentos (
          id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id              uuid NOT NULL REFERENCES lojas (id),
          cliente_id           uuid NOT NULL,
          servico_id           uuid,
          funcionario_id       uuid NOT NULL,
          local_id             uuid,
          link_reuniao         varchar(500),
          inicio               timestamptz NOT NULL,
          fim                  timestamptz NOT NULL,
          preco                numeric(10,2) CHECK (preco >= 0),
          status               status_agendamento NOT NULL DEFAULT 'agendado',
          origem               origem_agendamento NOT NULL DEFAULT 'painel',
          observacoes          text,
          motivo_cancelamento  text,
          criado_por           uuid DEFAULT contexto_uuid('app.funcionario_id'),
          {CONTROLE_LOJA},
          CONSTRAINT agendamentos_cliente_fk FOREIGN KEY (loja_id, cliente_id)
            REFERENCES clientes (loja_id, id),
          CONSTRAINT agendamentos_servico_fk FOREIGN KEY (loja_id, servico_id)
            REFERENCES servicos (loja_id, id),
          CONSTRAINT agendamentos_funcionario_fk FOREIGN KEY (loja_id, funcionario_id)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT agendamentos_local_fk FOREIGN KEY (loja_id, local_id)
            REFERENCES locais (loja_id, id),
          CONSTRAINT agendamentos_criado_por_fk FOREIGN KEY (loja_id, criado_por)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT agendamentos_periodo_ck CHECK (fim > inicio),
          CONSTRAINT agendamentos_motivo_cancelamento_ck
            CHECK (status <> 'cancelado' OR nullif(btrim(motivo_cancelamento), '') IS NOT NULL),
          CONSTRAINT agendamentos_sem_conflito EXCLUDE USING gist (
            funcionario_id WITH =,
            tstzrange(inicio, fim) WITH &&
          ) WHERE (status NOT IN ('cancelado', 'nao_compareceu') AND excluido_em IS NULL),
          CONSTRAINT agendamentos_local_sem_conflito EXCLUDE USING gist (
            local_id WITH =,
            tstzrange(inicio, fim) WITH &&
          ) WHERE (local_id IS NOT NULL AND status NOT IN ('cancelado', 'nao_compareceu')
                   AND excluido_em IS NULL)
        );
        CREATE INDEX agendamentos_inicio_idx ON agendamentos (loja_id, inicio);
        CREATE INDEX agendamentos_funcionario_idx ON agendamentos (loja_id, funcionario_id, inicio);
        CREATE INDEX agendamentos_cliente_idx ON agendamentos (loja_id, cliente_id);
        CREATE INDEX agendamentos_local_idx ON agendamentos (loja_id, local_id, inicio);

    """)
    tabela_loja('agendamentos')
    op.execute(f"""
        CREATE TABLE agendamento_materiais (
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          agendamento_id  uuid NOT NULL,
          material_id     uuid NOT NULL,
          quantidade      numeric(10,2) NOT NULL CHECK (quantidade > 0),
          {CONTROLE_LOJA},
          PRIMARY KEY (agendamento_id, material_id),
          CONSTRAINT agendamento_materiais_agendamento_fk FOREIGN KEY (loja_id, agendamento_id)
            REFERENCES agendamentos (loja_id, id),
          CONSTRAINT agendamento_materiais_material_fk FOREIGN KEY (loja_id, material_id)
            REFERENCES materiais (loja_id, id)
        );
    """)
    tabela_loja('agendamento_materiais', ('agendamento_id', 'material_id'))

    op.execute(f"""
        CREATE TABLE movimentacoes_estoque (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          material_id     uuid NOT NULL,
          tipo            tipo_movimentacao NOT NULL,
          quantidade      numeric(10,2) NOT NULL CHECK (quantidade <> 0),
          agendamento_id  uuid,
          funcionario_id  uuid DEFAULT contexto_uuid('app.funcionario_id'),
          motivo          varchar(200),
          {CONTROLE_LOJA},
          CONSTRAINT movimentacoes_estoque_material_fk FOREIGN KEY (loja_id, material_id)
            REFERENCES materiais (loja_id, id),
          CONSTRAINT movimentacoes_estoque_agendamento_fk FOREIGN KEY (loja_id, agendamento_id)
            REFERENCES agendamentos (loja_id, id),
          CONSTRAINT movimentacoes_estoque_funcionario_fk FOREIGN KEY (loja_id, funcionario_id)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT movimentacoes_estoque_sinal_ck CHECK (
            (tipo <> 'entrada' OR quantidade > 0)
            AND (tipo NOT IN ('saida_atendimento', 'perda') OR quantidade < 0)),
          CONSTRAINT movimentacoes_estoque_agendamento_ck
            CHECK (tipo <> 'saida_atendimento' OR agendamento_id IS NOT NULL),
          CONSTRAINT movimentacoes_estoque_motivo_ck
            CHECK (tipo NOT IN ('ajuste', 'perda') OR nullif(btrim(motivo), '') IS NOT NULL)
        );
        CREATE INDEX movimentacoes_estoque_material_idx
          ON movimentacoes_estoque (loja_id, material_id, criado_em DESC);
        CREATE TRIGGER movimentacoes_estoque_aplicar AFTER INSERT ON movimentacoes_estoque
          FOR EACH ROW EXECUTE FUNCTION aplicar_movimentacao_estoque();
        CREATE TRIGGER movimentacoes_estoque_proteger BEFORE UPDATE ON movimentacoes_estoque
          FOR EACH ROW EXECUTE FUNCTION proteger_movimentacao();
    """)
    tabela_loja('movimentacoes_estoque')

    op.execute(f"""
        CREATE TABLE registros_ponto (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id         uuid NOT NULL REFERENCES lojas (id),
          funcionario_id  uuid NOT NULL,
          entrada         timestamptz NOT NULL,
          saida           timestamptz,
          origem          origem_ponto NOT NULL DEFAULT 'sistema',
          editado_por     uuid,
          justificativa   text,
          {CONTROLE_LOJA},
          CONSTRAINT registros_ponto_funcionario_fk FOREIGN KEY (loja_id, funcionario_id)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT registros_ponto_editado_por_fk FOREIGN KEY (loja_id, editado_por)
            REFERENCES funcionarios (loja_id, id),
          CONSTRAINT registros_ponto_periodo_ck CHECK (saida > entrada),
          CONSTRAINT registros_ponto_justificativa_ck
            CHECK (origem <> 'manual' OR nullif(btrim(justificativa), '') IS NOT NULL)
        );
        CREATE UNIQUE INDEX registros_ponto_um_aberto ON registros_ponto (funcionario_id)
          WHERE saida IS NULL AND excluido_em IS NULL;
        CREATE INDEX registros_ponto_funcionario_idx ON registros_ponto (loja_id, funcionario_id, entrada DESC);

        CREATE TABLE loja_configuracoes (
          loja_id              uuid PRIMARY KEY REFERENCES lojas (id),
          rotulo_local         varchar(40) NOT NULL DEFAULT 'Local',
          rotulo_local_plural  varchar(40) NOT NULL DEFAULT 'Locais',
          {CONTROLE_LOJA}
        );
    """)
    tabela_loja('registros_ponto')
    tabela_loja('loja_configuracoes', ('loja_id',))

    for tabela in TABELAS_LOJA:
        fks_controle_loja(tabela)


# ---------------------------------------------------------------------------------------------
# Permissões do usuário da aplicação
# ---------------------------------------------------------------------------------------------


def conceder_permissoes() -> None:
    papel = get_settings().papel_app
    existe = op.get_bind().execute(text('SELECT 1 FROM pg_roles WHERE rolname = :p'), {'p': papel}).scalar()
    if not existe:
        raise RuntimeError(
            f'O papel "{papel}" (usuário de DATABASE_URL) não existe. '
            'Rode antes: uv run python -m scripts.criar_papel_app'
        )
    op.execute(f"""
        GRANT USAGE ON SCHEMA public TO "{papel}";
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{papel}";
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{papel}";
        -- Auditoria: somente inserção (estrutura.md, 1.9)
        REVOKE UPDATE, DELETE, TRUNCATE ON auditoria FROM "{papel}";
        -- Controle de versão das migrações: só leitura
        REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM "{papel}";
        -- Tabelas futuras criadas pelo dono recebem as mesmas permissões
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
          GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{papel}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
          GRANT USAGE, SELECT ON SEQUENCES TO "{papel}";
    """)


def revogar_permissoes() -> None:
    papel = get_settings().papel_app
    existe = op.get_bind().execute(text('SELECT 1 FROM pg_roles WHERE rolname = :p'), {'p': papel}).scalar()
    if existe:
        op.execute(f"""
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM "{papel}";
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              REVOKE USAGE, SELECT ON SEQUENCES FROM "{papel}";
            REVOKE ALL ON alembic_version FROM "{papel}";
        """)


# ---------------------------------------------------------------------------------------------


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist;')
    for nome, valores in ENUMS.items():
        lista = ', '.join(f"'{v}'" for v in valores)
        op.execute(f'CREATE TYPE {nome} AS ENUM ({lista});')
    criar_funcoes()
    criar_tabelas_plataforma()
    criar_tabelas_loja()
    conceder_permissoes()


def downgrade() -> None:
    revogar_permissoes()
    # Quebra a dependência circular lojas -> funcionarios antes de apagar
    op.execute('ALTER TABLE lojas DROP CONSTRAINT lojas_atualizado_por_funcionario_fk;')
    op.execute('ALTER TABLE auditoria DROP CONSTRAINT auditoria_funcionario_fk;')
    for tabela in reversed(TABELAS_LOJA):
        op.execute(f'DROP TABLE {tabela} CASCADE;')
    for tabela in reversed(TABELAS_PLATAFORMA):
        op.execute(f'DROP TABLE {tabela} CASCADE;')
    op.execute("""
        DROP FUNCTION proteger_movimentacao();
        DROP FUNCTION proteger_quantidade_material();
        DROP FUNCTION aplicar_movimentacao_estoque();
        DROP FUNCTION validar_modulo_opcional();
        DROP FUNCTION bloquear_alteracao_auditoria();
        DROP FUNCTION registrar_auditoria();
        DROP FUNCTION excluir_logicamente();
        DROP FUNCTION registrar_alteracao_lojas();
        DROP FUNCTION registrar_alteracao_superadmin();
        DROP FUNCTION registrar_alteracao_loja();
        DROP FUNCTION registrar_alteracao();
        DROP FUNCTION pode_acessar_loja(uuid);
        DROP FUNCTION contexto_uuid(text);
    """)
    for nome in reversed(ENUMS):
        op.execute(f'DROP TYPE {nome};')
    op.execute('DROP EXTENSION IF EXISTS btree_gist;')
