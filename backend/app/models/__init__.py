"""Modelos SQLAlchemy. Importar daqui registra todas as tabelas no Base.metadata."""

from app.models.acesso import Cargo, Funcionario, Perfil, PerfilAcesso
from app.models.agenda import Agendamento, AgendamentoMaterial, BloqueioAgenda, PerfilHorario
from app.models.base import Base, ControleMixin, LojaMixin
from app.models.clientes import Cliente, ClienteCodigo, ClienteConta
from app.models.locais import Local, LojaConfiguracao
from app.models.materiais import CategoriaMaterial, Material, MovimentacaoEstoque
from app.models.notificacoes import Notificacao
from app.models.plataforma import (
    Auditoria,
    Funcionalidade,
    Loja,
    LojaFuncionalidade,
    Plano,
    Recurso,
    SuperadminUsuario,
)
from app.models.ponto import RegistroPonto
from app.models.servicos import Servico, ServicoFuncionario, ServicoLocal, ServicoMaterial

__all__ = [
    'Agendamento',
    'AgendamentoMaterial',
    'Auditoria',
    'Base',
    'BloqueioAgenda',
    'Cargo',
    'CategoriaMaterial',
    'Cliente',
    'ClienteCodigo',
    'ClienteConta',
    'ControleMixin',
    'Funcionalidade',
    'Funcionario',
    'Local',
    'Loja',
    'LojaConfiguracao',
    'LojaFuncionalidade',
    'LojaMixin',
    'Material',
    'MovimentacaoEstoque',
    'Notificacao',
    'Perfil',
    'PerfilAcesso',
    'PerfilHorario',
    'Plano',
    'Recurso',
    'RegistroPonto',
    'Servico',
    'ServicoFuncionario',
    'ServicoLocal',
    'ServicoMaterial',
    'SuperadminUsuario',
]
