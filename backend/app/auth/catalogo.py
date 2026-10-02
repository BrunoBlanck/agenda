"""Catálogo de módulos e recursos espelhado do banco (migração 0002) e do front (acesso.js).

O banco é a fonte da verdade; estas constantes existem para validar, já na importação, os códigos
usados em exigir(...). Um teste garante que batem com as tabelas funcionalidades e recursos.
"""

from app.models.enums import NivelAcesso

# Módulos: codigo -> opcional
MODULOS: dict[str, bool] = {
    'inicio': False,
    'agenda': False,
    'clientes': False,
    'funcionarios': False,
    'configuracoes': False,
    'servicos': True,
    'materiais': True,
    'controle_tempo': True,
    'locais': True,
}

# Recursos: codigo -> módulo
RECURSOS: dict[str, str] = {
    'agenda_propria': 'agenda',
    'agenda_equipe': 'agenda',
    'config_agendamentos': 'agenda',
    'clientes': 'clientes',
    'funcionarios': 'funcionarios',
    'perfis_acesso': 'funcionarios',
    'servicos': 'servicos',
    'materiais': 'materiais',
    'locais': 'locais',
    'ponto_proprio': 'controle_tempo',
    'ponto_equipe': 'controle_tempo',
    'config_loja': 'configuracoes',
}

# Escrita inclui leitura
PESO: dict[NivelAcesso, int] = {
    NivelAcesso.nenhum: 0,
    NivelAcesso.leitura: 1,
    NivelAcesso.escrita: 2,
}
