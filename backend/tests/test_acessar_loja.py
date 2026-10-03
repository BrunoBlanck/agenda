"""Acessar loja pelo SUPERADMIN (PLA-17 a PLA-19, PLA-14; docs/funcionalidades/acessar-loja.md)."""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import text

from app.config import get_settings
from app.models import Perfil
from app.models.enums import StatusLoja
from tests.fabricas import (
    SENHA,
    cabecalho,
    cabecalho_superadmin,
    criar_funcionario,
    criar_loja,
    criar_loja_teste,
    criar_superadmin,
    inserir,
)

MSG_SEM_ADMIN = 'Esta loja não tem um Administrador ativo para acessar.'


def url(loja_id) -> str:
    return f'/api/superadmin/lojas/{loja_id}/acesso'


def bearer(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def mudar_loja(engine, loja_id: UUID, **campos) -> None:
    atribuicoes = ', '.join(f'{campo} = :{campo}' for campo in campos)
    with engine.begin() as conexao:
        conexao.execute(text(f'UPDATE lojas SET {atribuicoes} WHERE id = :id'), {'id': loja_id, **campos})


def mudar_criado_em(engine, funcionario_id: UUID, momento: datetime) -> None:
    """criado_em é protegido pelo trigger de controle: só com os triggers desligados (dono do schema)."""
    with engine.begin() as conexao:
        conexao.execute(text('SET LOCAL session_replication_role = replica'))
        conexao.execute(
            text('UPDATE funcionarios SET criado_em = :momento WHERE id = :id'),
            {'momento': momento, 'id': funcionario_id},
        )


def ler_funcionario(engine, funcionario_id: UUID):
    with engine.connect() as conexao:
        return conexao.execute(
            text('SELECT ultimo_login_em, atualizado_em FROM funcionarios WHERE id = :id'),
            {'id': funcionario_id},
        ).one()


def auditoria_do_acesso(engine, loja_id: UUID) -> list:
    with engine.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT a.*, a::text AS linha FROM auditoria a WHERE a.loja_id = :loja AND a.depois->>'acao' = "
                "'acessar_loja' ORDER BY a.id"
            ),
            {'loja': loja_id},
        ).all()


@pytest.fixture
def superadmin(engine_dono):
    return criar_superadmin(engine_dono)


@pytest.fixture
def sa(superadmin):
    return cabecalho_superadmin(superadmin)


@pytest.fixture
def a(engine_dono):
    return criar_loja_teste(engine_dono, 'loja-a')


# --- Gerar o acesso -------------------------------------------------------------------------------


def test_gera_token_que_abre_o_painel_como_o_administrador(cliente, sa, a):
    antes = datetime.now(UTC)
    resposta = cliente.post(url(a.loja.id), json={}, headers=sa)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {'token', 'expira_em', 'slug', 'funcionario_nome'}
    assert corpo['slug'] == 'loja-a'
    assert corpo['funcionario_nome'] == 'Admin'
    assert corpo['expira_em'].endswith('-03:00')  # fuso da loja

    dados = jwt.decode(corpo['token'], options={'verify_signature': False})
    assert dados['tipo'] == 'funcionario'
    assert dados['sub'] == str(a.admin.id)
    assert dados['loja_id'] == str(a.loja.id)
    assert dados['suporte'] is True

    eu = cliente.get('/api/loja/eu', headers=bearer(corpo['token']))
    assert eu.status_code == 200
    eu = eu.json()
    assert eu['funcionario']['id'] == str(a.admin.id)
    assert eu['perfil']['acesso_total'] is True
    assert eu['sessao']['suporte'] is True
    assert eu['sessao']['expira_em'].endswith('-03:00')
    assert datetime.fromisoformat(eu['sessao']['expira_em']) == datetime.fromisoformat(corpo['expira_em'])
    assert datetime.fromisoformat(corpo['expira_em']) - antes <= timedelta(minutes=60, seconds=5)


def test_corpo_ausente_tambem_e_aceito(cliente, sa, a):
    assert cliente.post(url(a.loja.id), headers=sa).status_code == 201


