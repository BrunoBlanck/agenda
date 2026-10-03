---
name: armadilhas-form-antd
description: Form.List dentro do PainelFormulario (preserve={false}) perde os valores quando os dados chegam depois da abertura; e como testar o painel no navegador sem login
metadata:
  type: project
---

`PainelFormulario` monta o `Form` com `preserve={false}`. Um `Form.List` preenchido depois da
abertura (ex.: materiais do agendamento, que só vêm no GET do detalhe) recria as linhas e os
`Form.Item` internos desmontam/remontam: com preserve=false os valores somem e a lista fica `[{}, {}]`
(confirmado em 2026-10-02 no AgendamentoPainel). Correção: `preserve` nos `Form.Item` das linhas.

**Why:** o defeito não aparece em lint/build nem em curl; só no navegador, com nomes "Material" e quantidades vazias.
**How to apply:** todo `Form.List` (ou campo condicional) cujo valor chega por `setFieldsValue` depois de abrir o painel.

Teste no navegador sem gastar tentativas de login (5 falhas bloqueiam o IP): playwright-core no scratchpad
com o Chromium de `%LOCALAPPDATA%/ms-playwright/chromium-*`, gravando o token em
`sessionStorage['agenda.sessao.loja']` via `addInitScript`. Ver [[integracao-agenda]].
