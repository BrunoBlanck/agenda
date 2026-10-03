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
- ABE-10 Cliente com login próprio (agendar online logado).
- ABE-11 Antecedência mínima para **cancelar**.
- ABE-12 Notificações (WhatsApp/e-mail) de confirmação e lembrete.
- ABE-13 Financeiro (pagamentos, comissões).
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
