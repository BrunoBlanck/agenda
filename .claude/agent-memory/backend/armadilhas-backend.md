---
name: armadilhas-backend
description: Armadilhas técnicas confirmadas no back-end (concorrência, testes, limites, ferramentas) e como contorná-las
metadata:
  type: project
---

Armadilhas confirmadas em 2026-10-02 (correção da revisão A1–A12):

- **Teste de corrida precisa de servidor real.** O TestClient serializa; use a fixture de sessão `servidor` (uvicorn numa thread, `tests/conftest.py`) + `tests/concorrencia.py::rajada` (barreira + um httpx.Client por thread). Para provar que o teste pega o defeito sem tocar em `app/` (editar lá dispara o --reload da API do usuário): o uvicorn da fixture roda no mesmo processo do pytest, então um teste temporário em `tests/` com `monkeypatch.setattr(modulo_da_rota, 'buscar', ...)` desliga a trava; rode, confira que falha, apague o arquivo. Nunca git stash (proibido).
  **Why:** o revisor exige corrida real (LOG-02) e um teste que passa com e sem a trava não prova nada.
  **How to apply:** toda regra "verificar e gravar" nova ganha um teste em `tests/test_concorrencia.py`.

- **`FOR UPDATE` não aceita agregação** (`count(*)`): selecione os ids com `.with_for_update(of=Modelo)` ordenados por id e conte em Python. Com join, use `of=` para não travar a outra tabela. Depois de travar, use `execution_options(populate_existing=True)` para não ficar com a versão antiga no identity map.

- **Mudar para o mesmo status é no-op 200** (`mudar_status`): numa rajada de "concluir", as repetidas voltam 200, não 409. O que prova a correção é a contagem de movimentações, não o status HTTP.

- **TestClient tem IP "testclient"**, que `ip_da_requisicao` transforma em None → todos os testes caem no mesmo contador de limite (`SEM_IP`). O `limpar` do conftest apaga `limites.contadores`; para testar limite por IP use `TestClient(app, client=('203.0.113.x', 50000))` e baixe os limites com `monkeypatch.setattr(get_settings(), ...)`.

- **Schema `limites` é técnico**: fora das regras de tabela de negócio (sem controle/auditoria/RLS) e fora do `public`, então `test_migracoes` não o cobra. Contadores gravam por um engine próprio em AUTOCOMMIT (`get_engine_limites`), senão o rollback de um 401/404 apagaria a contagem.

- **Heredoc longo no Bash (Git Bash) truncou um arquivo de teste no meio** (parou em `['servico_nome`). Para criar arquivos de teste grandes use a ferramenta Write; heredoc só para trechos curtos.

- **Erro de lista grande do Pydantic é `too_long`**: já mapeado em `app/erros.py` ("Itens demais (máximo de N)."). Tipo de erro novo sem mapeamento vira "Valor inválido.".

- **Bloqueio de login nunca é só por conta** (revisão rodada 2, A18): um terceiro que sabe o e-mail tranca a conta para sempre renovando o bloqueio. A chave é conta + IP; o ataque distribuído fica com o limite global por IP. Teste "bloqueio renovado por terceiro" em `tests/test_limites.py`.
  **Why:** reprovado como bloqueante. **How to apply:** qualquer trava de conta nova precisa de teste com dois IPs.

- **Rota pega-tudo fora de /api (`/{slug}/{resto:path}`) muda o comportamento da API** (2026-10-03): `/api/x` inexistente viraria HTML, e `POST /api/x` viraria 405 (o Starlette prefere casamento parcial de caminho a 404). Solução em `app/routers/paginas.py`: conversor próprio (`register_url_convertor('segmento', ...)`, regex `(?!api(?:/|$))[^/]+`) e o router registrado por último. Teste em `tests/test_roteamento.py` com GET/POST/HEAD.
- **uvicorn atrás de proxy:** `--proxy-headers` + `FORWARDED_ALLOW_IPS` (padrão do uvicorn sem a variável: `127.0.0.1,::1`). Host/porta saem de `UVICORN_HOST`/`UVICORN_PORT` (click auto_envvar) se não forem passados no CMD. Com `-p 127.0.0.1:8000:8000` no Docker o remetente é o gateway (172.17.0.1), não 127.0.0.1.
- **Lista de constantes repetida em migração** (ex.: slugs reservados): teste compara com `pg_get_constraintdef` para não divergir.
- **Teste que depende da ordem por `criado_em`** (2026-10-03): o trigger de controle reescreve `criado_em` em todo UPDATE. Para fixar a data num teste, use `engine_dono` com `SET LOCAL session_replication_role = replica` na mesma transação (ver `tests/test_acessar_loja.py::mudar_criado_em`).
- **Comparar `expira_em` com o `exp` do JWT:** o JWT guarda segundos inteiros; `criar_token` já trunca `agora` para os dois baterem. Não compare com `datetime.now()` com microssegundos.
- **Formulário HTML que trata erro do banco e continua respondendo** (2026-10-04): depois de um flush que falhou (23P01), a transação da requisição fica abortada e o commit de `app.db.sessao` vira 500. Rode a gravação dentro de `db.begin_nested()` (savepoint): a falha desfaz só o pedido e a sessão segue para a consulta de "pedido repetido" e o redirecionamento (`app/routers/site/paginas.py`).
- **Nada de `git rm`/`git add` para apagar arquivo**: mexe no índice (proibido ao agente). Use `rm`; se tocar no índice sem querer, `git restore --staged <arquivo>` volta ao estado anterior.

- **Coluna nova num modelo quebra teste de migração antiga** (2026-10-05): o ORM manda todas as colunas no INSERT (NULL nas não preenchidas), então `criar_loja` (ORM) num banco em `0002`/`0004` falha com UndefinedColumn. Padrão: criar os dados em `head` e `command.downgrade` até a revisão antiga (feito em `test_0003...` e `test_migracao_para_se_alguma_loja_usa_slug_reservado`).
- **Teste flaky ≠ culpa da mudança:** para ter a linha de base sem git stash, `git archive HEAD backend | tar -x -C <scratch>` + copiar `.env` + `uv sync` e rodar o teste lá (mesmo banco de teste; apagar a cópia no fim).

Relacionado: [[contratos-alterados-revisao-1]]
