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

Confirmadas em 2026-10-06 (conta do cliente no site):

- **Cookie `Secure` no TestClient:** o cookie da sessão do cliente tem `Secure` fora de `AMBIENTE=desenvolvimento` (nos testes, `teste`). Com o `base_url` padrão (`http://testserver`) o httpx não guarda nem manda o cookie: use `TestClient(app, base_url='https://testserver')` (fixture `navegador` em `tests/test_conta_cliente.py`). O `mesma_origem` compara só o host, então `Origin: https://testserver` passa.
- **ruff PT018 nos testes:** `assert a and b` reprova no `ruff check`; quebre em vários `assert`.
- **`tests/test_saude.py::test_cors_libera_o_front_local` falha com o `.env` de dev atual** (`CORS_ORIGENS=["http://localhost:4824"]`, porta do front configurável): o teste espera `localhost:5173` (o do `.env.example`). Não é regressão; reportar e não mexer no `.env` do usuário.
- **Migração que muda função de trigger** (`registrar_auditoria`, `so_dados_de_login`): `CREATE OR REPLACE` com o corpo inteiro da versão anterior parametrizado, e o downgrade recria exatamente o corpo da migração anterior (ver 0004 e 0007). `jsonb - text[]` tira várias chaves de uma vez.
- **Dev DB precisa da migração nova** para a API de dev (com --reload) não dar 500 nas rotas novas: `.venv/Scripts/python.exe -m alembic upgrade head` em `backend/` (avisar no relatório).

Confirmadas em 2026-10-06 (conta do cliente, Fase B):

- **Heredoc truncou de novo** (~140 linhas anexadas com `cat >> ... <<'EOF'`): parou no meio de uma string. Para trechos grandes, Write num arquivo do scratchpad e anexe com Python.
- **Provar que o teste pega o defeito sem tocar em `app/`:** arquivo temporário `tests/test_tmp_*.py` que importa as funções de teste **e as fixtures do módulo delas** (senão dá ERROR de fixture) e um fixture autouse com `monkeypatch` desligando a regra; rodar, ver falhar, apagar.
- **Fixture `navegador`** (TestClient https) mora em `tests/conftest.py`; não importe fixture de outro módulo de teste nos testes definitivos (ruff F811/F401).
- **Corrida em página HTML com sessão:** o `servidor` é http; mande o cookie como cabeçalho `Cookie: sessao_cliente=<token>` (o `Secure` só vale para o navegador guardar). Helper `_postar_com_cookie` em `tests/test_conta_cliente_alterar.py`.
- **Forçar 23P01 de forma determinística:** monkeypatch da função de conferência do serviço (ex.: `conta_agendamentos.horario_oferecido`) chamando a original e, antes de devolver, inserindo o agendamento conflitante com `engine_dono` (outra conexão, já confirmada).
- **Nunca rode dois pytest ao mesmo tempo** (suíte inteira em background + um arquivo em primeiro plano): os dois usam o mesmo banco agenda_test e o limpar/recriar de um derruba o outro (55 ERROR falsos). Espere a suíte terminar; se precisar parar, TaskStop e mate só os processos pytest (Get-CimInstance Win32_Process), nunca o uvicorn da porta 4823.

Confirmadas em 2026-10-06 (revisão rodada 1 da conta do cliente):

- **Dígitos Unicode:** `str.isdigit()`, `\d` e `re.sub(r'\D', ...)` aceitam "²", "١" e "１"; `int('²')` levanta ValueError e `secrets.compare_digest` com não-ASCII levanta TypeError (500). `so_digitos` agora é `[^0-9]`; regex de data/hora com `re.ASCII`; número lido à mão com `re.fullmatch(r'[0-9]{1,N}', ...)`.
- **Advisory lock + FOR UPDATE = impasse se a ordem variar.** Na conta do cliente a ordem é sempre telefone (advisory) e depois linha (código/conta). Quem parte de um id assinado lê sem travar, trava o telefone e relê com FOR UPDATE + populate_existing. Argon2 antes de qualquer trava.
- **Erro de banco escapando numa página HTML virava JSON:** o tratador de DBAPIError em `app/erros.py` agora responde `erro.html` fora de /api.
- **Provar o teste de impasse:** monkeypatch de `conta.codigo_confirmado` travando o código com FOR UPDATE (a ordem antiga) faz `test_senha_e_novo_codigo_juntos_sem_impasse` falhar com 409.