def test_token_vale_60_minutos_fixos_sem_usar_a_validade_do_login(cliente, sa, a, monkeypatch):
    monkeypatch.setattr(get_settings(), 'jwt_expira_minutos', 5)
    antes = datetime.now(UTC).replace(microsecond=0)
    corpo = cliente.post(url(a.loja.id), headers=sa).json()
    depois = datetime.now(UTC)
    dados = jwt.decode(corpo['token'], options={'verify_signature': False})
    assert dados['exp'] - dados['iat'] == 3600
    expira = datetime.fromisoformat(corpo['expira_em'])
    assert antes + timedelta(minutes=60) <= expira <= depois + timedelta(minutes=60)
    assert int(expira.timestamp()) == dados['exp']


def test_login_normal_mostra_sessao_sem_suporte(cliente, a):
    eu = cliente.get('/api/loja/eu', headers=a.h_recepcao).json()
    assert eu['sessao']['suporte'] is False
    assert eu['sessao']['expira_em'].endswith('-03:00')


# --- Quem é o Administrador (PLA-17) -------------------------------------------------------------


def test_escolhe_o_administrador_ativo_mais_antigo(cliente, engine_dono, sa):
    loja, perfis = criar_loja(engine_dono, 'loja-x')
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # Mais antigos, mas fora da regra: inativo, outro perfil com acesso total, perfil não-Administrador
    inativo = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'inativo@x.com', ativo=False)
    perfil_total = inserir(engine_dono, Perfil(loja_id=loja.id, nome='Dono', acesso_total=True, padrao=False))
    dono = criar_funcionario(engine_dono, loja, perfil_total, 'dono@x.com', nome='Dono')
    recepcao = criar_funcionario(engine_dono, loja, perfis['Recepção'], 'recepcao@x.com')
    # Criado antes, mas com criado_em mais novo: a ordem é por criado_em, não pela inserção
    novo = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'novo@x.com', nome='Novo')
    antigo = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'antigo@x.com', nome='Antigo')
    for minutos, funcionario in enumerate([inativo, dono, recepcao, antigo, novo]):
        mudar_criado_em(engine_dono, funcionario.id, base + timedelta(minutes=minutos))

    corpo = cliente.post(url(loja.id), headers=sa).json()
    assert corpo['funcionario_nome'] == 'Antigo'
    assert jwt.decode(corpo['token'], options={'verify_signature': False})['sub'] == str(antigo.id)


def test_empate_no_criado_em_desempata_pelo_id(cliente, engine_dono, sa):
    loja, perfis = criar_loja(engine_dono, 'loja-x')
    um = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'um@x.com', nome='Um')
    dois = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'dois@x.com', nome='Dois')
    momento = datetime(2026, 1, 1, tzinfo=UTC)
    mudar_criado_em(engine_dono, um.id, momento)
    mudar_criado_em(engine_dono, dois.id, momento)
    menor = min([um, dois], key=lambda f: f.id)
    corpo = cliente.post(url(loja.id), headers=sa).json()
    assert corpo['funcionario_nome'] == menor.nome


def test_funcionario_excluido_nao_e_escolhido(cliente, engine_dono, sa):
    loja, perfis = criar_loja(engine_dono, 'loja-x')
    excluido = criar_funcionario(engine_dono, loja, perfis['Administrador'], 'exc@x.com', nome='Excluído')
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'ok@x.com', nome='Ativo')
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE funcionarios SET excluido_em = now() WHERE id = :id'), {'id': excluido.id}
        )
    assert cliente.post(url(loja.id), headers=sa).json()['funcionario_nome'] == 'Ativo'


def test_loja_sem_administrador_ativo_responde_409(cliente, engine_dono, sa):
    loja, perfis = criar_loja(engine_dono, 'loja-x')
    criar_funcionario(engine_dono, loja, perfis['Administrador'], 'inativo@x.com', ativo=False)
    criar_funcionario(engine_dono, loja, perfis['Recepção'], 'recepcao@x.com')
    perfil_total = inserir(engine_dono, Perfil(loja_id=loja.id, nome='Dono', acesso_total=True))
    criar_funcionario(engine_dono, loja, perfil_total, 'dono@x.com')
    resposta = cliente.post(url(loja.id), headers=sa)
    assert resposta.status_code == 409
    assert resposta.json() == {'detail': MSG_SEM_ADMIN}
    assert auditoria_do_acesso(engine_dono, loja.id) == []  # nada registrado quando não abre


