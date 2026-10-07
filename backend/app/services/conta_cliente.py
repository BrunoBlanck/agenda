"""Conta do cliente no site (SIT-16 a SIT-21) e a parte dela que o painel vê (CLI-06).

- **Conta por telefone** (SIT-16): uma por (loja, telefone só com dígitos). Não pertence a um registro de
  cliente: enxerga os agendamentos de todos os clientes da loja com aquele telefone, comparando os
  dígitos na hora (se a loja trocar o telefone de um cliente, os agendamentos dele mudam de conta).
- **Código de confirmação** (SIT-17): 6 dígitos, vale ``VALIDADE_CODIGO``, até ``TENTATIVAS_MAXIMAS``
  erradas no total (e 5 por IP, ``app/limites.py::TentativasDoCodigo``). Pedir código com um pendente
  válido devolve o mesmo (um terceiro não invalida o código de quem já o tem); só sem pendente um novo é
  gerado (e os anteriores, invalidados). O envio passa por um provedor trocável (``EnvioCodigo``); o
  atual, "painel", só grava o código e a loja o vê no painel. Limites de pedidos em ``app/limites.py``.
- **Ordem das travas** (sem deadlock): sempre o telefone primeiro (advisory lock, ``travar_telefone``) e
  só depois as linhas do código e da conta (``FOR UPDATE``). Quem parte de um ``t``/``v`` lê o código sem
  travar, trava o telefone e relê o código travado (``travar_codigo``). O Argon2 é calculado antes.
- **Criar conta e esqueci a senha** (SIT-18): o mesmo caminho telefone → código → senha. Os passos levam
  identificadores assinados (``app/services/assinatura.py``) com o id do código, nunca o telefone.
- **Senha** (SIT-19): 8 a 128 caracteres, diferente do telefone, Argon2.
- **Sessão** (SIT-20): token ``cliente`` (``app/auth/tokens.py``) com a versão da conta; trocar a senha
  ou a loja remover o acesso incrementa ``sessao_versao`` e derruba todas as sessões.
- **Meus agendamentos** (SIT-21): próximos e histórico, com ``alteravel`` (cancelar/remarcar, SIT-23/24,
  em ``app/services/conta_agendamentos.py``).

Contexto da transação: as páginas do site gravam ``app.origem = 'site'`` e a loja (RLS); o painel,
``painel`` e o funcionário. Os triggers cuidam das colunas de controle e da auditoria (que mascara
``senha_hash`` e ``codigo``).
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy import ColumnElement, Row, Select, and_, func, not_, select, update
from sqlalchemy.orm import Session

from app.auth.tokens import DadosTokenCliente
from app.db import definir_contexto
from app.models import Agendamento, Cliente, ClienteCodigo, ClienteConta, Funcionario, Local, Servico
from app.models.enums import CanalCliente, StatusAgendamento
from app.schemas.comum import formatar_telefone, so_digitos
from app.services.agendamento_site import NOME_SEM_SERVICO, cliente_do_telefone, filtro_telefone
from app.services.assinatura import assinar_id, ler_id

VALIDADE_CODIGO = timedelta(minutes=15)
TENTATIVAS_MAXIMAS = 20  # erros no total por código, igual ao CHECK de cliente_codigos.tentativas
VALIDADE_PASSO = timedelta(minutes=15)  # identificadores dos passos "código" e "senha"
DOMINIO_TELEFONE = 'conta-telefone'
DOMINIO_VERIFICADO = 'conta-verificado'

SENHA_MINIMA, SENHA_MAXIMA = 8, 128

SITUACOES_ATIVAS = (StatusAgendamento.pendente, StatusAgendamento.agendado, StatusAgendamento.confirmado)
PROXIMOS_MAXIMO = 50
HISTORICO_POR_PAGINA = 20
PAGINA_MAXIMA = 10_000

MSG_SENHA_TAMANHO = f'A senha precisa ter de {SENHA_MINIMA} a {SENHA_MAXIMA} caracteres.'
MSG_SENHA_TELEFONE = 'A senha não pode ser o seu telefone.'
MSG_SENHA_DIFERENTE = 'As senhas não são iguais.'


# --- Provedor de envio do código (trocável) ---------------------------------------------------------


class EnvioCodigo(Protocol):
    """Como o código chega ao cliente. Um provedor de SMS/WhatsApp entra aqui (ABE-12).

    ``enviar`` roda dentro da transação da página: um provedor externo deve enfileirar o envio, não
    esperar a rede com a transação aberta (PER-05).
    """

    nome: str

    def enviar(self, loja_id: UUID, telefone_digitos: str, codigo: str) -> None: ...

    def instrucao(self, nome_da_loja: str) -> str: ...


class EnvioPeloPainel:
    """Provisório: o código só fica gravado e a loja o vê no painel (Clientes), que o repassa ao cliente."""

    nome = 'painel'

    def enviar(self, loja_id: UUID, telefone_digitos: str, codigo: str) -> None:
        return None

    def instrucao(self, nome_da_loja: str) -> str:
        return f'Por enquanto, peça o código à {nome_da_loja} pelo telefone ou WhatsApp.'


PROVEDORES: dict[str, EnvioCodigo] = {'painel': EnvioPeloPainel()}


def provedor_de_codigo() -> EnvioCodigo:
    return PROVEDORES['painel']


# --- Telefone e senha ------------------------------------------------------------------------------


def ler_telefone(texto: str | None) -> str | None:
    """Dígitos de um telefone com DDD (10 ou 11, sem começar com 0), com ou sem máscara; senão None."""
    digitos = so_digitos(texto or '')
    if len(digitos) not in (10, 11) or digitos[0] == '0' or len(texto or '') > 30:
        return None
    return digitos


def erros_da_senha(senha: str, repetir: str, telefone_digitos: str) -> dict[str, str]:
    """Regras da SIT-19 (mensagens ao lado de cada campo)."""
    if not SENHA_MINIMA <= len(senha) <= SENHA_MAXIMA:
        return {'senha': MSG_SENHA_TAMANHO}
    sem_letras = not any(c.isalpha() for c in senha)
    if sem_letras and so_digitos(senha) in (telefone_digitos, telefone_digitos[2:]):
        return {'senha': MSG_SENHA_TELEFONE}
    if senha != repetir:
        return {'repetir': MSG_SENHA_DIFERENTE}
    return {}


def travar_telefone(db: Session, loja_id: UUID, digitos: str) -> None:
    """Serializa, na transação, o que muda códigos e conta de um telefone (advisory lock).

    É sempre a primeira trava (antes de ``FOR UPDATE`` em códigos e contas do telefone).
    """
    db.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(f'conta-cliente:{loja_id}:{digitos}', 0)))
    )


# --- Código de confirmação (SIT-17) ----------------------------------------------------------------


def _pendente() -> list[ColumnElement[bool]]:
    """Condições de um código pendente (não usado, não invalidado, na validade, tentativas < máximo)."""
    return [
        ClienteCodigo.usado_em.is_(None),
        ClienteCodigo.invalidado_em.is_(None),
        ClienteCodigo.expira_em > func.now(),
        ClienteCodigo.tentativas < TENTATIVAS_MAXIMAS,
    ]


def _invalidar_codigos(db: Session, loja_id: UUID, digitos: str) -> None:
    """Todos os códigos ainda não invalidados do telefone (pendentes e confirmados sem senha definida)."""
    db.execute(
        update(ClienteCodigo)
        .where(
            ClienteCodigo.loja_id == loja_id,
            ClienteCodigo.telefone_digitos == digitos,
            ClienteCodigo.invalidado_em.is_(None),
            ClienteCodigo.excluido_em.is_(None),
        )
        .values(invalidado_em=func.now())
        .execution_options(synchronize_session=False)
    )


def obter_codigo(
    db: Session, loja_id: UUID, digitos: str, antes_de_gerar: Callable[[], None]
) -> ClienteCodigo:
    """O código pendente do telefone ou, sem nenhum, um novo (os anteriores são invalidados) enviado
    pelo provedor atual. ``antes_de_gerar`` confere o limite de códigos gerados (pode levantar 429).

    Responde igual exista ou não cliente/conta com o telefone (SIT-07): quem pede não fica sabendo. Um
    terceiro que pede código para o telefone de outra pessoa não invalida o que ela já tem (SIT-17).
    """
    travar_telefone(db, loja_id, digitos)
    pendente = codigo_pendente(db, loja_id, digitos)
    if pendente is not None:
        return pendente
    antes_de_gerar()
    _invalidar_codigos(db, loja_id, digitos)
    provedor = provedor_de_codigo()
    codigo = ClienteCodigo(
        loja_id=loja_id,
        telefone_digitos=digitos,
        codigo=f'{secrets.randbelow(1_000_000):06d}',
        expira_em=func.now() + VALIDADE_CODIGO,
        provedor=provedor.nome,
    )
    db.add(codigo)
    db.flush()
    provedor.enviar(loja_id, digitos, codigo.codigo)
    return codigo


def passo_do_codigo(loja_id: UUID, codigo_id: UUID) -> str:
    """Identificador do passo "digite o código" (parâmetro ``t``)."""
    return assinar_id(DOMINIO_TELEFONE, loja_id, codigo_id, VALIDADE_PASSO)


def passo_da_senha(loja_id: UUID, codigo_id: UUID) -> str:
    """Identificador do passo "nova senha" (parâmetro ``v``): telefone confirmado por aquele código."""
    return assinar_id(DOMINIO_VERIFICADO, loja_id, codigo_id, VALIDADE_PASSO)


def _codigo_do_passo(db: Session, loja_id: UUID, texto: str | None, dominio: str) -> ClienteCodigo | None:
    lido = ler_id(texto or '', loja_id, (dominio,))
    if lido is None:
        return None
    return db.scalar(
        select(ClienteCodigo).where(ClienteCodigo.id == lido[0], ClienteCodigo.loja_id == loja_id)
    )


def codigo_do_passo(db: Session, loja_id: UUID, texto: str | None) -> ClienteCodigo | None:
    """Código do parâmetro ``t`` (assinatura, loja e validade conferidas), sem travar, ou None."""
    return _codigo_do_passo(db, loja_id, texto, DOMINIO_TELEFONE)


def travar_codigo(db: Session, codigo: ClienteCodigo) -> ClienteCodigo:
    """Trava o telefone e depois a linha do código (relida: outra transação pode tê-la mudado)."""
    travar_telefone(db, codigo.loja_id, codigo.telefone_digitos)
    return db.scalars(
        select(ClienteCodigo)
        .where(ClienteCodigo.id == codigo.id, ClienteCodigo.loja_id == codigo.loja_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()  # códigos não são excluídos


def codigo_aberto(codigo: ClienteCodigo) -> bool:
    """O código ainda aceita tentativas (pendente)."""
    return (
        codigo.usado_em is None
        and codigo.invalidado_em is None
        and codigo.tentativas < TENTATIVAS_MAXIMAS
        and codigo.expira_em > datetime.now(UTC)
    )


class Conferencia(StrEnum):
    certo = 'certo'
    errado = 'errado'
    vencido = 'vencido'  # vencido, usado, invalidado ou sem tentativas


def conferir_codigo(db: Session, codigo: ClienteCodigo, digitado: str) -> Conferencia:
    """Confere o código digitado (o chamador já travou a linha). Errar soma uma tentativa."""
    if not codigo_aberto(codigo):
        return Conferencia.vencido
    if secrets.compare_digest(codigo.codigo.encode(), digitado.encode()):
        codigo.usado_em = func.now()
        db.flush()
        return Conferencia.certo
    codigo.tentativas += 1
    db.flush()
    return Conferencia.errado if codigo.tentativas < TENTATIVAS_MAXIMAS else Conferencia.vencido


def confirmado(codigo: ClienteCodigo | None) -> bool:
    """Código usado (telefone confirmado) e ainda não consumido nem invalidado."""
    return codigo is not None and codigo.usado_em is not None and codigo.invalidado_em is None


def codigo_confirmado(db: Session, loja_id: UUID, texto: str | None) -> ClienteCodigo | None:
    """Código do parâmetro ``v`` (sem travar), se ainda confirma o telefone; senão None."""
    codigo = _codigo_do_passo(db, loja_id, texto, DOMINIO_VERIFICADO)
    return codigo if confirmado(codigo) else None


# --- Conta e senha (SIT-18, SIT-19) ----------------------------------------------------------------


def conta_do_telefone(
    db: Session, loja_id: UUID, digitos: str, *, travar: bool = False
) -> ClienteConta | None:
    consulta = select(ClienteConta).where(
        ClienteConta.loja_id == loja_id, ClienteConta.telefone_digitos == digitos
    )
    if travar:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    return db.scalar(consulta)


def definir_senha(
    db: Session,
    loja_id: UUID,
    codigo: ClienteCodigo,
    senha_hash: str,
    nome: str | None = None,
    sobrenome: str | None = None,
) -> ClienteConta:
    """Cria a conta do telefone confirmado ou troca a senha dela (versão +1: derruba as outras sessões).

    O chamador já travou o telefone e o código (``travar_codigo``) e conferiu que ele ainda confirma o
    telefone; ``senha_hash`` vem pronto (o Argon2 é lento: calcule antes das travas). Sem nenhum cliente
    com o telefone, cadastra um (canal ``site``) com ``nome``/``sobrenome``; cliente já cadastrado não
    muda (SIT-07). O código é consumido (o mesmo passo não serve duas vezes).
    """
    digitos = codigo.telefone_digitos
    travar_telefone(db, loja_id, digitos)  # já travado pelo chamador (a trava é reentrante)
    if cliente_do_telefone(db, loja_id, digitos) is None:
        if not nome or not sobrenome:
            raise ValueError('Telefone sem cliente: nome e sobrenome são obrigatórios.')
        db.add(
            Cliente(
                loja_id=loja_id,
                nome=nome,
                sobrenome=sobrenome,
                telefone=formatar_telefone(digitos),
                canais=[CanalCliente.site],
            )
        )
    conta = conta_do_telefone(db, loja_id, digitos, travar=True)
    if conta is None:
        conta = ClienteConta(loja_id=loja_id, telefone_digitos=digitos, senha_hash=senha_hash)
        db.add(conta)
    else:
        conta.senha_hash = senha_hash
        conta.sessao_versao += 1
    conta.ultimo_acesso_em = func.now()
    codigo.invalidado_em = func.now()
    db.flush()
    db.refresh(conta, ['sessao_versao', 'ultimo_acesso_em'])
    return conta


def registrar_acesso(
    db: Session, loja_id: UUID, conta: ClienteConta, novo_hash: str | None, ip: str | None
) -> None:
    """Entrou com a senha: grava o último acesso (fora do histórico, como o login do painel)."""
    definir_contexto(db, origem='site', loja_id=loja_id, ip=ip, login=True)
    conta.ultimo_acesso_em = func.now()
    if novo_hash:
        conta.senha_hash = novo_hash
    db.flush()


# --- Sessão (SIT-20) -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SessaoCliente:
    conta: ClienteConta
    cliente: Cliente | None  # o mais antigo com o telefone (None: a loja trocou ou não há cadastro)

    @property
    def nome(self) -> str | None:
        return self.cliente.nome if self.cliente else None

    @property
    def telefone(self) -> str:
        return formatar_telefone(self.conta.telefone_digitos)


def sessao_valida(db: Session, loja_id: UUID, dados: DadosTokenCliente) -> SessaoCliente | None:
    """A sessão do token vale: mesma loja, conta não removida e mesma versão."""
    if dados.loja_id != loja_id:
        return None
    conta = db.scalar(
        select(ClienteConta).where(ClienteConta.id == dados.conta_id, ClienteConta.loja_id == loja_id)
    )
    if conta is None or conta.sessao_versao != dados.versao:
        return None
    return SessaoCliente(conta=conta, cliente=cliente_do_telefone(db, loja_id, conta.telefone_digitos))


# --- Meus agendamentos (SIT-21) --------------------------------------------------------------------


@dataclass(frozen=True)
class MeuAgendamento:
    id: UUID
    inicio: datetime
    fim: datetime
    status: StatusAgendamento
    preco: Decimal | None
    servico_nome: str
    funcionario_nome: str
    local_nome: str | None
    alteravel: bool  # pode cancelar/remarcar pelo site (situação ativa e prazo da loja, CFG-05)
    servico_id: UUID | None
    funcionario_id: UUID


@dataclass(frozen=True)
class MeusAgendamentos:
    proximos: list[MeuAgendamento]
    historico: list[MeuAgendamento]
    total_historico: int
    pagina: int
    por_pagina: int = HISTORICO_POR_PAGINA


def pode_alterar(
    status: StatusAgendamento, inicio: datetime, antecedencia: timedelta, agora: datetime | None = None
) -> bool:
    """SIT-23/24: situação ativa e pelo menos ``antecedencia`` (a da loja, CFG-05) antes do início."""
    return status in SITUACOES_ATIVAS and inicio - (agora or datetime.now(UTC)) >= antecedencia


def _da_conta(loja_id: UUID, digitos: str) -> Select:
    """Agendamentos (não excluídos) de todos os clientes da loja com o telefone, com os nomes do histórico."""
    return (
        select(
            Agendamento.id,
            Agendamento.inicio,
            Agendamento.fim,
            Agendamento.status,
            Agendamento.preco,
            Servico.nome,
            Funcionario.nome,
            Local.nome,
            Agendamento.servico_id,
            Agendamento.funcionario_id,
        )
        .join(Cliente, (Cliente.id == Agendamento.cliente_id) & (Cliente.loja_id == Agendamento.loja_id))
        .join(
            Funcionario,
            (Funcionario.id == Agendamento.funcionario_id) & (Funcionario.loja_id == Agendamento.loja_id),
        )
        .outerjoin(Servico, (Servico.id == Agendamento.servico_id) & (Servico.loja_id == Agendamento.loja_id))
        .outerjoin(Local, (Local.id == Agendamento.local_id) & (Local.loja_id == Agendamento.loja_id))
        .where(
            Agendamento.loja_id == loja_id,
            Agendamento.excluido_em.is_(None),
            Cliente.excluido_em.is_(None),
            filtro_telefone(loja_id, digitos),
        )
        .execution_options(incluir_excluidos=True)  # serviço, profissional e local excluídos mantêm o nome
    )


def _proximo() -> ColumnElement[bool]:
    return and_(Agendamento.status.in_(SITUACOES_ATIVAS), Agendamento.fim >= func.now())


def _item(linha: Row, agora: datetime, antecedencia: timedelta) -> MeuAgendamento:
    (
        id_,
        inicio,
        fim,
        situacao,
        preco,
        servico_nome,
        funcionario_nome,
        local_nome,
        servico_id,
        funcionario_id,
    ) = linha
    return MeuAgendamento(
        id=id_,
        inicio=inicio,
        fim=fim,
        status=situacao,
        preco=preco,
        servico_nome=servico_nome or NOME_SEM_SERVICO,
        funcionario_nome=funcionario_nome,
        local_nome=local_nome,
        alteravel=pode_alterar(situacao, inicio, antecedencia, agora),
        servico_id=servico_id,
        funcionario_id=funcionario_id,
    )


def meus_agendamentos(
    db: Session, loja_id: UUID, digitos: str, pagina: int, antecedencia: timedelta
) -> MeusAgendamentos:
    """Próximos (início crescente, até 50) e uma página do histórico (início decrescente).

    ``antecedencia``: prazo da loja para cancelar/remarcar pelo site (CFG-05).
    """
    agora = datetime.now(UTC)
    base = _da_conta(loja_id, digitos)
    proximos = db.execute(
        base.where(_proximo()).order_by(Agendamento.inicio, Agendamento.id).limit(PROXIMOS_MAXIMO)
    ).all()
    passados = base.where(not_(_proximo()))
    total = db.scalar(select(func.count()).select_from(passados.order_by(None).subquery())) or 0
    historico = db.execute(
        passados.order_by(Agendamento.inicio.desc(), Agendamento.id)
        .offset((pagina - 1) * HISTORICO_POR_PAGINA)
        .limit(HISTORICO_POR_PAGINA)
    ).all()
    return MeusAgendamentos(
        proximos=[_item(linha, agora, antecedencia) for linha in proximos],
        historico=[_item(linha, agora, antecedencia) for linha in historico],
        total_historico=total,
        pagina=pagina,
    )


def meu_agendamento(
    db: Session, loja_id: UUID, digitos: str, agendamento_id: UUID, antecedencia: timedelta
) -> MeuAgendamento | None:
    """Um agendamento da conta (mesma loja, cliente com o telefone, não excluído), ou None (página 404)."""
    linha = db.execute(_da_conta(loja_id, digitos).where(Agendamento.id == agendamento_id)).one_or_none()
    return _item(linha, datetime.now(UTC), antecedencia) if linha is not None else None


# --- Painel: códigos e acesso ao site (CLI-06) -----------------------------------------------------


def codigos_pendentes(
    db: Session, loja_id: UUID, limite: int = 100
) -> list[tuple[ClienteCodigo, list[Cliente]]]:
    """Códigos pendentes da loja (mais novo primeiro) com os clientes de cada telefone (uma consulta)."""
    codigos = list(
        db.scalars(
            select(ClienteCodigo)
            .where(ClienteCodigo.loja_id == loja_id, *_pendente())
            .order_by(ClienteCodigo.criado_em.desc(), ClienteCodigo.id)
            .limit(limite)
        )
    )
    telefones = {c.telefone_digitos for c in codigos}
    por_telefone: dict[str, list[Cliente]] = {t: [] for t in telefones}
    if telefones:
        digitos = func.regexp_replace(Cliente.telefone, r'\D', '', 'g')
        for cliente, chave in db.execute(
            select(Cliente, digitos)
            .where(Cliente.loja_id == loja_id, digitos.in_(telefones))
            .order_by(Cliente.criado_em, Cliente.id)
        ):
            por_telefone[chave].append(cliente)
    return [(c, por_telefone[c.telefone_digitos]) for c in codigos]


def codigo_pendente(db: Session, loja_id: UUID, digitos: str) -> ClienteCodigo | None:
    """O código pendente mais novo do telefone."""
    return db.scalar(
        select(ClienteCodigo)
        .where(ClienteCodigo.loja_id == loja_id, ClienteCodigo.telefone_digitos == digitos, *_pendente())
        .order_by(ClienteCodigo.criado_em.desc(), ClienteCodigo.id)
        .limit(1)
    )


def remover_acesso(db: Session, loja_id: UUID, digitos: str) -> bool:
    """Remove a conta do telefone (exclusão lógica + versão +1, SIT-20) e invalida os códigos dele.

    False se o telefone não tem conta.
    """
    travar_telefone(db, loja_id, digitos)
    conta = conta_do_telefone(db, loja_id, digitos, travar=True)
    if conta is None:
        return False
    conta.sessao_versao += 1
    conta.excluido_em = func.now()
    _invalidar_codigos(db, loja_id, digitos)
    db.flush()
    return True
