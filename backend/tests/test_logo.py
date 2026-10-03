"""Logo da loja: envio (painel e superadmin), remoção, rota pública e segurança do upload (SEG-13)."""

import io
import re
import uuid

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.db import definir_contexto, get_sessionmaker
from app.models import Loja
from app.services.arquivos import pasta_logos, trocar_logo
from tests.fabricas import cabecalho_superadmin, criar_superadmin, sessao, usuario_com

URL = '/api/loja/configuracoes/loja/logo'
MAXIMO = 2 * 1024 * 1024

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 64
WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + b'\x00' * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
GIF = b'GIF89a' + b'\x00' * 64

MSG_FORMATO = 'Formato não aceito. Envie uma imagem PNG, JPEG ou WebP.'


def _enviar(cliente, cabecalho, conteudo: bytes, *, nome='logo.png', tipo='image/png', url=URL):
    return cliente.put(url, files={'arquivo': (nome, conteudo, tipo)}, headers=cabecalho)


def _arquivos(loja_id) -> list[str]:
    pasta = pasta_logos(loja_id)
    return sorted(p.name for p in pasta.iterdir()) if pasta.exists() else []


def _logo_url(engine, loja_id) -> str | None:
    with engine.connect() as conexao:
        return conexao.execute(select(Loja.logo_url).where(Loja.id == loja_id)).scalar()


@pytest.mark.parametrize(
    ('conteudo', 'extensao', 'tipo'),
    [(PNG, 'png', 'image/png'), (JPEG, 'jpg', 'image/jpeg'), (WEBP, 'webp', 'image/webp')],
)
def test_enviar_logo_e_servir_pela_rota_publica(cliente, lojas, conteudo, extensao, tipo):
    a, _ = lojas
    # Extensão e content-type do cliente não importam: vale a assinatura do arquivo
    resposta = _enviar(cliente, a.h_admin, conteudo, nome='../../qualquer.exe', tipo='text/html')
    assert resposta.status_code == 200, resposta.json()
    corpo = resposta.json()
    assert re.fullmatch(rf'/api/arquivos/logos/{a.loja.id}/[0-9a-f]{{32}}\.{extensao}', corpo['logo_url'])
    assert corpo['atualizado_por'] == str(a.admin.id)
    assert _arquivos(a.loja.id) == [corpo['logo_url'].rsplit('/', 1)[1]]

    publica = cliente.get(corpo['logo_url'])  # sem login
    assert publica.status_code == 200
    assert publica.content == conteudo
    assert publica.headers['content-type'] == tipo
    assert publica.headers['x-content-type-options'] == 'nosniff'
    assert 'immutable' in publica.headers['cache-control']
    assert 'sandbox' in publica.headers['content-security-policy']
    assert cliente.get(URL.removesuffix('/logo'), headers=a.h_admin).json()['logo_url'] == corpo['logo_url']


@pytest.mark.parametrize(
    'conteudo',
    [SVG, GIF, b'texto qualquer', b'', b'\x89PN'],
    ids=['svg', 'gif', 'texto', 'vazio', 'png-cortado'],
)
def test_formato_recusado_pelos_bytes(cliente, lojas, engine_dono, conteudo):
    a, _ = lojas
    resposta = _enviar(cliente, a.h_admin, conteudo, nome='logo.png', tipo='image/png')
    assert resposta.status_code == 422
    assert resposta.json()['detail'] == MSG_FORMATO
    assert _arquivos(a.loja.id) == []
    assert _logo_url(engine_dono, a.loja.id) is None


def test_sem_o_campo_arquivo(cliente, lojas):
    a, _ = lojas
    resposta = cliente.put(URL, files={'outro': ('x.png', PNG, 'image/png')}, headers=a.h_admin)
    assert resposta.status_code == 422
    assert resposta.json()['erros'] == [{'campo': 'arquivo', 'mensagem': 'Campo obrigatório.'}]


def test_tamanho_maximo(cliente, lojas, engine_dono):
    a, _ = lojas
    # No limite: aceita
    assert _enviar(cliente, a.h_admin, PNG + b'\x00' * (MAXIMO - len(PNG))).status_code == 200
    url = _logo_url(engine_dono, a.loja.id)
    # Um byte a mais: 413 com a mensagem da rota, nada muda
    grande = _enviar(cliente, a.h_admin, PNG + b'\x00' * (MAXIMO - len(PNG) + 1))
    assert grande.status_code == 413
    assert grande.json()['detail'] == 'A imagem deve ter no máximo 2 MB.'
    # Muito maior: o middleware recusa pelo Content-Length, sem ler o corpo
    enorme = _enviar(cliente, a.h_admin, PNG + b'\x00' * (3 * MAXIMO))
    assert enorme.status_code == 413
    assert enorme.json()['detail'] == 'O envio passou do tamanho máximo permitido.'
    assert _logo_url(engine_dono, a.loja.id) == url
    assert len(_arquivos(a.loja.id)) == 1


