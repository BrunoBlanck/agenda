"""Consulta da auditoria para o SUPERADMIN e registro de ações sem alteração de linha (estrutura.md, 1.9).

A auditoria é preenchida pelos triggers. Aqui ela é lida (uma loja por vez, ou a "Plataforma"), com os
nomes de quem fez resolvidos e o que mudou (campo: antes → depois).
"""

import json
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, and_, select, text
from sqlalchemy.orm import Session

from app.models import Auditoria, Cliente, Funcionalidade, Loja
from app.models.enums import OperacaoAuditoria, OrigemAuditoria
from app.schemas.superadmin import FUSO_PLATAFORMA, AuditoriaItem, Mudanca, Periodo, Quem
from app.services.comum import intervalo_de_dias, invalido, nomes_funcionarios
from app.services.plataforma import nomes_superadmins

PLATAFORMA = 'plataforma'

# Tabelas que podem ser consultadas (frontend/src/data/plataforma.js: tabelasLoja e tabelasPlataforma)
TABELAS_LOJA: dict[str, str] = {
    'agendamentos': 'Agendamentos',
    'clientes': 'Clientes',
    'funcionarios': 'Funcionários',
    'cargos': 'Cargos',
    'servicos': 'Serviços',
    'servico_funcionarios': 'Profissionais dos serviços',
    'servico_locais': 'Locais dos serviços',
    'servico_materiais': 'Materiais dos serviços',
    'materiais': 'Materiais',
    'categorias_material': 'Categorias de material',
    'movimentacoes_estoque': 'Movimentações de estoque',
    'agendamento_materiais': 'Materiais dos agendamentos',
    'locais': 'Locais',
    'registros_ponto': 'Controle de tempo',
    'perfis': 'Perfis de acesso',
    'perfil_acessos': 'Níveis dos perfis',
    'perfil_horarios': 'Jornadas dos perfis',
    'bloqueios_agenda': 'Bloqueios da agenda',
    'lojas': 'Dados da loja',
    'loja_funcionalidades': 'Módulos da loja',
    'loja_configuracoes': 'Configurações da loja',
}
TABELAS_PLATAFORMA: dict[str, str] = {
    'planos': 'Planos',
    'superadmin_usuarios': 'Usuários admin',
}

# Colunas de controle: não aparecem em "o que mudou"
CONTROLE = {
    'criado_em',
    'atualizado_em',
    'atualizado_por',
    'atualizado_por_funcionario',
    'atualizado_por_superadmin',
}
SENHA_OCULTA = '••••••'
DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']


def nome_tabela(tabela: str) -> str:
    return TABELAS_LOJA.get(tabela) or TABELAS_PLATAFORMA.get(tabela) or tabela


# --- Registro de ações sem alteração de linha ----------------------------------------------------


def registrar_acao(
    db: Session,
    *,
    loja_id: UUID | None,
    tabela: str,
    registro_id: str,
    depois: dict[str, Any],
    antes: dict[str, Any] | None = None,
    campos: Sequence[str] | None = None,
) -> None:
    """Grava na auditoria uma ação que não altera nenhuma linha (ex.: enviar link de nova senha).

    Entra como "alterar", com o detalhe em ``depois`` (estrutura.md, 1.9). Quem fez, a origem e o IP vêm
    do contexto da transação, como nos triggers. Nunca passe senha, token ou dado pessoal no detalhe.
    ``campos`` são os que o histórico mostra (padrão: todos de ``depois``); um campo só de rótulo, como
    ``nome``, fica fora para não parecer alterado.
    """
    db.execute(
        text(
            'INSERT INTO auditoria (loja_id, tabela, registro_id, operacao, antes, depois, campos_alterados,'
            ' funcionario_id, superadmin_id, origem, ip) VALUES ('
            ' :loja_id, :tabela, :registro_id, :operacao, CAST(:antes AS jsonb), CAST(:depois AS jsonb),'
            " :campos, contexto_uuid('app.funcionario_id'), contexto_uuid('app.superadmin_id'),"
            " coalesce(nullif(current_setting('app.origem', true), ''), 'sistema')::origem_auditoria,"
            " nullif(current_setting('app.ip', true), '')::inet)"
        ),
        {
            'loja_id': loja_id,
            'tabela': tabela,
            'registro_id': registro_id,
            'operacao': OperacaoAuditoria.alterar.value,
            'antes': json.dumps(antes) if antes is not None else None,
            'depois': json.dumps(depois),
            'campos': sorted(depois if campos is None else campos),
        },
    )


# --- Filtros -------------------------------------------------------------------------------------


def interpretar_loja(valor: str) -> UUID | None:
    """'plataforma' (tabelas sem loja) ou o id da loja."""
    if valor == PLATAFORMA:
        return None
    try:
        return UUID(valor)
    except ValueError:
        raise invalido('Escolha uma loja ou "plataforma".') from None


