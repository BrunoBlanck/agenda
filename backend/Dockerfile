# Imagem simples da API (funciona em x86 e ARM). Configuração só por variáveis de ambiente.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

RUN useradd --system --uid 10001 agenda \
    && mkdir -p /app/arquivos && chown agenda /app/arquivos
# Logos enviadas pelas lojas (ARQUIVOS_DIR): monte um volume persistente aqui
VOLUME ["/app/arquivos"]
USER agenda

# Atrás do nginx (deploy/nginx/agenda.conf): --proxy-headers faz o uvicorn usar o X-Forwarded-For e o
# X-Forwarded-Proto, mas só de quem está em FORWARDED_ALLOW_IPS (IPs do proxy, separados por vírgula).
# Qualquer outro remetente tem os cabeçalhos ignorados. O IP real do cliente vale para a auditoria e para
# o limite de requisições (app/limites.py). Endereço e porta: UVICORN_HOST e UVICORN_PORT.
ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--proxy-headers"]
