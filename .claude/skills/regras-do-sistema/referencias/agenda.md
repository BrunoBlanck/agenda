# Agenda e agendamentos (`AGE-*`)

Fonte: `estrutura.md` 2.5, 2.6, 2.13, 2.14, 6.1 e o README (Regras de agendamento). No código: `backend/app/services/agendamentos.py` (constante `TRANSICOES`), `disponibilidade.py`, `horarios_livres.py`.

## Criação
- **AGE-01** Todo agendamento tem cliente (obrigatório), profissional (obrigatório), `inicio` e `fim` (`fim > inicio`).
- **AGE-02** Com o módulo **Serviços** ativo: serviço obrigatório; a **duração** vem do serviço (`fim = inicio + duracao_minutos`), mas pode ser ajustada à mão.
- **AGE-03** Só profissionais **habilitados** para o serviço (par existe em `servico_funcionarios`) e **ativos**.
- **AGE-04** **Preço congelado:** o agendamento copia o preço do serviço na criação; mudar o preço do serviço depois não altera agendamentos.
- **AGE-05** Materiais do serviço são **copiados** para `agendamento_materiais` na criação (com o módulo Materiais ativo) e recopiados se o serviço mudar antes de concluir. Podem ser ajustados até a conclusão. Mudar os materiais do serviço não afeta agendamentos já criados.
- **AGE-06** Criado no painel começa `agendado` ou `confirmado`. `pendente` só vem do site.

## Conflitos e disponibilidade
- **AGE-07** **Sem conflito de profissional:** dois agendamentos ativos do mesmo profissional não se sobrepõem. Garantido no banco (`EXCLUDE USING gist`), ignorando `cancelado`, `nao_compareceu` e excluídos. Conflito = 409 com mensagem clara.
- **AGE-08** **Jornada:** o atendimento precisa caber **inteiro** numa faixa da jornada do **perfil** do profissional (`perfil_horarios`), no mesmo dia, no fuso da loja. Um dia pode ter várias faixas (almoço). `dia_semana` 0 = domingo … 6 = sábado.
- **AGE-09** **Bloqueios:** profissional bloqueado quando há bloqueio da **loja inteira** (perfil e funcionário NULL), do **perfil** dele ou **dele próprio**. No máximo um de `perfil_id`/`funcionario_id` preenchido.
- **AGE-10** Jornada e bloqueios são conferidos ao criar e quando muda horário ou profissional (não quando só muda o status).
- **AGE-11** Jornadas e bloqueios só são alterados com **escrita** em *Horários e bloqueios* (`config_agendamentos`).

## Locais
- **AGE-12** Com o módulo **Locais** ativo: local obrigatório, **ativo** e **permitido** para o serviço. Serviço **sem nenhum local vinculado** pode usar **qualquer local ativo** (inclusive criados depois). Com Serviços desligado, qualquer local ativo serve.
- **AGE-13** **Sem conflito de local:** mesma regra do AGE-07 por `local_id` (agendamentos sem local não entram). Pedidos `pendente` do site também ocupam o local.
- **AGE-14** Módulo **Locais desligado**: `local_id` é ignorado/NULL e as regras de local não se aplicam; agendamentos antigos mantêm o local.
- **AGE-15** Módulo **Serviços desligado**: agendamento **sem serviço**, duração obrigatória e preço manuais; AGE-03 não se aplica; ao editar, o `servico_id` antigo é mantido.
- **AGE-16** Local online: link fixo em `locais.link_padrao`; link por atendimento em `agendamentos.link_reuniao` (vazio = usa o padrão).

## Status
- **AGE-17** Transições permitidas (nenhuma outra):

```
pendente   -> confirmado | cancelado            (aceitar / recusar pedido do site)
agendado   -> confirmado | cancelado | nao_compareceu
confirmado -> concluido  | cancelado | nao_compareceu
```

`agendado` não vai direto para `concluido`.
- **AGE-18** `concluido`, `cancelado` e `nao_compareceu` são **finais**. Só o Administrador (`acesso_total`) reabre, para `agendado` ou `confirmado`.
- **AGE-19** `cancelado` exige `motivo_cancelamento` (recusar pedido do site também).
- **AGE-20** Ir para `concluido` dá **baixa** nos materiais (`saida_atendimento`, na mesma transação), só com o módulo Materiais ativo. Reabrir um concluído gera **estorno** (`ajuste` positivo, motivo "Estorno: atendimento reaberto"). Concluir de novo gera nova saída.
- **AGE-21** Agendamento final não é editado (reabra antes). **Concluído não é excluído.**

## Visibilidade
- **AGE-22** Só *Minha agenda*: vê e altera apenas onde `funcionario_id` é ele. Com *Agenda da equipe*: todos. Leitura só vê; escrita cria, remarca, muda status e cancela.
- **AGE-23** Histórico do cliente exige leitura em *Clientes* e mostra só os agendamentos que o usuário pode ver na agenda (`parcial = true` quando há outros).
- **AGE-24** Todo o histórico do agendamento (remarcação, status, troca de profissional/local) vem da `auditoria`.
- **AGE-25** Transições exclusivas do cliente pelo site (SIT-23/24), em `TRANSICOES_DO_CLIENTE` (`app/services/conta_agendamentos.py`): `pendente`/`agendado`/`confirmado` → `cancelado`; `agendado`/`confirmado` → `pendente` e `pendente` → `pendente` com outro horário (remarcação). O `TRANSICOES` do painel não muda: nenhum caminho do painel volta um agendamento a `pendente`.
