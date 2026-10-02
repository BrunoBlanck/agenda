# Agendamento para Clínica

Sistema web para gestão de uma clínica com vários funcionários: agenda de atendimentos, cadastro de clientes, funcionários, serviços e materiais, além do controle de ponto (entrada e saída) da equipe.

> **Status:** o front-end ainda usa dados de exemplo em memória (ao recarregar a página, os dados voltam ao estado inicial). O back-end está em construção em [`backend/`](backend/README.md): já tem o banco completo (PostgreSQL), dados de exemplo, login de funcionário e de superadmin e as regras de acesso; as rotas de cada menu ainda não existem, então o front ainda não está ligado à API.

## Funcionalidades

| Menu | Descrição |
|---|---|
| **Início** | Resumo do dia: agendamentos de hoje, clientes cadastrados, funcionários em serviço e materiais a repor |
| **Agenda** | Visão por **semana** (uma coluna por dia, horários na vertical, clique num horário vazio para agendar) ou por **mês**, com filtro por profissional e painel lateral com os atendimentos do dia selecionado em ordem |
| **Agendamentos** | Lista de agendamentos com filtro por profissional, local e período; criar, editar e excluir |
| **Clientes** | Cadastro de clientes (nome e sobrenome separados, CPF, telefone, e-mail, nascimento) |
| **Funcionários** | Cadastro de funcionários (nome, cargo, e-mail de login, telefone, ativo/inativo) |
| **Serviços** | Cadastro de serviços com duração, preço, profissionais habilitados, locais onde podem acontecer e materiais usados por atendimento |
| **Locais** | Onde o atendimento acontece: salas, cadeiras, macas, consultórios ou links online. A loja escolhe o nome que aparece no menu (ex.: "Salas", "Cadeiras") |
| **Materiais** | Controle de estoque com quantidade mínima e alerta de reposição |
| **Controle de Tempo** | Registro de entrada/saída dos funcionários e total de horas trabalhadas por dia |
| **Configurações › Dados da loja** | Logo, nome, razão social, contato, endereço (com busca por CEP) e CNPJ |
| **Configurações › Perfis e horários** | Cada perfil reúne o nível de acesso (nenhum, leitura ou escrita) em cada área, a jornada semanal e os bloqueios (folgas, férias, feriados). O funcionário é vinculado ao perfil uma vez só e herda tudo |

### Acessos e módulos

- Cada funcionário tem um **perfil** (Administrador, Recepção, Profissional ou outros criados pela loja). O menu e os botões mostrados dependem do nível do perfil em cada área.
- **Serviços, Materiais, Controle de Tempo e Locais** podem ser desativados por loja. Sem Serviços, o agendamento é feito sem serviço (duração e preço manuais). Sem Locais, o agendamento não pede local.
- Como ainda não há login nem painel SUPERADMIN, o botão **Demonstração** (no topo) permite trocar o usuário logado, ligar/desligar módulos e mudar o tipo da loja.
- Detalhes das regras em [`estrutura.md`](estrutura.md).

### Prévia do painel SUPERADMIN

Em `/superadmin` (ou pelo botão **Demonstração › Abrir prévia do painel SUPERADMIN**) há uma prévia navegável da área da plataforma:

| Menu | Descrição |
|---|---|
| **Visão geral** | Lojas ativas/suspensas, funcionários, receita dos planos, lojas por tipo, módulos em uso e últimas ações dos admins |
| **Lojas** | Lista com filtros e criação de loja (tipo, plano, módulos que a loja vai usar e o primeiro Administrador). No detalhe: dados gerais, módulos (ligar/desligar, observação e prazo), funcionários (suporte: criar, editar, redefinir senha) e histórico |
| **Planos** | Nome e preço. O plano não define módulos: eles são escolhidos loja a loja |
| **Usuários admin** | Só as contas de superadmin. Usuários das lojas são cadastrados na loja |
| **Auditoria** | Uma loja por vez: escolhe a loja, a tabela e o período e vê o que mudou (antes → depois) e quem fez |

O tipo da loja (Clínica, Barbearia, Escola) é uma constante do sistema: cada tipo terá o próprio site do consumidor. Nada é apagado de verdade: excluir marca a data/hora e quem excluiu, e tudo fica na auditoria.

A "Clínica Sorriso" é a loja aberta no painel da loja: o que o superadmin muda nela (módulos, dados, funcionários) aparece no painel na hora.

### Regras de agendamento

- Todo agendamento é vinculado a um **serviço** previamente cadastrado.
- Ao escolher o serviço, a **duração** é preenchida automaticamente.
- Só podem ser escolhidos os **profissionais habilitados** para aquele serviço.
- Os **materiais** do serviço são exibidos no momento do agendamento.
- Com o módulo **Locais** ativo, o agendamento exige um local permitido para o serviço (serviço sem local vinculado aceita qualquer um) e não deixa escolher um local já ocupado no horário. Local online pode ter um link fixo ou um link por atendimento.

## Tecnologias

Front-end:

- [React 19](https://react.dev/) + [Vite](https://vite.dev/)
- [Ant Design](https://ant.design/) (UI kit, em português via `pt_BR`)
- [React Router](https://reactrouter.com/)
- [Day.js](https://day.js.org/) para datas

Back-end ([`backend/`](backend/README.md)): Python, FastAPI, PostgreSQL 16, SQLAlchemy 2 e Alembic.

## Como rodar

O back-end tem as próprias instruções em [`backend/README.md`](backend/README.md). Para o front-end:

Pré-requisito: [Node.js](https://nodejs.org/) 20 ou superior.

```bash
cd frontend
npm install
npm run dev
```

Abra o endereço exibido no terminal (por padrão http://localhost:5173).

| Endereço | O que é |
|---|---|
| `/` | Site do consumidor final (exemplo): escolhe o serviço, vê horários livres, faz um cadastro e solicita o agendamento |
| `/painel` | Painel da loja (todos os menus ficam em `/painel/...`) |
| `/superadmin` | Prévia do painel SUPERADMIN |

### Outros comandos

| Comando | O que faz |
|---|---|
| `npm run build` | Gera a versão de produção em `frontend/dist` |
| `npm run preview` | Serve localmente a versão de produção gerada |
| `npm run lint` | Verifica o código com o Oxlint |

## Estrutura

```
frontend/src/
├── main.jsx                  # Inicialização (tema, idioma, rotas, dados)
├── App.jsx                   # Definição das rotas
├── layout/
│   ├── AppLayout.jsx         # Menu lateral, cabeçalho e bloqueio de telas sem acesso
│   ├── navegacao.jsx         # Itens do menu e regra de acesso de cada tela
│   └── PainelDemonstracao.jsx # Troca de usuário e módulos (provisório)
├── components/
│   ├── AgendamentoModal.jsx  # Formulário de agendamento
│   └── CadastroTabela.jsx    # Tela genérica de cadastro (busca + tabela + formulário)
├── data/
│   ├── mock.js               # Dados de exemplo
│   ├── acesso.js             # Catálogos: módulos, recursos e níveis de acesso
│   ├── useAcesso.js          # Regras de acesso do usuário logado
│   └── DataContext.jsx       # Estado em memória compartilhado entre as telas
└── pages/                    # Uma tela por menu
```

## Próximos passos

- Back-end: rotas de cada menu do painel da loja, do painel SUPERADMIN e do site do consumidor
- Ligar o front-end à API (login real no lugar do botão Demonstração)
- Painel SUPERADMIN
- Validação de conflito de horários por profissional
- Baixa automática de materiais no estoque ao concluir um atendimento
