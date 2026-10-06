---
name: armadilhas-ambiente
description: Armadilhas do ambiente Windows/Git Bash e do pytest neste backend (fim de linha, resumo do pytest, fuso de teste)
metadata:
  type: project
---

- `sed -i` no Git Bash regrava o arquivo inteiro com LF; vários .py do backend estão com CRLF (core.autocrlf=true), então o diff vira o arquivo todo. Edite com Edit/Write ou Python (`open(..., 'w')` mantém CRLF no Windows), nunca `sed -i`.
- `pyproject.toml` já tem `addopts = "-q"`; `pytest -q` vira `-qq` e some a linha "N passed". Sem F/E nos pontos = passou; para contar, `pytest --collect-only -q`.
- Testar "hoje no fuso da loja" de forma determinística: trocar `lojas.fuso_horario` para `Pacific/Pago_Pago` (UTC-11) e `Pacific/Kiritimati` (UTC+14) via `engine_dono`; não depende da hora em que o teste roda.
- Lista de fusos do Postgres fica em cache no processo (`app.db._fusos_do_banco`); nos testes, `monkeypatch.setattr('app.db._fusos_do_banco', frozenset(...))` simula um fuso que o PG não conhece.

- Barra invertida + quebra de linha dentro de heredoc pela ferramenta Bash some (vira uma linha só com espaços): continuação de linha de Dockerfile/shell escreva com Edit/Write. O `RUN useradd ... &&` antigo do Dockerfile tinha sido estragado assim.
- Docker Desktop pode estar desligado (pipe dockerDesktopLinuxEngine não existe): `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`, esperar e `docker compose up -d` em backend/. Validar nginx sem instalar: `MSYS_NO_PATHCONV=1 docker run --rm -v "C:\...\deploy
ginx:/etc/nginx/conf.d:ro" nginx:stable-alpine nginx -t` (caminho Windows no -v). Teste de roteamento de ponta a ponta: trocar 127.0.0.1:8000 por host.docker.internal:<porta> numa cópia no scratchpad, `--add-host host.docker.internal:host-gateway`, uvicorn temporário com --host 0.0.0.0.
- `grep -c $'\r'` no Git Bash NÃO detecta CRLF (o grep tira o \r): conferir fim de linha com Python (`'\r\n' in open(p, newline='').read()`). Substituição por Python em arquivo CRLF: normalize para `\n`, troque e regrave com o fim de linha original. O git normaliza (autocrlf), então arquivo regravado em LF não vira diff inteiro.
- `uv` não está no PATH do Git Bash (nem do PowerShell da ferramenta): use `.venv\Scripts\python.exe -m pytest|ruff|uvicorn` em backend/. Suíte inteira leva ~9 min: rode com `run_in_background` (ou Wait-Process), o limite de 600 s do foreground estoura.
- Verificar o site no navegador: o `node_modules` com playwright-core pode ser copiado do scratchpad de outra sessão (`cp -r`); limites do site sobem por env (`LIMITE_SITE_POR_IP`, `LIMITE_SITE_PEDIDOS_POR_IP`) no uvicorn temporário. Ver [[verificacao-navegador-site]].

**Why:** perdi tempo com um `sed -i` que reescreveu `servicos.py` inteiro e com o resumo do pytest sumindo.
**How to apply:** antes de editar por shell e ao ler a saída do pytest.