def intervalo_do_periodo(
    periodo: Periodo, inicio: date | None, fim: date | None, zona: ZoneInfo
) -> tuple[datetime, datetime]:
    """[início, fim) do período, com os dias no fuso da loja (como os atalhos da tela)."""
    hoje = datetime.now(zona).date()
    if periodo == 'intervalo':
        if inicio is None or fim is None:
            raise invalido('Informe o início e o fim do período.')
        if fim < inicio:
            raise invalido('O fim do período deve ser depois do início.')
        return intervalo_de_dias(inicio, fim, zona)
    dias = {'hoje': 0, '7d': 6, '30d': 29, '90d': 89}
    if periodo == 'ano':
        try:
            primeiro = hoje.replace(year=hoje.year - 1)
        except ValueError:  # 29/02
            primeiro = hoje - timedelta(days=365)
    else:
        primeiro = hoje - timedelta(days=dias[periodo])
    return intervalo_de_dias(primeiro, hoje, zona)


def filtro_quem(chave: str) -> ColumnElement[bool]:
    """Chave do filtro de pessoa: f:<id> (funcionário), s:<id> (superadmin), site ou sistema."""
    if chave == 'site':
        return Auditoria.origem == OrigemAuditoria.site
    if chave == 'sistema':
        return and_(
            Auditoria.origem == OrigemAuditoria.sistema,
            Auditoria.funcionario_id.is_(None),
            Auditoria.superadmin_id.is_(None),
        )
    tipo, _, valor = chave.partition(':')
    try:
        alvo = UUID(valor)
    except ValueError:
        raise invalido('Pessoa inválida no filtro.') from None
    if tipo == 'f':
        return Auditoria.funcionario_id == alvo
    if tipo == 's':
        return Auditoria.superadmin_id == alvo
    raise invalido('Pessoa inválida no filtro.')


def consulta_base(loja_id: UUID | None, tabela: str | None, de: datetime, ate: datetime) -> Select:
    tabelas = TABELAS_LOJA if loja_id is not None else TABELAS_PLATAFORMA
    if tabela is not None and tabela not in tabelas:
        raise invalido('Tabela não disponível na auditoria desta área.')
    consulta = select(Auditoria).where(
        Auditoria.loja_id.is_(None) if loja_id is None else Auditoria.loja_id == loja_id,
        Auditoria.criado_em >= de,
        Auditoria.criado_em < ate,
    )
    if tabela is not None:
        consulta = consulta.where(Auditoria.tabela == tabela)
    return consulta


# --- Quem fez ------------------------------------------------------------------------------------


def _chave_quem(funcionario_id: UUID | None, superadmin_id: UUID | None, origem: OrigemAuditoria) -> str:
    if superadmin_id is not None:
        return f's:{superadmin_id}'
    if funcionario_id is not None:
        return f'f:{funcionario_id}'
    return 'site' if origem == OrigemAuditoria.site else 'sistema'


def descrever_quem(
    db: Session, loja_id: UUID | None, linhas: Sequence[tuple[UUID | None, UUID | None, OrigemAuditoria]]
) -> dict[str, Quem]:
    """Quem fez cada alteração, com o nome resolvido (funcionário, superadmin, cliente pelo site)."""
    funcionarios = nomes_funcionarios(db, loja_id, (f for f, _, _ in linhas)) if loja_id is not None else {}
    superadmins = nomes_superadmins(db, (s for _, s, _ in linhas))
    quem: dict[str, Quem] = {}
    for funcionario_id, superadmin_id, origem in linhas:
        chave = _chave_quem(funcionario_id, superadmin_id, origem)
        if chave in quem:
            continue
        if superadmin_id is not None:
            nome = superadmins.get(superadmin_id, 'Superadmin')
            quem[chave] = Quem(tipo='superadmin', id=superadmin_id, nome=nome, chave=chave)
        elif funcionario_id is not None:
            nome = funcionarios.get(funcionario_id, 'Funcionário')
            quem[chave] = Quem(tipo='funcionario', id=funcionario_id, nome=nome, chave=chave)
        elif origem == OrigemAuditoria.site:
            quem[chave] = Quem(tipo='site', nome='Cliente, pelo site', chave=chave)
        else:
            quem[chave] = Quem(tipo='sistema', nome='Sistema', chave=chave)
    return quem


# --- O que mudou e rótulo do registro ------------------------------------------------------------


# timestamptz gravado pelo trigger (to_jsonb): "2026-10-03T00:22:41.592358+00:00"
_MOMENTO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)$', re.ASCII)


def _no_fuso(valor: Any, zona: ZoneInfo) -> Any:
    """Data/hora com fuso (UTC no banco) passa para o fuso da loja, como o resto da API (GER-15)."""
    if not isinstance(valor, str) or not _MOMENTO.match(valor):
        return valor
    try:
        return datetime.fromisoformat(valor).astimezone(zona).isoformat(timespec='seconds')
    except ValueError:
        return valor


def _linha_no_fuso(linha: dict[str, Any] | None, zona: ZoneInfo) -> dict[str, Any] | None:
    if linha is None:
        return None
    return {campo: _no_fuso(valor, zona) for campo, valor in linha.items()}