def test_loja_sem_nenhum_funcionario_responde_409(cliente, engine_dono, sa):
    loja, _ = criar_loja(engine_dono, 'loja-x')
    resposta = cliente.post(url(loja.id), headers=sa)
    assert resposta.status_code == 409
    assert resposta.json()['detail'] == MSG_SEM_ADMIN


# --- Situação da loja (PLA-19 e GER-25) -----------------------------------------------------------


@pytest.mark.parametrize('situacao', [StatusLoja.suspensa, StatusLoja.cancelada])
def test_loja_suspensa_ou_cancelada_pode_ser_acessada(cliente, engine_dono, sa, a, situacao):
    mudar_loja(engine_dono, a.loja.id, status=situacao.value)
    resposta = cliente.post(url(a.loja.id), headers=sa)
    assert resposta.status_code == 201
    h = bearer(resposta.json()['token'])
    assert cliente.get('/api/loja/eu', headers=h).status_code == 200
    assert cliente.get('/api/loja/clientes', headers=h).status_code == 200
    criado = cliente.post(
        '/api/loja/clientes',
        json={'nome': 'Maria', 'sobrenome': 'Silva', 'telefone': '(11) 91111-1111'},
        headers=h,
    )
    assert criado.status_code == 201


@pytest.mark.parametrize('situacao', [StatusLoja.suspensa, StatusLoja.cancelada])
def test_funcionarios_continuam_bloqueados_na_loja_suspensa_ou_cancelada(
    cliente, engine_dono, sa, a, situacao
):
    mudar_loja(engine_dono, a.loja.id, status=situacao.value)
    assert cliente.post(url(a.loja.id), headers=sa).status_code == 201
    login = cliente.post(
        '/api/loja/auth/login', json={'slug': 'loja-a', 'email': 'admin@loja-a.com', 'senha': SENHA}
    )
    assert login.status_code == 403
    token_normal = cliente.get('/api/loja/eu', headers=a.h_admin)
    assert token_normal.status_code == 403
    assert situacao.value[:7] in token_normal.json()['detail']


def test_loja_excluida_responde_404(cliente, engine_dono, sa, a):
    mudar_loja(engine_dono, a.loja.id, status=StatusLoja.cancelada.value)
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET excluido_em = now() WHERE id = :id'), {'id': a.loja.id})
    resposta = cliente.post(url(a.loja.id), headers=sa)
    assert resposta.status_code == 404
    assert resposta.json() == {'detail': 'Loja não encontrada.'}


def test_token_de_suporte_para_de_valer_quando_a_loja_e_excluida(cliente, engine_dono, sa, a):
    token = cliente.post(url(a.loja.id), headers=sa).json()['token']
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE lojas SET excluido_em = now() WHERE id = :id'), {'id': a.loja.id})
    assert cliente.get('/api/loja/eu', headers=bearer(token)).status_code == 401


def test_loja_inexistente_responde_404(cliente, sa):
    resposta = cliente.post(url(uuid4()), headers=sa)
    assert resposta.status_code == 404
    assert resposta.json() == {'detail': 'Loja não encontrada.'}


def test_loja_id_que_nao_e_uuid_responde_422(cliente, sa):
    resposta = cliente.post(url('nao-e-uuid'), headers=sa)
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == 'Verifique os dados informados.'


# --- Auditoria (PLA-14) e ultimo_login_em --------------------------------------------------------


