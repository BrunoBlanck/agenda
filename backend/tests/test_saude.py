def test_saude_responde_ok(cliente):
    resposta = cliente.get('/api/saude')
    assert resposta.status_code == 200
    assert resposta.json() == {'status': 'ok'}


def test_rota_inexistente_responde_em_portugues(cliente):
    resposta = cliente.get('/api/nao-existe')
    assert resposta.status_code == 404
    assert resposta.json() == {'detail': 'Não encontrado.'}


def test_cors_libera_o_front_local(cliente):
    resposta = cliente.options(
        '/api/saude',
        headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET'},
    )
    assert resposta.headers.get('access-control-allow-origin') == 'http://localhost:5173'


def test_validacao_responde_em_portugues_por_campo(cliente):
    resposta = cliente.post('/api/loja/auth/login', json={'slug': 'x', 'email': 'nao-e-email'})
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo['detail'] == 'Verifique os dados informados.'
    assert {'campo': 'email', 'mensagem': 'E-mail inválido.'} in corpo['erros']
    assert {'campo': 'senha', 'mensagem': 'Campo obrigatório.'} in corpo['erros']