Confirmadas em 2026-10-06 (notificações):

- **Editar arquivos por Python no Bash:** heredoc com `\n` dentro de string Python vira quebra de linha de verdade (arquivo quebrado). Padrão que funcionou: script `editar.py` no scratchpad que lê uma lista `EDICOES = [(arquivo, [(velho, novo), ...])]` de outro .py escrito com Write (preserva CRLF, falha se o trecho não existir).
- **INSERT com `criado_em` explícito é reescrito pelo trigger** (não só o UPDATE): para fixar datas num teste, `SET LOCAL session_replication_role = replica` na mesma transação do INSERT.
- **Pedido do site sem `local_id` pega o primeiro local em ordem alfabética** ("Online" antes de "Sala 1" na clínica dos testes): teste que confere texto com o local precisa mandar `local_id`/`local`.
- **`db.commit()` dentro da rota com `DbDep` funciona** (o `with db.begin()` da dependência vê a transação fechada e não commita de novo), desde que nada mais use o banco depois. Usado para enviar e-mail (rede) sem transação aberta (PER-05).
- **`TestClient(app)` como context manager roda o lifespan**: tarefa de fundo nova precisa ficar desligada em `AMBIENTE=teste` (senão roda durante os testes).
- **Prova de teste de concorrência da fila:** com SKIP LOCKED + releitura do WHERE após o lock, o que impede envio duplicado é a reserva (próxima tentativa no futuro); o teste que pega o defeito é o de um segundo ciclo começando *durante* o envio do primeiro (`test_outro_processo_durante_o_envio_nao_pega_os_reservados`).
- **Revisão rodada 1 das notificações (2026-10-06):** tempo limite de socket é por operação (servidor que goteja 1 byte/s nunca estoura) → prazo total com um vigia (`threading.Timer` que fecha o socket). Reserva de fila calculada com o `agora` do início do ciclo é bug (ciclo longo = reserva já vencida): use o relógio na hora da reserva e confira um token (tentativa + data da reserva) ao gravar o resultado. Em testes com `agora` simulado em 2030, comparações com `criado_em` (hora real do banco) precisam do relógio real, não do simulado. Porta de SMTP de teste precisa passar no CHECK (25/465/587/2525): o servidor lento do teste usa 2525.
- **Rodada 2 (A6): prazo total com TLS.** `wrap_socket` faz `detach()` do socket TCP na criação (antes do handshake): fechar/derrubar o socket bruto depois disso não faz nada. Registre o `SSLSocket` antes do handshake (`do_handshake_on_connect=False` + `do_handshake()` manual, via um contexto embrulhado passado ao smtplib) e derrube com `shutdown(SHUT_RDWR)`. O CPython dá ao handshake inteiro o tempo limite do socket como prazo: um teste de handshake travado só pega o defeito se o prazo já tiver sido gasto antes (saudação lenta) — com prazo == tempo limite, passa até sem a correção.

Confirmadas em 2026-10-07 (pagamento do atendimento):

- **Provar a segunda barreira (índice único) de um "verificar e gravar":** teste definitivo com `monkeypatch.setattr(regras, 'buscar_visivel', lambda ctx, i, travar=False: original(ctx, i))` (desliga o FOR UPDATE no uvicorn da fixture `servidor`) + `rajada`; para provar que ele pega o defeito, arquivo temporário que importa o teste com nome `test_*` (senão não é coletado) e um fixture autouse que faz `DROP INDEX` pelo `engine_dono` e recria no teardown (depois de apagar as linhas). Sem o índice, todos voltam 200.
- **Erros do Pydantic para Decimal** (`decimal_max_places`, `decimal_whole_digits`, `decimal_max_digits`, `decimal_type`, `finite_number`) agora têm mensagem em `app/erros.py`; tipo novo sem mapeamento cai em "Valor inválido.".
- **Contar consultas (PER-01) num teste:** `event.listen(engine_app, 'before_cursor_execute', ...)` em volta de uma chamada do TestClient; compare a contagem com 1 e com N itens (não um número fixo, que quebra quando auth/contexto muda).
