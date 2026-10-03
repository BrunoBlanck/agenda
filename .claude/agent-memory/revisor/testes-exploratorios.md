---
name: testes-exploratorios
description: Como rodar testes exploratórios do revisor fora do repositório, reaproveitando as fixtures do backend (inclusive concorrência real)
metadata:
  type: reference
---

Testes exploratórios ficam no scratchpad (fora do repo) e reaproveitam `backend/tests/conftest.py` como plugin:

`cd backend && uv run python -m pytest <arquivo fora do repo> -p tests.conftest -c pyproject.toml --rootdir . -p no:cacheprovider -q -s`

- Fixtures úteis: `cliente`, `lojas` (loja-a/loja-b com Admin, Recepção, Profissional), `engine_dono`; `tests.clinica.montar_clinica(cliente, lojas[0])`; `tests.fabricas.usuario_com(engine, loja, {'recurso': 'nivel'})` e `cabecalho(funcionario)`.
- Para ver 500 em vez de exceção: `TestClient(app, raise_server_exceptions=False)`.
- Concorrência real: subir `uvicorn.Server` numa thread (porta 8765) dentro do teste e disparar com `httpx` + `threading.Barrier`; o `TestClient` é sequencial e não reproduz corrida.

- O `conftest` já tem a fixture `servidor` (sessão) e `tests/concorrencia.py` (`rajada`); uma fixture local com outro nome/porta evita conflito.
- Limites de login/site: os contadores ficam em `limites.contadores` (apagados pelo `limpar`). No TestClient o IP é inválido, então tudo cai na chave "desconhecido". Para testar bloqueio sem esperar minutos, altere `get_settings().login_bloqueio_*` no teste e chame `get_settings.cache_clear()` no fim.
- **Nunca** rodar os exploratórios ao mesmo tempo que o `pytest` do projeto: os dois recriam e limpam o mesmo `agenda_test` e geram falhas falsas (IntegrityError/OperationalError). Rode em sequência.
- O `addopts = "-q"` do projeto somado a `-q` esconde o resumo; use `-o addopts=""` para ver "N passed".
- IP por requisição no TestClient: `TestClient(app, client=('203.0.113.5', 50000))`.
- Migração: rodar `alembic upgrade/downgrade` num banco temporário criado pelo dono (`PYTHONPATH=.` ao rodar script fora do repo).
- **API local já de pé (rodada de integração):** script httpx no scratchpad contra `http://localhost:8000/api`, logins do seed (superadmin `rafael@agendaplataforma.com`/`superadmin123`; loja por `slug`+e-mail/`senha123`). Para provar fuso, trocar a `escola-harmonia` para America/Manaus via `PUT /superadmin/lojas/{id}` (corpo com todos os campos de `LojaEntrada`) e **restaurar no fim**. Front: `node` importando `frontend/src/data/api/conversao.js` por `file:///` com `TZ=` variado.

Relacionado: [[defeitos-recorrentes]].
