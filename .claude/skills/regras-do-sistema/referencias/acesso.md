# Acesso: login, módulos, perfis e níveis (`ACE-*`)

Fonte: `estrutura.md` 1.4, 1.7, 1.8, 2.1, 2.2, 2.4 e 6.1. No código: `backend/app/auth/` (`dependencias.py`, `catalogo.py`) e `frontend/src/data/acesso.js` / `useAcesso.js` (espelho no front).

## Login e sessão
- **ACE-01** Dois tipos de usuário, em tabelas separadas: **funcionário** (`funcionarios`, login no painel da loja) e **superadmin** (`superadmin_usuarios`). Um não é o outro.
- **ACE-02** O e-mail do funcionário é único **por loja** (sem diferenciar maiúsculas), então o login do painel identifica a loja pelo `slug`.
- **ACE-03** Não faz login: funcionário **inativo**, funcionário de loja **suspensa/cancelada/excluída**, superadmin inativo. A mensagem de erro não revela qual dos dados está errado.
- **ACE-04** Token JWT carrega o tipo (`funcionario` com `loja_id`, ou `superadmin`). Rotas da loja recusam token de superadmin e vice-versa (401). A cada requisição o back-end confere de novo se o usuário segue ativo e a loja segue ativa (token antigo não vale para loja que foi suspensa depois).
- **ACE-05** Senhas com Argon2; mínimo de 8 caracteres. Nunca devolvidas nem logadas.

## Módulos (funcionalidades)
- **ACE-06** Catálogo fixo (migração). Base, sempre ativos: `inicio`, `agenda`, `clientes`, `funcionarios`, `configuracoes`. Opcionais: `servicos`, `materiais`, `controle_tempo`, `locais`.
- **ACE-07** **Módulo ativo na loja** = `opcional = false` **ou** linha em `loja_funcionalidades` com `habilitado = true` e `expira_em` nula ou futura. Prazo vencido = desligado.
- **ACE-08** Só o superadmin liga/desliga módulos. O plano não interfere (PLA-*).
- **ACE-09** Módulo desligado: some do menu, a API responde **403** nas rotas dele (até para o Administrador) e os dados ficam intactos. Efeitos em outras áreas: ver AGE-14/AGE-15, MAT-07, PON-01.

## Recursos e níveis
- **ACE-10** Recursos (catálogo fixo) e o que cada nível permite:

| Recurso | Módulo | Leitura | Escrita |
|---|---|---|---|
| `agenda_propria` | agenda | ver os próprios agendamentos | criar, remarcar, mudar status, cancelar os próprios |
| `agenda_equipe` | agenda | ver de todos | o mesmo, de qualquer profissional |
| `config_agendamentos` | agenda | ver jornadas e bloqueios | editar jornadas, bloqueios, folgas, feriados |
| `clientes` | clientes | lista e ficha | cadastrar, editar, inativar |
| `funcionarios` | funcionarios | lista | cadastrar, editar, inativar, cargo e perfil |
| `perfis_acesso` | funcionarios | perfis e níveis | criar e editar perfis e níveis |
| `servicos` | servicos | ver | cadastrar, editar, vincular profissionais/locais/materiais |
| `materiais` | materiais | estoque e movimentações | cadastrar, editar, entradas, ajustes, perdas |
| `locais` | locais | ver | cadastrar, editar, inativar, rótulos |
| `ponto_proprio` | controle_tempo | próprios registros | registrar entrada/saída |
| `ponto_equipe` | controle_tempo | registros de todos | corrigir (com justificativa) |
| `config_loja` | configuracoes | dados da loja | editar dados da loja |

- **ACE-11** Níveis: `nenhum` (some do menu, API 403), `leitura` (vê, não altera; botões de alterar ocultos), `escrita` (vê e altera). **Escrita inclui leitura.**
- **ACE-12** Recurso sem linha em `perfil_acessos` = `nenhum` (recurso novo começa bloqueado, exceto para o Administrador).
- **ACE-13** **Nível efetivo** = nível do perfil, mas `nenhum` se o módulo do recurso estiver desligado (ACE-09).
- **ACE-14** Leitura tentando escrever: 403 "Você só tem permissão de leitura aqui."

## Perfis
- **ACE-15** Cada funcionário tem **um** perfil e herda dele os níveis **e** a jornada semanal (AGE-08) e os bloqueios do grupo. Trocar de perfil troca a jornada.
- **ACE-16** Perfis padrão criados com a loja: **Administrador** (`acesso_total`, escrita em tudo, não editável), **Recepção** e **Profissional** (editáveis). Perfil padrão não é renomeado nem excluído.

| Recurso | Administrador | Recepção | Profissional |
|---|---|---|---|
| Minha agenda | escrita | escrita | escrita |
| Agenda da equipe | escrita | escrita | nenhum |
| Horários e bloqueios | escrita | leitura | nenhum |
| Clientes | escrita | escrita | leitura |
| Funcionários / Perfis / Materiais / Ponto da equipe / Dados da loja | escrita | nenhum | nenhum |
| Serviços / Locais | escrita | leitura | nenhum |
| Meu ponto | escrita | escrita | escrita |

- **ACE-17** Ao criar um perfil é possível copiar níveis e jornada de outro. Mesmo acesso com horários diferentes = perfis diferentes ("Profissional · manhã").
- **ACE-18** Perfil com funcionários (mesmo inativos) não é excluído (409). Excluir perfil exclui junto os níveis, a jornada e os bloqueios dele.
- **ACE-19** **Sem escalada de acesso:** quem tem escrita em *Funcionários* mas não em *Perfis de acesso* só atribui perfis existentes e **nunca** o Administrador. Só o Administrador (ou o superadmin) atribui o perfil Administrador. Ninguém edita níveis acima dos próprios.
- **ACE-20** A loja nunca fica sem **Administrador ativo**: não se inativa, troca de perfil ou exclui o último (vale também para o superadmin pelo suporte).

## Listas de apoio
- **ACE-21** Listas usadas em formulários (clientes, serviços, profissionais, locais ao criar agendamento) são liberadas para quem **pode criar agendamentos**, mesmo sem leitura nos recursos de origem, e devolvem só o necessário (id, nome, vínculos). Quem só tem escrita em *Minha agenda* recebe só a si mesmo e os serviços que realiza. Rota: `GET /api/loja/apoio/agendamento`.
