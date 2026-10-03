---
name: regras-do-sistema
description: Catálogo das regras de negócio do sistema de agendamento multi-loja (plataforma SUPERADMIN, painel da loja, agenda, cadastros, estoque, ponto, site do consumidor), com um código para cada regra. Use para especificar, implementar ou revisar qualquer funcionalidade, e para responder "qual é a regra de X?".
user-invocable: false
---

# Regras do sistema

Catálogo condensado das regras do produto. **A fonte da verdade continua sendo o `estrutura.md`** (banco e regras 📌, seções 1 a 6) e o `README.md`. Este catálogo existe para que todo agente fale a mesma língua: cada regra tem um código (`AGE-04`) que aparece na especificação, nos testes e nas revisões.

## Como usar

1. Leia este arquivo inteiro (regras transversais valem para tudo).
2. Abra a referência da área que a tarefa toca:

| Área | Arquivo | Códigos |
|---|---|---|
| Acesso: login, módulos, perfis, níveis, listas de apoio | [referencias/acesso.md](referencias/acesso.md) | `ACE-*` |
| Agenda e agendamentos: status, conflitos, jornada, bloqueios, visibilidade | [referencias/agenda.md](referencias/agenda.md) | `AGE-*` |
| Cadastros da loja: clientes, funcionários, cargos, serviços, locais, materiais, estoque, ponto, dados da loja | [referencias/cadastros.md](referencias/cadastros.md) | `CLI-*`, `FUN-*`, `SER-*`, `LOC-*`, `MAT-*`, `PON-*`, `CFG-*` |
| Plataforma (SUPERADMIN): lojas, módulos, planos, usuários admin, auditoria | [referencias/plataforma.md](referencias/plataforma.md) | `PLA-*` |
| Site do consumidor (público, por `slug`) | [referencias/site.md](referencias/site.md) | `SIT-*` |
| Pontos em aberto e decisões provisórias | [referencias/em-aberto.md](referencias/em-aberto.md) | `ABE-*` |

3. Se a regra não está em nenhum lugar, **não invente**: é um ponto em aberto. Escolha o comportamento mais conservador, deixe fácil de trocar e registre como decisão provisória (ver `em-aberto.md`).

## Manutenção (responsabilidade do coordenador)

Quando o usuário decide uma regra nova ou muda uma existente, atualize **no mesmo trabalho**: o `estrutura.md` (fonte), a referência da área aqui (com código novo, nunca reaproveitando um código antigo) e, se for o caso, tire o item de `em-aberto.md`. Regra que só existe na conversa se perde.

---

## Regras transversais (`GER-*`): valem para todas as áreas

### O produto
- **GER-01** SaaS multi-loja de agendamento para negócios de serviço: **clínica, barbearia, escola** (`tipo_loja`). Três áreas: **Painel da loja** (`/painel`, SPA React), **SUPERADMIN** (`/superadmin`, SPA React) e **Site do consumidor** (`/`, HTML renderizado pelo back-end Python; o que existe em `frontend/src/site/` é só protótipo).
- **GER-02** A **API do back-end é a única fonte da verdade** das regras de negócio. Regra no front é conveniência de UX (desabilitar botão, validar campo), nunca proteção.
- **GER-03** O tipo da loja **não muda nada no painel** (nem módulos, nem telas). Só muda o site do consumidor. Textos do painel que variam por loja vêm de `loja_configuracoes` (ex.: rótulo "Sala"/"Cadeira").

### Isolamento entre lojas
- **GER-04** Toda tabela do painel tem `loja_id NOT NULL`, `UNIQUE (loja_id, id)` e FKs internas **compostas** `(loja_id, x_id)`. Uma loja nunca enxerga nem referencia dado de outra.
- **GER-05** O `loja_id` vem **sempre do token**, nunca do corpo, da query ou da URL do painel. RLS (`app.loja_id`) é a segunda camada.
- **GER-06** Recurso de outra loja responde **404** (não 403), para não revelar que existe.
- **GER-07** O mesmo cliente/pessoa em duas lojas são dois registros independentes.

