"""Locais de atendimento e configurações da loja (estrutura.md, 2.19 e 2.21)."""

import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ControleMixin, IdMixin, LojaMixin, gerado_pelo_banco
from app.models.enums import TipoLocal, pg_enum


class Local(IdMixin, LojaMixin, Base):
    __tablename__ = 'locais'

    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoLocal] = mapped_column(pg_enum(TipoLocal, 'tipo_local'), server_default='presencial')
    link_padrao: Mapped[str | None] = mapped_column(String(500))
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default='true')


class LojaConfiguracao(ControleMixin, Base):
    """Opções da loja que não são dados cadastrais. Uma linha por loja."""

    __tablename__ = 'loja_configuracoes'

    loja_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rotulo_local: Mapped[str] = mapped_column(String(40), server_default='Local')
    rotulo_local_plural: Mapped[str] = mapped_column(String(40), server_default='Locais')
    # Cores do site do consumidor (#rrggbb); NULL = paleta do tipo da loja (SIT-13)
    cor_site_topo: Mapped[str | None] = mapped_column(String(7))
    cor_site_destaque: Mapped[str | None] = mapped_column(String(7))
    # CFG-05: lembrete ao cliente e prazo para cancelar/remarcar pelo site, em minutos
    antecedencia_cliente_minutos: Mapped[int] = mapped_column(Integer, server_default='120')
    # CFG-06: SMTP da loja (a senha é cifrada com CHAVE_CIFRA e nunca sai pela API nem pela auditoria)
    smtp_ativo: Mapped[bool] = mapped_column(Boolean, server_default='false')
    smtp_servidor: Mapped[str | None] = mapped_column(String(255))
    smtp_porta: Mapped[int | None] = mapped_column(Integer)
    smtp_seguranca: Mapped[str | None] = mapped_column(String(10))
    smtp_usuario: Mapped[str | None] = mapped_column(String(255))
    smtp_senha_cifrada: Mapped[str | None] = mapped_column(Text)
    smtp_remetente_email: Mapped[str | None] = mapped_column(String(254))
    smtp_remetente_nome: Mapped[str | None] = mapped_column(String(120))
    atualizado_por: Mapped[uuid.UUID | None] = gerado_pelo_banco()
