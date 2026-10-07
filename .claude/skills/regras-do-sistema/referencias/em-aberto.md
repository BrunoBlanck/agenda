# Pontos em aberto e decisões provisórias (`ABE-*`)

Fonte: `estrutura.md` seção 5 (pontos em aberto) e 6.1/6.2 (decisões *provisórias*). **Nenhum agente decide estes pontos sozinho.** O coordenador leva ao usuário quando a funcionalidade depender deles; até lá vale o comportamento provisório, que precisa ficar fácil de trocar.

## Decisões provisórias em vigor
| Código | Ponto | Comportamento atual | Onde trocar |
|---|---|---|---|
| ABE-01 | Estoque negativo | Permitido; a conclusão não é bloqueada e o material aparece em "Repor" | `PERMITIR_ESTOQUE_NEGATIVO` em `backend/app/services/estoque.py` |
| ABE-02 | Antecedência mínima para agendar (site) | 60 min, passos de 30 min, até 31 dias | `backend/app/services/horarios_livres.py` |
| ABE-03 | Senha sem e-mail | Senha provisória devolvida uma vez | `gerar_senha_provisoria` em `backend/app/auth/senhas.py` |
| ABE-04 | Cliente inativo pedindo pelo site | Não é reativado | serviço do site |
| ABE-05 | Serviços desligado | Agendamento sem serviço, duração e preço manuais | `services/agendamentos.py` |

## Ainda sem decisão
- ~~ABE-10 Cliente com login próprio~~ Decidido em 2026-10-06: SIT-16 a SIT-24.
- ~~ABE-11 Antecedência mínima para cancelar~~ Decidido em 2026-10-06: configurável pela loja (CFG-05), padrão 2 h, vale para cancelar e remarcar pelo site e para o lembrete (NOT-05).
- ABE-12 Notificações por **WhatsApp/SMS** (e-mail, sino e lembrete decididos em 2026-10-06: NOT-01 a NOT-08; hoje o WhatsApp fica sempre com status 4). Inclui trocar o provedor "painel" do código da conta (SIT-17) por SMS/WhatsApp: hoje quem tem escrita em Clientes, ou quem convence a recepção, consegue o código e assume a conta de um telefone; ao trocar, guardar só o hash do código. Risco provisório aceito (rodada 2 da conta-cliente): com 4 IPs dá para esgotar as 20 tentativas de um código e um telefone visado recebe até 100 palpites/hora; avaliar teto de erros por telefone e aviso à loja.
- ABE-13 Financeiro (caixa, relatórios, comissões, várias formas por atendimento, parcelas). Decidido em 2026-10-07: concluir exige registrar forma e valor do pagamento (AGE-26 a AGE-29).
- ABE-14 Prontuário/anotações clínicas (dados sensíveis, LGPD).
- ABE-15 Um funcionário em mais de uma loja.
- ABE-16 Subtipo/segmento da loja (só afetaria o site).
- ABE-17 Retenção da auditoria e remoção definitiva por LGPD.
- ABE-18 Planos com limites.
- ABE-19 Ajuste de acesso por funcionário (exceção ao perfil).
- ABE-20 Razão social editável pela loja.
- ABE-21 Quem liga o módulo Locais (superadmin ou a própria loja).
- ABE-22 Atendimentos em grupo (capacidade de local/serviço).
- ABE-23 Proteção contra abuso nas rotas públicas (rate limit, captcha) — ver SIT-10.
