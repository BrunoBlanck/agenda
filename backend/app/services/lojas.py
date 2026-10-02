"""Criação de loja: perfis padrão, módulos e configurações (estrutura.md, 1.6, 1.7, 2.1 e 2.21).

Usado pelo seed e, na etapa do SUPERADMIN, pela rota de criação de loja.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.catalogo import MODULOS
from app.models import Funcionalidade, LojaConfiguracao, LojaFuncionalidade, Perfil, PerfilAcesso, Recurso
from app.models.enums import NivelAcesso

E, L = NivelAcesso.escrita, NivelAcesso.leitura

# Perfis criados com a loja (estrutura.md, 2.1). Recurso ausente = nenhum.
PERFIS_PADRAO: list[dict] = [
    {
        'nome': 'Administrador',
        'descricao': 'Escrita em tudo o que estiver ativo na loja',
        'acesso_total': True,
        'acessos': {},
    },
    {
        'nome': 'Recepção',
        'descricao': 'Agenda de todos os profissionais, clientes e o próprio ponto',
        'acesso_total': False,
        'acessos': {
            'agenda_propria': E,
            'agenda_equipe': E,
            'config_agendamentos': L,
            'clientes': E,
            'servicos': L,
            'locais': L,
            'ponto_proprio': E,
        },
    },
    {
        'nome': 'Profissional',
        'descricao': 'Apenas a própria agenda, consulta de clientes e o próprio ponto',
        'acesso_total': False,
        'acessos': {'agenda_propria': E, 'clientes': L, 'ponto_proprio': E},
    },
]


def criar_perfis_padrao(db: Session, loja_id: UUID) -> dict[str, Perfil]:
    """Cria Administrador, Recepção e Profissional com uma linha de nível para cada recurso."""
    recursos = dict(db.execute(select(Recurso.codigo, Recurso.id)).all())
    perfis: dict[str, Perfil] = {}
    for modelo in PERFIS_PADRAO:
        perfil = Perfil(
            loja_id=loja_id,
            nome=modelo['nome'],
            descricao=modelo['descricao'],
            padrao=True,
            acesso_total=modelo['acesso_total'],
        )
        db.add(perfil)
        db.flush()
        if not perfil.acesso_total:
            for codigo, recurso_id in recursos.items():
                nivel = modelo['acessos'].get(codigo, NivelAcesso.nenhum)
                db.add(PerfilAcesso(loja_id=loja_id, perfil_id=perfil.id, recurso_id=recurso_id, nivel=nivel))
        perfis[perfil.nome] = perfil
    db.flush()
    return perfis


def definir_modulos(db: Session, loja_id: UUID, modulos: dict[str, bool]) -> None:
    """Cria um registro em loja_funcionalidades para cada módulo opcional (habilitado conforme a escolha).

    Módulo opcional não informado fica desligado.
    """
    desconhecidos = set(modulos) - {c for c, opcional in MODULOS.items() if opcional}
    if desconhecidos:
        raise ValueError(f'Módulos que não são opcionais ou não existem: {sorted(desconhecidos)}')
    opcionais = db.execute(
        select(Funcionalidade.codigo, Funcionalidade.id).where(Funcionalidade.opcional)
    ).all()
    for codigo, funcionalidade_id in opcionais:
        db.add(
            LojaFuncionalidade(
                loja_id=loja_id,
                funcionalidade_id=funcionalidade_id,
                habilitado=modulos.get(codigo, False),
            )
        )
    db.flush()


def provisionar_loja(
    db: Session,
    loja_id: UUID,
    modulos: dict[str, bool],
    rotulo_local: str = 'Local',
    rotulo_local_plural: str = 'Locais',
) -> dict[str, Perfil]:
    """Tudo o que nasce junto com a loja. Retorna os perfis padrão por nome."""
    db.add(
        LojaConfiguracao(loja_id=loja_id, rotulo_local=rotulo_local, rotulo_local_plural=rotulo_local_plural)
    )
    definir_modulos(db, loja_id, modulos)
    return criar_perfis_padrao(db, loja_id)
