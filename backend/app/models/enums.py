"""Enums do banco (estrutura.md, seção 3). Os valores são os mesmos do Postgres."""

from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class StatusLoja(StrEnum):
    ativa = 'ativa'
    suspensa = 'suspensa'
    cancelada = 'cancelada'


class StatusAgendamento(StrEnum):
    pendente = 'pendente'
    agendado = 'agendado'
    confirmado = 'confirmado'
    concluido = 'concluido'
    cancelado = 'cancelado'
    nao_compareceu = 'nao_compareceu'


class FormaPagamento(StrEnum):
    credito = 'credito'
    debito = 'debito'
    dinheiro = 'dinheiro'
    pix = 'pix'


class OrigemAgendamento(StrEnum):
    painel = 'painel'
    site = 'site'


class CanalCliente(StrEnum):
    loja = 'loja'
    whatsapp = 'whatsapp'
    site = 'site'


class TipoMovimentacao(StrEnum):
    entrada = 'entrada'
    saida_atendimento = 'saida_atendimento'
    ajuste = 'ajuste'
    perda = 'perda'


class OrigemPonto(StrEnum):
    sistema = 'sistema'
    manual = 'manual'


class NivelAcesso(StrEnum):
    nenhum = 'nenhum'
    leitura = 'leitura'
    escrita = 'escrita'


class TipoLocal(StrEnum):
    presencial = 'presencial'
    online = 'online'


class TipoLoja(StrEnum):
    clinica = 'clinica'
    barbearia = 'barbearia'
    escola = 'escola'


class OperacaoAuditoria(StrEnum):
    inserir = 'inserir'
    alterar = 'alterar'
    excluir = 'excluir'
    restaurar = 'restaurar'


class OrigemAuditoria(StrEnum):
    painel = 'painel'
    superadmin = 'superadmin'
    site = 'site'
    sistema = 'sistema'


def pg_enum(classe: type[StrEnum], nome: str) -> ENUM:
    """Tipo enum do Postgres já criado pela migração."""
    return ENUM(classe, name=nome, create_type=False, values_callable=lambda e: [m.value for m in e])