def test_corpo_sem_content_length_tambem_tem_limite(cliente, lojas):
    """Envio em partes (sem Content-Length): o middleware conta os bytes recebidos."""
    a, _ = lojas

    def partes():
        for _ in range(5):
            yield b'x' * MAXIMO

    resposta = cliente.put(
        URL,
        content=partes(),
        headers={**a.h_admin, 'Content-Type': 'multipart/form-data; boundary=limite'},
    )
    assert resposta.status_code == 413
    assert resposta.json()['detail'] == 'O envio passou do tamanho máximo permitido.'
    # O limite também vale para as rotas com JSON
    json_grande = cliente.put(
        '/api/loja/configuracoes/loja',
        content=b'{"nome": "' + b'x' * (3 * MAXIMO) + b'"}',
        headers={**a.h_admin, 'Content-Type': 'application/json'},
    )
    assert json_grande.status_code == 413


def test_trocar_apaga_a_anterior_e_remover_apaga_o_arquivo(cliente, lojas, engine_dono):
    a, _ = lojas
    primeira = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    segunda = _enviar(cliente, a.h_admin, JPEG).json()['logo_url']
    assert primeira != segunda
    assert _arquivos(a.loja.id) == [segunda.rsplit('/', 1)[1]]
    assert cliente.get(primeira).status_code == 404
    assert cliente.get(segunda).status_code == 200

    assert cliente.delete(URL, headers=a.h_admin).status_code == 204
    assert _logo_url(engine_dono, a.loja.id) is None
    assert _arquivos(a.loja.id) == []
    assert cliente.get(segunda).status_code == 404
    # Remover sem logo: continua 204
    assert cliente.delete(URL, headers=a.h_admin).status_code == 204


def test_envio_fica_na_auditoria(cliente, lojas, engine_dono):
    a, _ = lojas
    url = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    with engine_dono.connect() as conexao:
        linha = conexao.execute(
            text(
                "SELECT funcionario_id, campos_alterados, depois ->> 'logo_url' FROM auditoria"
                " WHERE tabela = 'lojas' ORDER BY id DESC LIMIT 1"
            )
        ).one()
    assert tuple(linha) == (a.admin.id, ['logo_url'], url)


def test_permissoes(cliente, lojas, engine_dono):
    a, _ = lojas
    leitor = usuario_com(engine_dono, a.loja, {'config_loja': 'leitura'})
    for cabecalho in (a.h_recepcao, a.h_prof, leitor):
        assert _enviar(cliente, cabecalho, PNG).status_code == 403
        assert cliente.delete(URL, headers=cabecalho).status_code == 403
    assert _enviar(cliente, leitor, PNG).json()['detail'] == 'Você só tem permissão de leitura aqui.'
    assert _enviar(cliente, {}, PNG).status_code == 401
    assert _arquivos(a.loja.id) == []


def test_isolamento_entre_lojas(cliente, lojas, engine_dono):
    a, b = lojas
    url_a = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    url_b = _enviar(cliente, b.h_admin, PNG).json()['logo_url']
    assert f'/{b.loja.id}/' in url_b
    assert cliente.delete(URL, headers=b.h_admin).status_code == 204
    assert _logo_url(engine_dono, a.loja.id) == url_a
    assert cliente.get(url_a).status_code == 200
    # Uma URL de outra loja gravada na loja A nunca leva a apagar o arquivo da outra loja
    url_b = _enviar(cliente, b.h_admin, PNG).json()['logo_url']
    with sessao(engine_dono) as db:
        db.get(Loja, a.loja.id).logo_url = url_b
    _enviar(cliente, a.h_admin, JPEG)
    assert cliente.get(url_b).status_code == 200


@pytest.mark.parametrize(
    'caminho',
    [
        '{loja}/..%2F..%2F..%2Fpyproject.toml',
        '{loja}/../{nome}',
        'nao-e-uuid/{nome}',
        '{loja}/{nome_maiusculo}',
        '{loja}/{nome_sem_extensao}',
        '{loja}/0123456789abcdef0123456789abcdef.svg',
        '{loja}/0123456789abcdef0123456789abcdef.png',
    ],
)
def test_rota_publica_so_serve_nomes_gerados(cliente, lojas, caminho):
    a, _ = lojas
    nome = _enviar(cliente, a.h_admin, PNG).json()['logo_url'].rsplit('/', 1)[1]
    url = '/api/arquivos/logos/' + caminho.format(
        loja=a.loja.id,
        nome=nome,
        nome_maiusculo=nome.upper(),
        nome_sem_extensao=nome.removesuffix('.png'),
    )
    resposta = cliente.get(url)
    assert resposta.status_code == 404
    assert resposta.headers['content-type'].startswith('application/json')