def test_auditoria_da_loja_registra_o_superadmin_sem_o_token(cliente, engine_dono, superadmin, sa, a):
    token = cliente.post(url(a.loja.id), headers=sa).json()['token']
    linhas = auditoria_do_acesso(engine_dono, a.loja.id)
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha.tabela == 'funcionarios'
    assert linha.registro_id == str(a.admin.id)
    assert linha.operacao == 'alterar'
    assert linha.origem == 'superadmin'
    assert linha.superadmin_id == superadmin.id
    assert linha.funcionario_id is None
    assert linha.depois == {'acao': 'acessar_loja', 'como_funcionario': 'Admin', 'nome': 'Admin'}
    assert linha.campos_alterados == ['acao', 'como_funcionario']  # nome é só o rótulo
    assert linha.antes is None
    assert token not in linha.linha
    assert token.split('.')[2] not in linha.linha  # nem a assinatura

    # Aparece na tela de auditoria do SUPERADMIN, como ação do superadmin
    item = cliente.get(
        '/api/superadmin/auditoria', params={'loja': str(a.loja.id), 'tabela': 'funcionarios'}, headers=sa
    ).json()['itens'][0]
    assert item['quem']['id'] == str(superadmin.id)
    assert item['origem'] == 'superadmin'
    assert item['rotulo'] == 'Admin'  # e não "#<uuid>"
    assert item['mudancas'] == [
        {'campo': 'acao', 'antes': None, 'depois': 'acessar_loja'},
        {'campo': 'como_funcionario', 'antes': None, 'depois': 'Admin'},
    ]


def test_gerar_e_usar_o_acesso_nao_muda_o_ultimo_login(cliente, engine_dono, sa, a):
    antes = ler_funcionario(engine_dono, a.admin.id)
    token = cliente.post(url(a.loja.id), headers=sa).json()['token']
    assert cliente.get('/api/loja/eu', headers=bearer(token)).status_code == 200
    depois = ler_funcionario(engine_dono, a.admin.id)
    assert antes.ultimo_login_em is None
    assert depois == antes  # nem ultimo_login_em, nem atualizado_em


def test_o_que_e_feito_na_sessao_fica_como_o_administrador(cliente, engine_dono, sa, a):
    h = bearer(cliente.post(url(a.loja.id), headers=sa).json()['token'])
    criado = cliente.post(
        '/api/loja/clientes',
        json={'nome': 'Maria', 'sobrenome': 'Silva', 'telefone': '(11) 91111-1111'},
        headers=h,
    )
    assert criado.status_code == 201
    assert criado.json()['atualizado_por'] == str(a.admin.id)
    assert criado.json()['atualizado_por_nome'] == 'Admin'
    with engine_dono.connect() as conexao:
        linha = conexao.execute(
            text("SELECT funcionario_id, superadmin_id, origem FROM auditoria WHERE tabela = 'clientes'")
        ).one()
    assert (linha.funcionario_id, linha.superadmin_id, linha.origem) == (a.admin.id, None, 'painel')


# --- O token de suporte segue as demais regras ---------------------------------------------------


def test_modulo_desligado_continua_bloqueado_no_suporte(cliente, engine_dono, sa):
    loja = criar_loja_teste(engine_dono, 'loja-x', modulos={'servicos': False})
    h = bearer(cliente.post(url(loja.loja.id), headers=sa).json()['token'])
    resposta = cliente.get('/api/loja/servicos', headers=h)
    assert resposta.status_code == 403
    assert resposta.json()['detail'] == 'Este módulo não está ativo na sua loja.'


def test_administrador_inativado_depois_perde_a_sessao_de_suporte(cliente, engine_dono, sa, a):
    h = bearer(cliente.post(url(a.loja.id), headers=sa).json()['token'])
    with engine_dono.begin() as conexao:
        conexao.execute(text('UPDATE funcionarios SET ativo = false WHERE id = :id'), {'id': a.admin.id})
    assert cliente.get('/api/loja/eu', headers=h).status_code == 401