def mudancas(registro: Auditoria, zona: ZoneInfo | None = None) -> list[Mudanca]:
    if registro.operacao != OperacaoAuditoria.alterar:
        return []
    zona = zona or ZoneInfo(FUSO_PLATAFORMA)
    antes, depois = registro.antes or {}, registro.depois or {}
    saida = []
    for campo in registro.campos_alterados or []:
        if campo in CONTROLE:
            continue
        if campo == 'senha_hash':
            saida.append(Mudanca(campo='senha', antes=SENHA_OCULTA, depois='redefinida'))
            continue
        valor_antes, valor_depois = _no_fuso(antes.get(campo), zona), _no_fuso(depois.get(campo), zona)
        saida.append(Mudanca(campo=campo, antes=valor_antes, depois=valor_depois))
    return saida


def _data_hora(valor: Any, zona: ZoneInfo) -> str | None:
    if not isinstance(valor, str):
        return None
    try:
        return datetime.fromisoformat(valor).astimezone(zona).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return None


def rotulos(db: Session, loja_id: UUID | None, registros: Sequence[Auditoria], zona: ZoneInfo) -> list[str]:
    """Descrição curta de cada registro, como a coluna "Registro" da tela."""
    linhas = [r.depois or r.antes or {} for r in registros]
    ids_clientes = {
        UUID(linha['cliente_id'])
        for r, linha in zip(registros, linhas, strict=True)
        if r.tabela == 'agendamentos' and linha.get('cliente_id')
    }
    clientes: dict[UUID, str] = {}
    if ids_clientes and loja_id is not None:
        clientes = {
            i: f'{n} {s}'
            for i, n, s in db.execute(
                select(Cliente.id, Cliente.nome, Cliente.sobrenome)
                .where(Cliente.loja_id == loja_id, Cliente.id.in_(ids_clientes))
                .execution_options(incluir_excluidos=True)
            ).all()
        }
    modulos = {}
    if any(r.tabela == 'loja_funcionalidades' for r in registros):
        modulos = {str(i): n for i, n in db.execute(select(Funcionalidade.id, Funcionalidade.nome)).all()}

    saida = []
    for r, linha in zip(registros, linhas, strict=True):
        rotulo: str | None = None
        match r.tabela:
            case 'agendamentos':
                quando = _data_hora(linha.get('inicio'), zona)
                cliente = clientes.get(UUID(linha['cliente_id'])) if linha.get('cliente_id') else None
                rotulo = ' · '.join(x for x in (quando, cliente) if x)
            case 'clientes':
                rotulo = f'{linha.get("nome", "")} {linha.get("sobrenome", "")}'.strip()
            case 'registros_ponto':
                quando = _data_hora(linha.get('entrada'), zona)
                rotulo = f'Entrada {quando}' if quando else None
            case 'perfil_horarios':
                dia = linha.get('dia_semana')
                if isinstance(dia, int) and 0 <= dia <= 6:
                    ini, fim = str(linha.get('hora_inicio', ''))[:5], str(linha.get('hora_fim', ''))[:5]
                    rotulo = f'{DIAS[dia]} {ini}–{fim}'
            case 'bloqueios_agenda':
                rotulo = linha.get('motivo') or _data_hora(linha.get('inicio'), zona)
            case 'loja_funcionalidades':
                rotulo = modulos.get(str(linha.get('funcionalidade_id')))
            case 'movimentacoes_estoque':
                rotulo = f'{linha.get("tipo", "")} {linha.get("quantidade", "")}'.strip()
            case _:
                rotulo = linha.get('nome_fantasia') or linha.get('nome') or linha.get('email')
        saida.append(rotulo or f'#{r.registro_id}')
    return saida


def descrever(
    db: Session, loja_id: UUID | None, registros: Sequence[Auditoria], zona: ZoneInfo
) -> list[AuditoriaItem]:
    quem = descrever_quem(db, loja_id, [(r.funcionario_id, r.superadmin_id, r.origem) for r in registros])
    textos = rotulos(db, loja_id, registros, zona)
    return [
        AuditoriaItem(
            id=r.id,
            criado_em=r.criado_em.astimezone(zona),
            loja_id=r.loja_id,
            tabela=r.tabela,
            tabela_nome=nome_tabela(r.tabela),
            registro_id=r.registro_id,
            rotulo=rotulo,
            operacao=r.operacao,
            origem=r.origem,
            quem=quem[_chave_quem(r.funcionario_id, r.superadmin_id, r.origem)],
            mudancas=mudancas(r, zona),
            antes=_linha_no_fuso(r.antes, zona),
            depois=_linha_no_fuso(r.depois, zona),
        )
        for r, rotulo in zip(registros, textos, strict=True)
    ]


def fuso_da_area(db: Session, loja_id: UUID | None) -> ZoneInfo:
    if loja_id is None:
        return ZoneInfo(FUSO_PLATAFORMA)
    fuso = db.scalar(
        select(Loja.fuso_horario).where(Loja.id == loja_id).execution_options(incluir_excluidos=True)
    )
    return ZoneInfo(fuso or FUSO_PLATAFORMA)
