"""Notificações (NOT-01 a NOT-08), antecedência do cliente (CFG-05) e SMTP por loja (CFG-06).

- **notificacoes:** uma linha por aviso, para um cliente (``tipo = cliente``) ou para um funcionário
  (``tipo = loja``), com o texto congelado e o status de cada canal: site (1 não visualizada, 2
  visualizada), e-mail e WhatsApp (1 pendente, 2 enviado, 3 erro, 4 dado faltando). Tabela da loja como as
  outras (GER-04, GER-08 a GER-12). O status de um canal só avança (trigger ``notificacoes_status_avanca``):
  2, 3 e 4 são finais e uma visualizada não volta a ser não visualizada.
- **Lembrete** (NOT-05): no máximo um por (agendamento, início lembrado), garantido pelo índice único
  parcial ``notificacoes_lembrete_uk``.
- **Fila de e-mail** (NOT-07): índice parcial dos pendentes; a tarefa de fundo descobre as lojas com
  trabalho por ``notificacoes_lojas_com_trabalho(agora)`` (SECURITY DEFINER: lê só ids de lojas ativas,
  passando por cima do RLS, que exige uma loja no contexto) e depois trabalha loja por loja, com o
  contexto dela. ``agendamentos_lembrete_idx`` deixa a busca de lembretes barata.
- **loja_configuracoes:** ``antecedencia_cliente_minutos`` (CFG-05, padrão 120 = o comportamento anterior) e
  o SMTP da loja (CFG-06). ``smtp_senha_cifrada`` (Fernet) é mascarada na auditoria, como ``senha_hash``.

O downgrade volta ``registrar_auditoria`` ao corpo da 0007.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06
"""

import importlib
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.config import get_settings
from migrations.auxiliares import CONTROLE_LOJA, fks_controle_loja, tabela_loja

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_0007 = importlib.import_module('migrations.versions.0007_conta_cliente')

EVENTOS_CLIENTE = (
    'pedido_recebido',
    'agendamento_criado',
    'confirmado',
    'cancelado',
    'horario_alterado',
    'lembrete',
)
EVENTOS_LOJA = ('novo_pedido', 'remarcacao_pedida', 'cancelado_pelo_cliente')

# Colunas que nunca vão para antes/depois da auditoria (só aparecem em campos_alterados)
MASCARA_0008 = (
    "(ARRAY['senha_hash'] || CASE WHEN TG_TABLE_NAME = 'cliente_codigos' THEN ARRAY['codigo']"
    " WHEN TG_TABLE_NAME = 'loja_configuracoes' THEN ARRAY['smtp_senha_cifrada']"
    ' ELSE ARRAY[]::text[] END)'
)