### Controle, exclusão e histórico
- **GER-08** Colunas de controle em toda tabela (`criado_em`, `atualizado_em`, `excluido_em`, `excluido_por`, e `atualizado_por` nas da loja) são preenchidas **pelos triggers**, a partir do contexto da transação (`set_config('app.funcionario_id' | 'app.superadmin_id' | 'app.loja_id' | 'app.origem' | 'app.ip', valor, true)`). O Python não grava essas colunas.
- **GER-09** **Nada é apagado de verdade.** `DELETE` vira exclusão lógica por trigger. Toda leitura filtra `excluido_em IS NULL`. `UNIQUE` é índice único **parcial** (`WHERE excluido_em IS NULL`), então dá para recadastrar um nome excluído.
- **GER-10** Tabela de ligação: religar um vínculo excluído **restaura** a linha existente em vez de inserir outra.
- **GER-11** `ativo = false` ≠ excluído: inativo continua visível (e no histórico), só não aparece para usos novos. Excluído some das telas.
- **GER-12** **Auditoria** de toda tabela por trigger (`inserir`, `alterar`, `excluir`, `restaurar`), com antes/depois, quem fez e origem (`painel`, `superadmin`, `site`, `sistema`). Somente inserção. Nunca guarda `senha_hash`.
- **GER-13** Alteração feita pelo superadmin numa tabela da loja deixa `atualizado_por` NULL; quem foi fica na auditoria.

### Convenções de dados
- **GER-14** Nomes em português, `snake_case` no banco e na API; tabelas no plural. PK `uuid`.
- **GER-15** Datas/horas em `timestamptz` (UTC no banco). A API recebe hora **sem fuso** como hora do **fuso da loja** e responde com o fuso da loja (ex.: `2030-01-07T09:00:00-03:00`). Filtros por dia usam o dia da loja. Nunca use o fuso do navegador nem do servidor para regra.
- **GER-16** Dinheiro `numeric(10,2)`, saída como número no JSON. Nunca `float` em cálculo no back-end (use `Decimal`).
- **GER-17** Hora de eventos "agora" (ponto, aceite) vem do **servidor**, não do cliente.

### Contrato da API
- **GER-18** Prefixos: `/api/loja/...` (token de funcionário), `/api/superadmin/...` (token de superadmin), `/api/site/{slug}/...` (público). Token de um tipo não vale na área do outro (401).
- **GER-19** Erros em português, prontos para o usuário: `{"detail": "..."}`; validação (422) traz também `erros: [{campo, mensagem}]`. Códigos: 401 sem login/token inválido, 403 sem permissão/módulo desligado/loja suspensa, 404 não existe ou é de outra loja, 409 conflito (unicidade, horário ocupado, exclusão com dependentes), 422 dado inválido.
- **GER-20** Listas que crescem são paginadas: `?pagina=1&por_pagina=20` → `{itens, total, pagina, por_pagina}` (clientes, agendamentos, histórico, movimentações, auditoria, lojas).
- **GER-21** Respostas de registro trazem `criado_em`, `atualizado_em`, `atualizado_por` e `atualizado_por_nome` (componente `UltimaAlteracao`).
- **GER-22** Nunca logar senha, token ou dado pessoal (CPF, telefone, e-mail de cliente). Segredos só no `.env`.

### Módulos e permissões (resumo; detalhe em `acesso.md`)
- **GER-23** Toda rota da loja exige `exigir(recurso, nivel)`: o nível vem do **perfil** e vale `nenhum` se o **módulo** do recurso estiver desligado na loja, inclusive para o Administrador.
- **GER-24** Módulos opcionais: **Serviços, Materiais, Controle de Tempo, Locais**. Desligar não apaga dados; religar volta tudo como estava.
- **GER-25** Loja `suspensa` ou `cancelada` não acessa o painel (403 no painel, 404 no site).

### Interface (resumo; detalhe na skill `padroes-ui`)
- **GER-26** Botões e menus seguem o nível efetivo: `nenhum` esconde, `leitura` mostra sem ações de alterar, `escrita` mostra tudo. Isso é UX; a proteção é o GER-23.
- **GER-27** Tudo que cria, edita ou consulta um registro por cima da tela é **painel lateral** (`PainelFormulario`/`PainelLateral`), nunca `Modal`.
- **GER-28** Status (agendamento, loja, ponto) sempre com texto/ícone além da cor (`components/Etiquetas.jsx`).
