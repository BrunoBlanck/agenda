---
name: defeitos-recorrentes
description: Tipos de defeito que já se repetiram neste projeto (back e front) e os padrões de correção adotados; olhar primeiro em toda revisão
metadata:
  type: project
---

Tipos de defeito que já apareceram mais de uma vez (revisão completa do back-end em 2026-10-02, rodadas 1 e 2):

1. **"Verificar e gravar" sem trava (LOG-02/LOG-07).** Rodada 1: último Administrador e conclusão/estorno de agendamento sem trava (comprovado: 2 baixas, loja sem admin). Corrigido na rodada 2 com `buscar_visivel(..., travar=True)`, `outros_admins_ativos` com `FOR UPDATE`, `lancar` travando o material e advisory lock no ponto e no telefone do site. Em rota nova que altera estado/contagem, cobrar o mesmo padrão.
2. **Valor extremo vira 500.** Corrigido com os tipos `Data`/`DataHora` (2000–2100), `PAGINA_MAX`, `QUANTIDADE_MAX` + saldo conferido, e tratadores de OverflowError/22003/22008. Em rota nova, conferir se as entradas usam esses tipos e não `date`/`datetime`/`int` crus.
3. **Formato não validado no painel.** Corrigido com `Cpf`, `Telefone`, `TelefoneOpcional`, `DataNascimento` em `schemas/comum.py`. O telefone da loja (`DadosLojaEntrada`) ainda é texto livre.
4. **Escalada dentro da loja (SEG-05/ACE-19).** Corrigido para *conceder* acima do teto. Ainda é possível *agir sobre* perfis e colegas acima (rebaixar níveis, inativar, trocar e-mail); isso depende da interpretação de ACE-19 pelo coordenador.
5. **Proteção que vira negação de serviço.** Rodada 2: o bloqueio de login por conta podia ser renovado indefinidamente por terceiros. Rodada 3: passou a ser por conta + IP (resolvido). Risco residual: força bruta distribuída (cerca de 5 tentativas por IP antes do bloqueio e depois ~1 a cada 15 min por IP e conta); o limite global por IP não segura isso, só captcha ou sinal global por conta. Ao revisar limites e bloqueios, testar sempre o abuso *do próprio limite* e o caso distribuído.

6. **Fuso horário (GER-15 / INT-11).** Já voltou várias vezes: respostas do back em UTC (corrigido com TimeZone da loja na transação, app/db.py) e, na integração de 2026-10-02, o front (`data/api/conversao.js` `lerDataHora`) convertendo todo ISO com offset para um fuso global da sessão em vez de usar a hora como veio. Sempre testar com uma loja fora de America/Sao_Paulo (ex.: America/Manaus) e o caminho ler → editar → salvar; prove com node importando `conversao.js` direto. Resolvido na rodada 2 da integração (2026-10-02): hora escrita na string quando há offset, só UTC é convertido; colunas de controle passam por `lerControle`/`dataHoraBR` (ambos usam `lerDataHora`).

**Why:** cada item apareceu em pelo menos dois pontos do código ou voltou numa correção.
**How to apply:** em toda rota nova, conferir trava/constraint, tipos de entrada com faixa, normalização de documentos e se a ação afeta quem está acima de quem age. Ver como comprovar em [[testes-exploratorios]].
