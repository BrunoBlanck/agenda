---
name: datas-controle-utc
description: Fuso das datas da API — o back-end responde tudo no fuso da loja; o front usa a hora escrita na string e só converte UTC ("Z")
metadata:
  type: project
---

Até 2026-10-02 as colunas de controle (`criado_em`, `atualizado_em`) saíam em UTC ("...Z"). O back-end passou a
responder tudo no fuso da loja (TimeZone da transação em `app/db.py`; SUPERADMIN converte por loja e usa
America/Sao_Paulo nos dados da plataforma). No front, `lerDataHora` (`data/api/conversao.js`) usa a hora escrita na
string quando há offset (nunca reconverte para um fuso global: errava lojas de outro fuso, achado A1 do revisor) e
só leva UTC ao fuso da sessão. `lerMomentoNaLoja`/`lerControle` ficam em `data/api/registro.js`.

**Why:** fuso é defeito recorrente (back e front); ver memória do revisor.
**How to apply:** nunca converta um ISO com offset para outro fuso na tela; teste com uma loja fora de
America/Sao_Paulo (ex.: America/Manaus) e o caminho ler → editar → salvar.