def test_token_de_suporte_nao_le_outra_loja(cliente, engine_dono, sa, a):
    b = criar_loja_teste(engine_dono, 'loja-b')
    maria_b = cliente.post(
        '/api/loja/clientes',
        json={'nome': 'Maria', 'sobrenome': 'B', 'telefone': '(11) 92222-2222'},
        headers=b.h_admin,
    ).json()
    h = bearer(cliente.post(url(a.loja.id), headers=sa).json()['token'])
    assert cliente.get(f'/api/loja/clientes/{maria_b["id"]}', headers=h).status_code == 404
    assert cliente.get('/api/loja/clientes', headers=h).json()['total'] == 0


def test_token_de_suporte_vencido_responde_401(cliente, a):
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            'sub': str(a.admin.id),
            'tipo': 'funcionario',
            'loja_id': str(a.loja.id),
            'suporte': True,
            'iat': agora - timedelta(hours=2),
            'exp': agora - timedelta(hours=1),
        },
        get_settings().jwt_secret.get_secret_value(),
        algorithm='HS256',
    )
    assert cliente.get('/api/loja/eu', headers=bearer(token)).status_code == 401


def test_claim_suporte_forjada_nao_passa(cliente, engine_dono, a):
    mudar_loja(engine_dono, a.loja.id, status=StatusLoja.suspensa.value)
    agora = datetime.now(UTC)
    dados = {
        'sub': str(a.admin.id),
        'tipo': 'funcionario',
        'loja_id': str(a.loja.id),
        'suporte': True,
        'iat': agora,
        'exp': agora + timedelta(minutes=30),
    }
    outro_segredo = jwt.encode(dados, 'outro-segredo-qualquer-com-tamanho-suficiente', algorithm='HS256')
    sem_assinatura = jwt.encode(dados, None, algorithm='none')
    # Token verdadeiro de funcionário com a claim colada no corpo (a assinatura não confere mais)
    topo, corpo, assinatura = cabecalho(a.admin)['Authorization'].removeprefix('Bearer ').split('.')
    original = json.loads(base64.urlsafe_b64decode(corpo + '=' * (-len(corpo) % 4)))
    forjado = (
        base64.urlsafe_b64encode(json.dumps({**original, 'suporte': True}).encode()).rstrip(b'=').decode()
    )
    colado = f'{topo}.{forjado}.{assinatura}'
    for token in (outro_segredo, sem_assinatura, colado):
        assert cliente.get('/api/loja/eu', headers=bearer(token)).status_code == 401


@pytest.mark.parametrize('valor', ['true', 1, 'sim'])
def test_claim_suporte_que_nao_e_booleano_true_nao_libera_loja_suspensa(cliente, engine_dono, a, valor):
    mudar_loja(engine_dono, a.loja.id, status=StatusLoja.suspensa.value)
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            'sub': str(a.admin.id),
            'tipo': 'funcionario',
            'loja_id': str(a.loja.id),
            'suporte': valor,
            'iat': agora,
            'exp': agora + timedelta(minutes=5),
        },
        get_settings().jwt_secret.get_secret_value(),
        algorithm='HS256',
    )
    assert cliente.get('/api/loja/eu', headers=bearer(token)).status_code == 403


# --- Quem pode gerar (rota do SUPERADMIN) --------------------------------------------------------


def test_sem_token_responde_401(cliente, a):
    resposta = cliente.post(url(a.loja.id))
    assert resposta.status_code == 401
    assert resposta.json() == {'detail': 'Faça login para continuar.'}


def test_token_de_funcionario_nao_gera_acesso(cliente, a):
    assert cliente.post(url(a.loja.id), headers=a.h_admin).status_code == 401


def test_token_de_suporte_nao_gera_outro_acesso(cliente, sa, a):
    h = bearer(cliente.post(url(a.loja.id), headers=sa).json()['token'])
    assert cliente.post(url(a.loja.id), headers=h).status_code == 401


def test_superadmin_inativo_nao_gera_acesso(cliente, engine_dono, superadmin, sa, a):
    with engine_dono.begin() as conexao:
        conexao.execute(
            text('UPDATE superadmin_usuarios SET ativo = false WHERE id = :id'), {'id': superadmin.id}
        )
    assert cliente.post(url(a.loja.id), headers=sa).status_code == 401
    assert auditoria_do_acesso(engine_dono, a.loja.id) == []
