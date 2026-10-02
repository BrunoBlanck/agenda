"""Criação de dados para os testes (com o dono do schema, sem RLS) e atalhos de login."""

from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from itertools import count
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.auth.senhas import gerar_hash
from app.auth.tokens import criar_token
from app.db import Origem, definir_contexto
from app.models import (
    Funcionalidade,
    Funcionario,
    Loja,
    LojaFuncionalidade,
    Perfil,
    PerfilAcesso,
    Recurso,
    SuperadminUsuario,
)
from app.models.enums import NivelAcesso, StatusLoja, TipoLoja
from app.services.lojas import provisionar_loja

SENHA = 'senha123'
TODOS_MODULOS = {'servicos': True, 'materiais': True, 'controle_tempo': True, 'locais': True}


@lru_cache
def hash_senha() -> str:
    return gerar_hash(SENHA)


@contextmanager
def sessao(engine: Engine, origem: Origem = 'sistema', **contexto):
    """Sessão com transação e contexto (funcionario_id, superadmin_id, loja_id) gravado."""
    with Session(engine, expire_on_commit=False) as db, db.begin():
        definir_contexto(db, origem=origem, **contexto)
        yield db


def criar_loja(
    engine: Engine,
    slug: str,
    *,
    modulos: dict[str, bool] | None = None,
    status: StatusLoja = StatusLoja.ativa,
) -> tuple[Loja, dict[str, Perfil]]:
    with sessao(engine) as db:
        loja = Loja(
            tipo=TipoLoja.clinica, nome=f'Loja {slug}', nome_fantasia=f'Loja {slug}', slug=slug, status=status
        )
        db.add(loja)
        db.flush()
        perfis = provisionar_loja(db, loja.id, TODOS_MODULOS if modulos is None else modulos)
    return loja, perfis


def criar_funcionario(
    engine: Engine,
    loja: Loja,
    perfil: Perfil,
    email: str,
    *,
    ativo: bool = True,
    nome: str = 'Funcionário',
) -> Funcionario:
    with sessao(engine) as db:
        funcionario = Funcionario(
            loja_id=loja.id, perfil_id=perfil.id, nome=nome, email=email, senha_hash=hash_senha(), ativo=ativo
        )
        db.add(funcionario)
    return funcionario


def criar_superadmin(
    engine: Engine, email: str = 'admin@plataforma.com', *, ativo: bool = True
) -> SuperadminUsuario:
    with sessao(engine) as db:
        superadmin = SuperadminUsuario(nome='Admin', email=email, senha_hash=hash_senha(), ativo=ativo)
        db.add(superadmin)
    return superadmin


def mudar_modulo(engine: Engine, loja_id: UUID, codigo: str, **valores) -> None:
    with sessao(engine) as db:
        registro = db.scalar(
            select(LojaFuncionalidade)
            .join(Funcionalidade, Funcionalidade.id == LojaFuncionalidade.funcionalidade_id)
            .where(LojaFuncionalidade.loja_id == loja_id, Funcionalidade.codigo == codigo)
        )
        for chave, valor in valores.items():
            setattr(registro, chave, valor)


def login_loja(cliente, slug: str, email: str, senha: str = SENHA) -> dict[str, str]:
    resposta = cliente.post('/api/loja/auth/login', json={'slug': slug, 'email': email, 'senha': senha})
    assert resposta.status_code == 200, resposta.json()
    return {'Authorization': f'Bearer {resposta.json()["token"]}'}


def login_superadmin(cliente, email: str, senha: str = SENHA) -> dict[str, str]:
    resposta = cliente.post('/api/superadmin/auth/login', json={'email': email, 'senha': senha})
    assert resposta.status_code == 200, resposta.json()
    return {'Authorization': f'Bearer {resposta.json()["token"]}'}


# --- Atalhos para os testes das rotas do painel -------------------------------------------------


def cabecalho(funcionario: Funcionario) -> dict[str, str]:
    """Token do funcionário sem passar pelo login (que gasta tempo com o Argon2)."""
    token, _ = criar_token(funcionario.id, 'funcionario', funcionario.loja_id)
    return {'Authorization': f'Bearer {token}'}


def inserir(engine: Engine, *objetos):
    """Grava objetos do ORM com o dono do schema (sem RLS). Devolve o primeiro (ou a tupla)."""
    with sessao(engine) as db:
        for obj in objetos:
            db.add(obj)
            db.flush()
    return objetos[0] if len(objetos) == 1 else objetos


_contador = count(1)


def usuario_com(
    engine: Engine, loja: Loja, acessos: dict[str, str], *, nome: str | None = None
) -> dict[str, str]:
    """Cria um perfil com os níveis dados (o resto = nenhum) e um funcionário nele. Devolve o cabeçalho."""
    n = next(_contador)
    with sessao(engine) as db:
        perfil = Perfil(loja_id=loja.id, nome=f'Perfil teste {n}')
        db.add(perfil)
        db.flush()
        for codigo, recurso_id in db.execute(select(Recurso.codigo, Recurso.id)).all():
            db.add(
                PerfilAcesso(
                    loja_id=loja.id,
                    perfil_id=perfil.id,
                    recurso_id=recurso_id,
                    nivel=NivelAcesso(acessos.get(codigo, 'nenhum')),
                )
            )
        funcionario = Funcionario(
            loja_id=loja.id,
            perfil_id=perfil.id,
            nome=nome or f'Usuário {n}',
            email=f'usuario{n}@{loja.slug}.com',
            senha_hash=hash_senha(),
        )
        db.add(funcionario)
    return cabecalho(funcionario)


@dataclass
class LojaTeste:
    loja: Loja
    perfis: dict[str, Perfil]
    admin: Funcionario
    recepcao: Funcionario
    prof: Funcionario

    @property
    def h_admin(self) -> dict[str, str]:
        return cabecalho(self.admin)

    @property
    def h_recepcao(self) -> dict[str, str]:
        return cabecalho(self.recepcao)

    @property
    def h_prof(self) -> dict[str, str]:
        return cabecalho(self.prof)


def criar_loja_teste(engine: Engine, slug: str, modulos: dict[str, bool] | None = None) -> LojaTeste:
    loja, perfis = criar_loja(engine, slug, modulos=modulos)
    return LojaTeste(
        loja=loja,
        perfis=perfis,
        admin=criar_funcionario(engine, loja, perfis['Administrador'], f'admin@{slug}.com', nome='Admin'),
        recepcao=criar_funcionario(engine, loja, perfis['Recepção'], f'recepcao@{slug}.com', nome='Recepção'),
        prof=criar_funcionario(engine, loja, perfis['Profissional'], f'prof@{slug}.com', nome='Profissional'),
    )