def test_superadmin_envia_e_remove_a_logo(cliente, lojas, engine_dono):
    a, _ = lojas
    h = cabecalho_superadmin(criar_superadmin(engine_dono))
    url = f'/api/superadmin/lojas/{a.loja.id}/logo'
    resposta = _enviar(cliente, h, WEBP, url=url)
    assert resposta.status_code == 200, resposta.json()
    logo = resposta.json()['logo_url']
    assert logo.endswith('.webp')
    assert cliente.get(logo).status_code == 200
    # O painel da loja vê a mesma logo; a alteração do superadmin fica sem autor (GER-13)
    dados = cliente.get('/api/loja/configuracoes/loja', headers=a.h_admin).json()
    assert (dados['logo_url'], dados['atualizado_por']) == (logo, None)

    assert _enviar(cliente, h, SVG, url=url).status_code == 422
    assert cliente.delete(url, headers=h).status_code == 204
    assert _arquivos(a.loja.id) == []
    # Loja inexistente: 404; token da loja não vale na área do superadmin
    outra = '/api/superadmin/lojas/00000000-0000-0000-0000-000000000000/logo'
    assert _enviar(cliente, h, PNG, url=outra).status_code == 404
    assert _enviar(cliente, a.h_admin, PNG, url=url).status_code == 401


def test_transacao_desfeita_apaga_o_arquivo_novo_e_mantem_o_antigo(cliente, lojas):
    a, _ = lojas
    antiga = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    contexto = {'funcionario_id': a.admin.id, 'loja_id': a.loja.id}
    with get_sessionmaker()() as db:
        db.begin()
        definir_contexto(db, origem='painel', **contexto)
        nova = trocar_logo(db, a.loja.id, io.BytesIO(JPEG)).logo_url
        assert len(_arquivos(a.loja.id)) == 2
        db.rollback()  # ex.: erro depois de gravar o arquivo
    assert _arquivos(a.loja.id) == [antiga.rsplit('/', 1)[1]]
    assert nova != antiga
    assert cliente.get(antiga).status_code == 200


def test_pasta_de_arquivos_vem_da_configuracao():
    assert 'agenda-arquivos-' in str(get_settings().arquivos_dir)  # testes nunca gravam em backend/arquivos


def test_rota_publica_responde_head(cliente, lojas):
    a, _ = lojas
    url = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    resposta = cliente.head(url)
    assert resposta.status_code == 200
    assert resposta.headers['content-type'] == 'image/png'
    assert resposta.content == b''


@pytest.mark.parametrize(
    'alteracao',
    ["status = 'suspensa'", "status = 'cancelada'", 'excluido_em = now()'],
    ids=['suspensa', 'cancelada', 'excluida'],
)
def test_logo_de_loja_que_nao_esta_ativa_responde_404(cliente, lojas, engine_dono, alteracao):
    """GER-25: loja fora do ar não tem a logo servida, e a resposta não diz o motivo."""
    a, b = lojas
    url = _enviar(cliente, a.h_admin, PNG).json()['logo_url']
    url_b = _enviar(cliente, b.h_admin, PNG).json()['logo_url']
    with engine_dono.begin() as conexao:
        conexao.execute(text(f'UPDATE lojas SET {alteracao} WHERE id = :i'), {'i': a.loja.id})
    for resposta in (cliente.get(url), cliente.head(url)):
        assert resposta.status_code == 404
    assert cliente.get(url).json() == {'detail': 'Arquivo não encontrado.'}
    assert cliente.get(url_b).status_code == 200  # a outra loja continua com a logo
    if alteracao != 'excluido_em = now()':  # religada, a logo volta (o arquivo não foi apagado)
        with engine_dono.begin() as conexao:
            conexao.execute(text("UPDATE lojas SET status = 'ativa' WHERE id = :i"), {'i': a.loja.id})
        assert cliente.get(url).status_code == 200


def test_logo_de_loja_inexistente_responde_404(cliente):
    url = f'/api/arquivos/logos/{uuid.uuid4()}/{"0" * 32}.png'
    assert cliente.get(url).status_code == 404


def test_multipart_mal_formado_responde_em_portugues(cliente, lojas):
    a, _ = lojas
    resposta = cliente.put(
        URL,
        content=b'--fim\r\nnada que preste',
        headers={**a.h_admin, 'Content-Type': 'multipart/form-data; boundary=fim'},
    )
    assert resposta.status_code == 400
    assert resposta.json() == {
        'detail': 'O envio do arquivo veio incompleto ou mal formado. Tente enviar de novo.'
    }
