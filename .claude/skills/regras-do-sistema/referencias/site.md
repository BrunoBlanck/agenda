# Site do consumidor (`SIT-*`)

Fonte: `estrutura.md` 1.2, 2.13, 6.2 e o README. Rotas públicas em `/api/site/{slug}/...`. A versão final é **HTML renderizado pelo back-end Python** (um modelo por tipo de loja); `frontend/src/site/` é só protótipo de fluxo.

- **SIT-01** Público, sem login, identificado pelo `slug`. Loja inexistente, excluída, suspensa ou cancelada: **404** em todas as rotas (não revela que existe).
- **SIT-02** Expõe só o necessário: dados públicos da loja, serviços ativos com profissionais habilitados, locais ativos (id, nome, tipo; **sem link**), horários livres e o pedido de agendamento. Nada de dados de clientes.
- **SIT-03** Fluxo: serviço → profissional (opcional, "qualquer um") → dia e horário → dados do cliente → confirmação.
- **SIT-04** **Horários livres** calculados no servidor com as mesmas regras do painel (jornada, bloqueios, ocupação, local permitido e livre). Provisório: passos de 30 min, 60 min de antecedência, até 31 dias por consulta. "Qualquer profissional" = primeiro livre em ordem alfabética; com Locais, o primeiro local permitido e livre (alfabética).
- **SIT-05** O pedido só é aceito num horário **oferecido**; manda `funcionario_id`, `inicio` e opcionalmente `local_id`. A corrida entre dois pedidos é recusada pelo banco (409).
- **SIT-06** Pedido vira agendamento `pendente`, `origem = site`, preço congelado, local reservado, materiais copiados; contexto `app.origem = 'site'` sem funcionário. **Pendente já ocupa o horário e o local.** A loja aceita (`confirmado`) ou recusa (`cancelado` com motivo), AGE-17.
- **SIT-07** Cliente identificado pelo **telefone** (só dígitos, mesma loja; com DDD; gravado com máscara). Existente: só ganha o canal `site`, nada do cadastro muda nem é devolvido. Novo: criado com nome e sobrenome separados (CLI-01).
- **SIT-08** Sem o módulo Serviços: um "Atendimento" genérico de 30 min, sem preço, com os funcionários ativos que têm jornada.
- **SIT-09** Cada tipo de loja tem identidade própria no site (tema por tokens); mobile first; poucos passos; funciona sem JS e JS só melhora.
- **SIT-10** **Pendente:** proteção contra abuso (limite de requisições, captcha). Toda rota pública nova deve considerar isso.
