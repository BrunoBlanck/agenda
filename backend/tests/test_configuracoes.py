"""Configurações › Dados da loja: campos editáveis, validações, permissões e isolamento."""

from sqlalchemy import select

from app.models import Loja
from tests.fabricas import criar_superadmin, mudar_modulo, sessao, usuario_com

URL = '/api/loja/configuracoes/loja'
DADOS = {
    'nome_fantasia': 'Clínica Sorriso',
    'nome': 'Clínica Sorriso Serviços Odontológicos Ltda',
    'cnpj': '11222333000181',
    'telefone': '(11) 3333-4444',
    'email': 'contato@clinicasorriso.com',
    'cep': '01310100',
    'logradouro': 'Avenida Paulista',
    'numero': '1000',
    'complemento': '',
    'bairro': 'Bela Vista',
    'cidade': 'São Paulo',
    'uf': 'sp',
}


def test_ler_e_editar_dados_da_loja(cliente, lojas, engine_dono):
    a, _ = lojas
    mudar_modulo(engine_dono, a.loja.id, 'locais', habilitado=False)
    antes = cliente.get(URL, headers=a.h_admin).json()
    assert antes['slug'] == 'loja-a'
    assert antes['tipo'] == 'clinica'
    assert antes['modulos'] == {'servicos': True, 'materiais': True, 'controle_tempo': True, 'locais': False}

    editado = cliente.put(URL, json={**DADOS, 'slug': 'outra', 'status': 'cancelada'}, headers=a.h_admin)
    assert editado.status_code == 200, editado.json()
    corpo = editado.json()
    assert corpo['cnpj'] == '11.222.333/0001-81'
    assert corpo['cep'] == '01310-100'
    assert corpo['uf'] == 'SP'
    assert corpo['complemento'] is None
    assert (corpo['slug'], corpo['status']) == ('loja-a', 'ativa')  # só o superadmin muda
    # Mesmo contrato do Controle das outras rotas: uuid do funcionário + nome, no fuso da loja
    assert (corpo['atualizado_por'], corpo['atualizado_por_nome']) == (str(a.admin.id), 'Admin')
    assert corpo['atualizado_em'].endswith('-03:00')
    assert corpo['criado_em'].endswith('-03:00')
    with engine_dono.connect() as conexao:
        quem = conexao.execute(select(Loja.atualizado_por_funcionario).where(Loja.id == a.loja.id)).scalar()
    assert quem == a.admin.id


def test_validacoes(cliente, lojas):
    a, b = lojas

    def erro(**campos):
        resposta = cliente.put(URL, json={**DADOS, **campos}, headers=a.h_admin)
        assert resposta.status_code == 422, resposta.json()
        return resposta.json()['erros'][0]['mensagem']

    assert erro(cnpj='11.222.333/0001-82') == 'CNPJ inválido.'
    assert erro(cnpj='11111111111111') == 'CNPJ inválido.'
    assert erro(cep='123') == 'CEP inválido.'
    assert erro(uf='S1') == 'UF inválida.'
    assert erro(email='sem-arroba') == 'E-mail inválido.'
    assert erro(nome_fantasia='') == 'Texto muito curto (mínimo de 1 caractere(s)).'
    # CNPJ de outra loja
    assert cliente.put(URL, json=DADOS, headers=b.h_admin).status_code == 200
    repetido = cliente.put(URL, json=DADOS, headers=a.h_admin)
    assert repetido.status_code == 409
    assert repetido.json()['detail'] == 'Este CNPJ já está cadastrado em outra loja.'
    # CNPJ é opcional
    assert cliente.put(URL, json={**DADOS, 'cnpj': ''}, headers=a.h_admin).json()['cnpj'] is None


def test_remover_logo(cliente, lojas, engine_dono):
    a, _ = lojas
    with sessao(engine_dono) as db:
        db.get(Loja, a.loja.id).logo_url = 'lojas/x/logo.png'
    assert cliente.get(URL, headers=a.h_admin).json()['logo_url'] == 'lojas/x/logo.png'
    assert cliente.delete(f'{URL}/logo', headers=a.h_admin).status_code == 204
    assert cliente.get(URL, headers=a.h_admin).json()['logo_url'] is None


def test_alteracao_do_superadmin_fica_sem_autor(cliente, lojas, engine_dono):
    """GER-13: alteração do superadmin deixa atualizado_por nulo (o front mostra "Superadmin")."""
    a, _ = lojas
    cliente.put(URL, json=DADOS, headers=a.h_admin)
    admin = criar_superadmin(engine_dono)
    with sessao(engine_dono, 'superadmin', superadmin_id=admin.id) as db:
        db.get(Loja, a.loja.id).telefone = '(11) 0000-0000'
    corpo = cliente.get(URL, headers=a.h_admin).json()
    assert (corpo['atualizado_por'], corpo['atualizado_por_nome']) == (None, None)


def test_permissoes(cliente, lojas):
    a, _ = lojas
    # Recepção e Profissional: nenhum em Dados da loja
    for cabecalho in (a.h_recepcao, a.h_prof):
        assert cliente.get(URL, headers=cabecalho).status_code == 403
        assert cliente.put(URL, json=DADOS, headers=cabecalho).status_code == 403
        assert cliente.delete(f'{URL}/logo', headers=cabecalho).status_code == 403


def test_leitura_nao_edita(cliente, lojas, engine_dono):
    a, _ = lojas
    leitor = usuario_com(engine_dono, a.loja, {'config_loja': 'leitura'})
    assert cliente.get(URL, headers=leitor).status_code == 200
    assert cliente.put(URL, json=DADOS, headers=leitor).status_code == 403


def test_isolamento_entre_lojas(cliente, lojas, engine_dono):
    a, b = lojas
    cliente.put(URL, json={**DADOS, 'nome_fantasia': 'Loja B nova'}, headers=b.h_admin)
    assert cliente.get(URL, headers=a.h_admin).json()['nome_fantasia'] == 'Loja loja-a'
    assert cliente.get(URL, headers=b.h_admin).json()['nome_fantasia'] == 'Loja B nova'
    with engine_dono.connect() as conexao:
        nome_a = conexao.execute(select(Loja.nome_fantasia).where(Loja.id == a.loja.id)).scalar()
    assert nome_a == 'Loja loja-a'
