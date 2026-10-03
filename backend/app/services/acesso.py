"""Nível de acesso efetivo do funcionário (estrutura.md, 1.7, 1.8 e 2.2).

Espelha frontend/src/data/useAcesso.js:
- módulo ativo = funcionalidade não opcional, ou registro em loja_funcionalidades com
  habilitado = true e expira_em nula ou futura (e a funcionalidade ativa no catálogo);
- nível efetivo = nenhum se o módulo do recurso estiver desativado (inclusive para o Administrador);
  escrita em tudo se o perfil tem acesso_total; senão o nível do perfil (sem linha = nenhum).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth.catalogo import PESO
from app.models import Funcionalidade, LojaFuncionalidade, Perfil, PerfilAcesso, Recurso
from app.models.enums import NivelAcesso


@dataclass(frozen=True)
class Acesso:
    modulos: dict[str, bool]
    niveis: dict[str, NivelAcesso]

    def modulo_ativo(self, codigo: str) -> bool:
        return self.modulos.get(codigo, False)

    def nivel(self, recurso: str) -> NivelAcesso:
        return self.niveis.get(recurso, NivelAcesso.nenhum)

    def pode(self, recurso: str, minimo: NivelAcesso = NivelAcesso.leitura) -> bool:
        return PESO[self.nivel(recurso)] >= PESO[minimo]


def modulos_da_loja(db: Session, loja_id: UUID, agora: datetime | None = None) -> dict[str, bool]:
    """Todos os módulos do catálogo, com True para os ativos na loja."""
    agora = agora or datetime.now(UTC)
    linhas = db.execute(
        select(
            Funcionalidade.codigo,
            Funcionalidade.opcional,
            Funcionalidade.ativo,
            LojaFuncionalidade.habilitado,
            LojaFuncionalidade.expira_em,
        ).outerjoin(
            LojaFuncionalidade,
            and_(
                LojaFuncionalidade.funcionalidade_id == Funcionalidade.id,
                LojaFuncionalidade.loja_id == loja_id,
            ),
        )
    ).all()
    modulos: dict[str, bool] = {}
    for codigo, opcional, ativo_catalogo, habilitado, expira_em in linhas:
        if not ativo_catalogo:
            modulos[codigo] = False
        elif not opcional:
            modulos[codigo] = True
        else:
            modulos[codigo] = bool(habilitado) and (expira_em is None or expira_em > agora)
    return modulos


def calcular_acesso(db: Session, loja_id: UUID, perfil: Perfil) -> Acesso:
    modulos = modulos_da_loja(db, loja_id)
    recursos = db.execute(
        select(Recurso.id, Recurso.codigo, Funcionalidade.codigo).join(
            Funcionalidade, Funcionalidade.id == Recurso.funcionalidade_id
        )
    ).all()
    do_perfil = dict(
        db.execute(
            select(PerfilAcesso.recurso_id, PerfilAcesso.nivel).where(
                PerfilAcesso.loja_id == loja_id, PerfilAcesso.perfil_id == perfil.id
            )
        ).all()
    )
    niveis: dict[str, NivelAcesso] = {}
    for recurso_id, codigo, modulo in recursos:
        if not modulos.get(modulo, False):
            niveis[codigo] = NivelAcesso.nenhum
        elif perfil.acesso_total:
            niveis[codigo] = NivelAcesso.escrita
        else:
            niveis[codigo] = do_perfil.get(recurso_id, NivelAcesso.nenhum)
    return Acesso(modulos=modulos, niveis=niveis)


# --- Sem escalada de acesso (ACE-19, SEG-05) ------------------------------------------------------


def niveis_do_perfil(db: Session, loja_id: UUID, perfil: Perfil) -> dict[str, NivelAcesso]:
    """Nível gravado no perfil para cada recurso do catálogo (Administrador = escrita em tudo).

    Sem o efeito dos módulos: um módulo desligado vale para todos os perfis ao mesmo tempo, então
    comparar os níveis gravados é o que impede alguém de conceder mais do que tem, hoje ou quando o
    módulo for religado. Nos módulos ligados, é igual ao nível efetivo.
    """
    codigos = db.scalars(select(Recurso.codigo)).all()
    if perfil.acesso_total:
        return dict.fromkeys(codigos, NivelAcesso.escrita)
    gravados = dict(
        db.execute(
            select(Recurso.codigo, PerfilAcesso.nivel)
            .join(Recurso, Recurso.id == PerfilAcesso.recurso_id)
            .where(PerfilAcesso.loja_id == loja_id, PerfilAcesso.perfil_id == perfil.id)
        ).all()
    )
    return {codigo: gravados.get(codigo, NivelAcesso.nenhum) for codigo in codigos}


def acima_do_teto(niveis: dict[str, NivelAcesso], teto: dict[str, NivelAcesso]) -> list[str]:
    """Recursos (do catálogo) em que ``niveis`` passa do ``teto`` de quem está agindo."""
    return sorted(
        codigo for codigo, nivel in niveis.items() if codigo in teto and PESO[nivel] > PESO[teto[codigo]]
    )
