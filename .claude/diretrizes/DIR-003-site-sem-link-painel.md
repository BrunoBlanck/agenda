---
id: DIR-003
titulo: Site do consumidor sem caminho para o painel
status: ativa
escopo: [backend, frontend-ui, frontend-dev, revisor, coordenador]
onde: backend/app/templates/**, backend/app/routers/paginas.py, backend/app/routers/site/**, qualquer tela futura do site do consumidor (/{slug}...)
criada_em: 2026-10-03
substitui: —
---

## Ordem do usuário
"No app do cliente final tem um botão para ir para loja, isso é errado, não pode mesmo." (2026-10-03)

## Regra
O site do consumidor (`/{slug}` e tudo que for público para o cliente final) **nunca** mostra botão, link, menu, rodapé ou texto que leve ao painel da loja (`/{slug}/painel`), ao login de funcionário ou ao SUPERADMIN. Também não expõe esses endereços em `href`, metadados, `sitemap`, `robots.txt` ou JSON público (`/api/site/...`). O funcionário chega ao painel digitando o endereço ou pelo próprio favorito.

## Exceções
- A página 404 genérica de `/painel` (sem loja), que só aparece para quem digitou `/painel`, pode dizer em texto (sem link) que o painel fica em `/nome-da-loja/painel`. Não é página de nenhuma loja.
- O painel e o SUPERADMIN podem linkar para o site (o caminho proibido é só site → painel).

## Como verificar
- `grep -rniE "painel|superadmin|login" backend/app/templates/` → nenhum resultado.
- `grep -rniE "/painel|superadmin" backend/app/routers/site/ backend/app/schemas/site.py` → nenhum endereço do painel numa resposta pública.
- Tela nova do site do consumidor: nenhum link para `/{slug}/painel` no HTML gerado (teste no `test_roteamento.py`/teste do site: `'/painel' not in resposta.text`).

## Aplicação no código existente
- [x] Protótipo React do site (`frontend/src/site/`, tinha "Ir para o painel") removido na funcionalidade `roteamento-url` (2026-10-03).
- [x] Página provisória `/{slug}` (`backend/app/templates/loja.html`, `base.html`): sem link para o painel (conferido por grep, 2026-10-03).
- [x] Teste automatizado garantindo que `GET /{slug}` não contém `/painel`, `superadmin` nem `login`: `backend/tests/test_roteamento.py::test_pagina_da_loja_nao_leva_ao_painel_nem_ao_login` (funcionalidade `acessar-loja`, 2026-10-03).
