"""Respostas de erro em português, prontas para mostrar ao usuário.

Nada aqui registra valores enviados pelo usuário (CPF, telefone, senha...): só o tipo do erro.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger('app.erros')

# Mensagens padrão do Starlette/FastAPI (em inglês) traduzidas
MENSAGENS_HTTP = {
    400: 'Requisição inválida.',
    401: 'Faça login para continuar.',
    403: 'Você não tem permissão para esta ação.',
    404: 'Não encontrado.',
    405: 'Método não permitido.',
    409: 'Conflito com dados existentes.',
    413: 'O envio passou do tamanho máximo permitido.',
    422: 'Verifique os dados informados.',
    429: 'Muitas requisições. Aguarde um pouco e tente novamente.',
    500: 'Erro interno. Tente novamente em instantes.',
}

MENSAGENS_VALIDACAO = {
    'missing': 'Campo obrigatório.',
    'string_too_short': 'Texto muito curto (mínimo de {min_length} caractere(s)).',
    'string_too_long': 'Texto muito longo (máximo de {max_length} caracteres).',
    'string_type': 'Informe um texto.',
    'int_parsing': 'Informe um número inteiro.',
    'int_type': 'Informe um número inteiro.',
    'float_parsing': 'Informe um número.',
    'decimal_parsing': 'Informe um número.',
    'bool_parsing': 'Informe verdadeiro ou falso.',
    'greater_than_equal': 'O valor deve ser maior ou igual a {ge}.',
    'greater_than': 'O valor deve ser maior que {gt}.',
    'less_than_equal': 'O valor deve ser menor ou igual a {le}.',
    'less_than': 'O valor deve ser menor que {lt}.',
    'uuid_parsing': 'Identificador inválido.',
    'uuid_type': 'Identificador inválido.',
    'date_from_datetime_parsing': 'Data inválida.',
    'date_parsing': 'Data inválida.',
    'datetime_parsing': 'Data e hora inválidas.',
    'datetime_from_date_parsing': 'Data e hora inválidas.',
    'time_parsing': 'Horário inválido.',
    'enum': 'Opção inválida.',
    'literal_error': 'Opção inválida.',
    'json_invalid': 'O corpo da requisição não é um JSON válido.',
    'model_attributes_type': 'Formato inválido.',
    'dict_type': 'Formato inválido.',
    'list_type': 'Informe uma lista.',
    'too_long': 'Itens demais (máximo de {max_length}).',
    'too_short': 'Itens de menos (mínimo de {min_length}).',
    'extra_forbidden': 'Campo não permitido.',
}


def _mensagem_validacao(erro: dict) -> str:
    tipo = erro.get('type', '')
    if tipo == 'regra':  # app.schemas.comum.regra: mensagem já em português
        return str(erro.get('msg', ''))
    if tipo == 'value_error' and 'email' in str(erro.get('msg', '')).lower():
        return 'E-mail inválido.'
    modelo = MENSAGENS_VALIDACAO.get(tipo)
    if modelo is None:
        return 'Valor inválido.'
    try:
        return modelo.format(**(erro.get('ctx') or {}))
    except (KeyError, IndexError):
        return modelo


def _campo(local: tuple | list) -> str:
    partes = [str(p) for p in local if p not in ('body', 'query', 'path', 'header')]
    return '.'.join(partes) or 'corpo'


MSG_FORA_DO_LIMITE = 'Valor fora do limite permitido.'
MSG_MULTIPART_INVALIDO = 'O envio do arquivo veio incompleto ou mal formado. Tente enviar de novo.'
MSG_TENTE_DE_NOVO = 'Outra alteração foi feita ao mesmo tempo e esta não foi salva. Tente novamente.'

# SQLSTATE do Postgres -> (status HTTP, mensagem)
ERROS_BANCO = {
    '23505': (status.HTTP_409_CONFLICT, 'Já existe um cadastro com esses dados.'),
    '23503': (status.HTTP_422_UNPROCESSABLE_CONTENT, 'Registro relacionado não encontrado.'),
    '23502': (status.HTTP_422_UNPROCESSABLE_CONTENT, 'Há um campo obrigatório sem valor.'),
    '23514': (status.HTTP_422_UNPROCESSABLE_CONTENT, 'Os dados informados não são válidos.'),
    '23P01': (status.HTTP_409_CONFLICT, 'Horário indisponível: já existe um agendamento nesse período.'),
    '42501': (status.HTTP_403_FORBIDDEN, 'Operação não permitida.'),
    # Duas transações disputando as mesmas linhas (deadlock ou falha de serialização): nada foi gravado
    '40P01': (status.HTTP_409_CONFLICT, MSG_TENTE_DE_NOVO),
    '40001': (status.HTTP_409_CONFLICT, MSG_TENTE_DE_NOVO),
    # Rede de segurança: valores e datas fora do que o banco suporta (a validação de entrada já barra)
    '22003': (status.HTTP_422_UNPROCESSABLE_CONTENT, MSG_FORA_DO_LIMITE),
    '22008': (status.HTTP_422_UNPROCESSABLE_CONTENT, 'Data fora do limite permitido.'),
}


# Mensagens específicas por constraint/índice (nome no banco). Têm prioridade sobre ERROS_BANCO.
MENSAGENS_CONSTRAINT = {
    'agendamentos_sem_conflito': 'O profissional já tem um agendamento nesse horário.',
    'agendamentos_local_sem_conflito': 'Este local já está ocupado nesse horário.',
    'clientes_cpf_uk': 'Já existe um cliente com este CPF.',
    'funcionarios_email_uk': 'Já existe um funcionário com este e-mail.',
    'funcionarios_cpf_uk': 'Já existe um funcionário com este CPF.',
    'perfis_nome_uk': 'Já existe um perfil com este nome.',
    'cargos_nome_uk': 'Já existe um cargo com este nome.',
    'servicos_nome_uk': 'Já existe um serviço com este nome.',
    'locais_nome_uk': 'Já existe um local com este nome.',
    'materiais_nome_uk': 'Já existe um material com este nome.',
    'categorias_material_nome_uk': 'Já existe uma categoria com este nome.',
    'lojas_cnpj_uk': 'Este CNPJ já está cadastrado em outra loja.',
    'lojas_slug_uk': 'Este endereço de acesso já está em uso por outra loja.',
    'planos_nome_uk': 'Já existe um plano com este nome.',
    'superadmin_usuarios_email_uk': 'Já existe um usuário admin com este e-mail.',
    'registros_ponto_um_aberto': 'Este funcionário já tem um registro de ponto em aberto.',
    'registros_ponto_sem_sobreposicao': 'Este funcionário já tem um registro de ponto nesse período.',
}


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detalhe = exc.detail
        # Mensagem padrão em inglês (ex.: "Not Found") vira português
        if not isinstance(detalhe, str) or detalhe == HTTPStatus(exc.status_code).phrase:
            detalhe = MENSAGENS_HTTP.get(exc.status_code, 'Não foi possível concluir a operação.')
        elif exc.status_code == 400 and 'multipart' in detalhe.lower():
            # Erros do parser de multipart do Starlette (em inglês): ex. "Invalid multipart data."
            detalhe = MSG_MULTIPART_INVALIDO
        return JSONResponse({'detail': detalhe}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        erros = [
            {'campo': _campo(e.get('loc', ())), 'mensagem': _mensagem_validacao(e)} for e in exc.errors()
        ]
        return JSONResponse(
            {'detail': MENSAGENS_HTTP[422], 'erros': erros}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(OverflowError)
    async def estouro(_: Request, exc: OverflowError) -> JSONResponse:
        # Ex.: soma de data passando do ano 9999. A validação de entrada (app.schemas.comum.Data) já barra
        log.info('Estouro de valor tratado (%s)', type(exc).__name__)
        return JSONResponse({'detail': MSG_FORA_DO_LIMITE}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(DBAPIError)
    async def banco(_: Request, exc: DBAPIError) -> JSONResponse:
        sqlstate = getattr(exc.orig, 'sqlstate', None)
        if sqlstate not in ERROS_BANCO:
            log.error('Erro de banco não tratado (SQLSTATE %s)', sqlstate)
            return JSONResponse({'detail': MENSAGENS_HTTP[500]}, status_code=500)
        codigo, mensagem = ERROS_BANCO[sqlstate]
        diag = getattr(exc.orig, 'diag', None)
        # Erros levantados pelas nossas funções (RAISE EXCEPTION) já vêm em português e sem dados
        # pessoais; os das constraints vêm em inglês e com valores, então usam a mensagem genérica.
        if (
            sqlstate in ('23514', '42501')
            and diag is not None
            and diag.constraint_name is None
            and diag.message_primary
        ):
            mensagem = diag.message_primary
        constraint = getattr(diag, 'constraint_name', None)
        if constraint in MENSAGENS_CONSTRAINT:
            mensagem = MENSAGENS_CONSTRAINT[constraint]
        log.info(
            'Erro de banco tratado (SQLSTATE %s, constraint %s)',
            sqlstate,
            getattr(diag, 'constraint_name', None),
        )
        return JSONResponse({'detail': mensagem}, status_code=codigo)
