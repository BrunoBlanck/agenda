"""Loja de exemplo montada pela API para os testes de agenda: jornada, clientes, locais, materiais e serviços.

Datas fixas no futuro: 2030-01-07 é uma segunda-feira (dia_semana = 1).
"""

from dataclasses import dataclass

from tests.fabricas import LojaTeste

SEGUNDA = '2030-01-07'


@dataclass
class Clinica:
    lt: LojaTeste
    maria: str
    joao: str
    sala1: str
    sala2: str
    online: str
    luvas: str
    limpeza: str
    avaliacao: str

    def dados(self, **extra):
        return {
            'cliente_id': self.maria,
            'servico_id': self.limpeza,
            'funcionario_id': str(self.lt.prof.id),
            'local_id': self.sala1,
            'inicio': f'{SEGUNDA}T09:00',
            **extra,
        }


def montar_clinica(cliente, lt: LojaTeste) -> Clinica:
    h = lt.h_admin

    def post(url, corpo):
        resposta = cliente.post(f'/api/loja/{url}', json=corpo, headers=h)
        assert resposta.status_code == 201, resposta.json()
        return resposta.json()['id']

    for perfil in lt.perfis.values():
        for ini, fim in (('08:00', '12:00'), ('13:00', '18:00')):
            post(f'perfis/{perfil.id}/horarios', {'dia_semana': 1, 'hora_inicio': ini, 'hora_fim': fim})
    maria = post('clientes', {'nome': 'Maria', 'sobrenome': 'Oliveira', 'telefone': '(11) 98888-1111'})
    joao = post('clientes', {'nome': 'João', 'sobrenome': 'Pereira', 'telefone': '(11) 98888-2222'})
    sala1, sala2 = post('locais', {'nome': 'Sala 1'}), post('locais', {'nome': 'Sala 2'})
    online = post(
        'locais', {'nome': 'Online', 'tipo': 'online', 'link_padrao': 'https://meet.example.com/fixo'}
    )
    luvas = post('materiais', {'nome': 'Luvas', 'quantidade_inicial': 10})
    limpeza = post(
        'servicos',
        {
            'nome': 'Limpeza',
            'duracao_minutos': 60,
            'preco': 200,
            'funcionario_ids': [str(lt.admin.id), str(lt.prof.id)],
            'local_ids': [sala1, online],
            'materiais': [{'material_id': luvas, 'quantidade': 2}],
        },
    )
    avaliacao = post(
        'servicos',
        {'nome': 'Avaliação', 'duracao_minutos': 30, 'preco': 100, 'funcionario_ids': [str(lt.admin.id)]},
    )
    return Clinica(lt, maria, joao, sala1, sala2, online, luvas, limpeza, avaliacao)