def _lista(valores: Sequence[str]) -> str:
    return ', '.join(f"'{v}'" for v in valores)  # constantes do código, nada vem de fora


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE notificacoes (
          id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          loja_id                     uuid NOT NULL REFERENCES lojas (id),
          tipo                        varchar(10) NOT NULL
                                      CONSTRAINT ck_notificacoes_tipo CHECK (tipo IN ('cliente', 'loja')),
          cliente_id                  uuid,
          funcionario_id              uuid,
          agendamento_id              uuid,
          evento                      varchar(30) NOT NULL,
          titulo                      varchar(120) NOT NULL,
          mensagem                    varchar(1000) NOT NULL,
          status_site                 smallint NOT NULL DEFAULT 1
                                      CONSTRAINT ck_notificacoes_status_site CHECK (status_site BETWEEN 1 AND 2),
          visualizada_em              timestamptz,
          status_email                smallint NOT NULL
                                      CONSTRAINT ck_notificacoes_status_email CHECK (status_email BETWEEN 1 AND 4),
          email_destino               varchar(254),
          email_tentativas            smallint NOT NULL DEFAULT 0
                                      CONSTRAINT ck_notificacoes_email_tentativas
                                      CHECK (email_tentativas BETWEEN 0 AND 3),
          email_proxima_tentativa_em  timestamptz,
          email_enviado_em            timestamptz,
          email_erro                  varchar(300),
          status_whatsapp             smallint NOT NULL
                                      CONSTRAINT ck_notificacoes_status_whatsapp
                                      CHECK (status_whatsapp BETWEEN 1 AND 4),
          whatsapp_erro               varchar(300),
          lembrete_inicio             timestamptz,
          {CONTROLE_LOJA},
          CONSTRAINT ck_notificacoes_destinatario CHECK (
            (tipo = 'cliente' AND cliente_id IS NOT NULL AND funcionario_id IS NULL)
            OR (tipo = 'loja' AND funcionario_id IS NOT NULL AND cliente_id IS NULL)),
          CONSTRAINT ck_notificacoes_evento CHECK (
            (tipo = 'cliente' AND evento IN ({_lista(EVENTOS_CLIENTE)}))
            OR (tipo = 'loja' AND evento IN ({_lista(EVENTOS_LOJA)}))),
          CONSTRAINT ck_notificacoes_visualizada CHECK ((status_site = 2) = (visualizada_em IS NOT NULL)),
          CONSTRAINT ck_notificacoes_lembrete CHECK (
            (evento = 'lembrete') = (lembrete_inicio IS NOT NULL)
            AND (lembrete_inicio IS NULL OR agendamento_id IS NOT NULL)),
          CONSTRAINT ck_notificacoes_email_destino CHECK (
            (status_email = 4 AND email_destino IS NULL)
            OR (status_email IN (1, 2) AND email_destino IS NOT NULL)
            OR status_email = 3),
          CONSTRAINT ck_notificacoes_email_enviado CHECK ((status_email = 2) = (email_enviado_em IS NOT NULL)),
          CONSTRAINT notificacoes_cliente_fk FOREIGN KEY (loja_id, cliente_id) REFERENCES clientes (loja_id, id),
          CONSTRAINT notificacoes_funcionario_fk
            FOREIGN KEY (loja_id, funcionario_id) REFERENCES funcionarios (loja_id, id),
          CONSTRAINT notificacoes_agendamento_fk
            FOREIGN KEY (loja_id, agendamento_id) REFERENCES agendamentos (loja_id, id)
        );
        -- Sino do painel (as do funcionário) e do site (as dos clientes do telefone), mais novas primeiro
        CREATE INDEX notificacoes_funcionario_idx ON notificacoes (loja_id, funcionario_id, criado_em DESC)
          WHERE tipo = 'loja' AND excluido_em IS NULL;
        CREATE INDEX notificacoes_cliente_idx ON notificacoes (loja_id, cliente_id, criado_em DESC)
          WHERE tipo = 'cliente' AND excluido_em IS NULL;
        -- Fila de e-mails (tarefa de fundo, NOT-07)
        CREATE INDEX notificacoes_fila_email_idx ON notificacoes (email_proxima_tentativa_em)
          WHERE status_email = 1 AND excluido_em IS NULL;
        -- Um lembrete por agendamento e início lembrado (NOT-05)
        CREATE UNIQUE INDEX notificacoes_lembrete_uk ON notificacoes (loja_id, agendamento_id, lembrete_inicio)
          WHERE evento = 'lembrete' AND excluido_em IS NULL;
        -- Agendamentos que podem receber lembrete, de todas as lojas (tarefa de fundo)
        CREATE INDEX agendamentos_lembrete_idx ON agendamentos (inicio)
          WHERE status IN ('agendado', 'confirmado') AND excluido_em IS NULL;

        -- NOT-04: o status de um canal só avança (2, 3 e 4 são finais; visualizada não volta)
        CREATE FUNCTION notificacoes_status_avanca() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF (OLD.status_email <> 1 AND NEW.status_email IS DISTINCT FROM OLD.status_email)
             OR (OLD.status_whatsapp <> 1 AND NEW.status_whatsapp IS DISTINCT FROM OLD.status_whatsapp)
             OR (OLD.status_site = 2 AND NEW.status_site IS DISTINCT FROM OLD.status_site) THEN
            RAISE EXCEPTION 'O status de envio de uma notificação não volta atrás.'
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER notificacoes_status_avanca BEFORE UPDATE ON notificacoes
          FOR EACH ROW EXECUTE FUNCTION notificacoes_status_avanca();
    """)
    tabela_loja('notificacoes')
    fks_controle_loja('notificacoes')

    op.execute("""
        ALTER TABLE loja_configuracoes
          ADD COLUMN antecedencia_cliente_minutos integer NOT NULL DEFAULT 120
            CONSTRAINT ck_loja_configuracoes_antecedencia CHECK (antecedencia_cliente_minutos BETWEEN 0 AND 10080),
          ADD COLUMN smtp_ativo boolean NOT NULL DEFAULT false,
          ADD COLUMN smtp_servidor varchar(255),
          ADD COLUMN smtp_porta integer
            CONSTRAINT ck_loja_configuracoes_smtp_porta CHECK (smtp_porta IN (25, 465, 587, 2525)),
          ADD COLUMN smtp_seguranca varchar(10)
            CONSTRAINT ck_loja_configuracoes_smtp_seguranca CHECK (smtp_seguranca IN ('ssl', 'starttls')),
          ADD COLUMN smtp_usuario varchar(255),
          ADD COLUMN smtp_senha_cifrada text,
          ADD COLUMN smtp_remetente_email varchar(254),
          ADD COLUMN smtp_remetente_nome varchar(120),
          ADD CONSTRAINT ck_loja_configuracoes_smtp_ativo CHECK (
            NOT smtp_ativo OR (smtp_servidor IS NOT NULL AND smtp_porta IS NOT NULL
                               AND smtp_seguranca IS NOT NULL AND smtp_remetente_email IS NOT NULL));

        -- Lojas ativas com e-mail pendente vencido ou agendamento na janela do lembrete sem lembrete
        -- (NOT-05, NOT-07). Só devolve ids: a tarefa trabalha cada loja com o contexto (e o RLS) dela.
        CREATE FUNCTION notificacoes_lojas_com_trabalho(agora timestamptz) RETURNS SETOF uuid
          LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
          SELECT l.id
            FROM lojas l
           WHERE l.status = 'ativa' AND l.excluido_em IS NULL
             AND l.id IN (
               SELECT n.loja_id FROM notificacoes n
                WHERE n.status_email = 1 AND n.excluido_em IS NULL
                  AND n.email_proxima_tentativa_em <= agora
               UNION
               SELECT a.loja_id
                 FROM agendamentos a
                 LEFT JOIN loja_configuracoes c ON c.loja_id = a.loja_id AND c.excluido_em IS NULL
                WHERE a.status IN ('agendado', 'confirmado') AND a.excluido_em IS NULL
                  AND a.inicio > agora AND a.inicio <= agora + interval '7 days'
                  AND a.inicio <= agora + make_interval(mins => coalesce(c.antecedencia_cliente_minutos, 120))
                  AND NOT EXISTS (
                    SELECT 1 FROM notificacoes n
                     WHERE n.loja_id = a.loja_id AND n.agendamento_id = a.id AND n.evento = 'lembrete'
                       AND n.lembrete_inicio = a.inicio AND n.excluido_em IS NULL))
        $$;
    """)
    _so_a_aplicacao_executa()
    op.execute(_0007._auditoria(MASCARA_0008))


def _so_a_aplicacao_executa() -> None:
    """A função SECURITY DEFINER passa por cima do RLS: só o papel da aplicação a executa (não PUBLIC)."""
    op.execute('REVOKE ALL ON FUNCTION notificacoes_lojas_com_trabalho(timestamptz) FROM PUBLIC')
    papel = get_settings().papel_app
    existe = op.get_bind().execute(text('SELECT 1 FROM pg_roles WHERE rolname = :p'), {'p': papel}).scalar()
    if existe:  # o nome vem da configuração (DATABASE_URL), não do usuário final
        op.execute(f'GRANT EXECUTE ON FUNCTION notificacoes_lojas_com_trabalho(timestamptz) TO "{papel}"')


def downgrade() -> None:
    op.execute(_0007._auditoria(_0007.MASCARA_0007))
    op.execute("""
        DROP FUNCTION notificacoes_lojas_com_trabalho(timestamptz);
        ALTER TABLE loja_configuracoes
          DROP CONSTRAINT ck_loja_configuracoes_smtp_ativo,
          DROP COLUMN antecedencia_cliente_minutos,
          DROP COLUMN smtp_ativo,
          DROP COLUMN smtp_servidor,
          DROP COLUMN smtp_porta,
          DROP COLUMN smtp_seguranca,
          DROP COLUMN smtp_usuario,
          DROP COLUMN smtp_senha_cifrada,
          DROP COLUMN smtp_remetente_email,
          DROP COLUMN smtp_remetente_nome;
        DROP INDEX agendamentos_lembrete_idx;
        DROP TABLE notificacoes;
        DROP FUNCTION notificacoes_status_avanca();
    """)
