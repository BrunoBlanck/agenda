# Agendamento para Clínica

Sistema web para gestão de uma clínica com vários funcionários: agenda de atendimentos, cadastro de clientes, funcionários, serviços e materiais, além do controle de ponto (entrada e saída) da equipe.

> **Status:** esboço inicial. Por enquanto existe apenas o front-end, com dados de exemplo mantidos em memória (ao recarregar a página, os dados voltam ao estado inicial). Ainda não há back-end, banco de dados nem login.

## Funcionalidades

| Menu | Descrição |
|---|---|
| **Início** | Resumo do dia: agendamentos de hoje, clientes cadastrados, funcionários em serviço e materiais a repor |
| **Agenda** | Calendário mensal com os agendamentos, filtro por profissional e lista dos atendimentos do dia selecionado |
| **Agendamentos** | Lista de agendamentos com filtro por profissional e período; criar, editar e excluir |
| **Clientes** | Cadastro de clientes (nome, CPF, telefone, e-mail, nascimento) |
| **Funcionários** | Cadastro de funcionários (nome, cargo, e-mail de login, telefone, ativo/inativo) |
| **Serviços** | Cadastro de serviços com duração, preço, profissionais habilitados e materiais usados por atendimento |
| **Materiais** | Controle de estoque com quantidade mínima e alerta de reposição |
| **Controle de Tempo** | Registro de entrada/saída dos funcionários e total de horas trabalhadas por dia |

### Regras de agendamento

- Todo agendamento é vinculado a um **serviço** previamente cadastrado.
- Ao escolher o serviço, a **duração** é preenchida automaticamente.
- Só podem ser escolhidos os **profissionais habilitados** para aquele serviço.
- Os **materiais** do serviço são exibidos no momento do agendamento.

## Tecnologias

- [React 19](https://react.dev/) + [Vite](https://vite.dev/)
- [Ant Design](https://ant.design/) (UI kit, em português via `pt_BR`)
- [React Router](https://reactrouter.com/)
- [Day.js](https://day.js.org/) para datas

## Como rodar

Pré-requisito: [Node.js](https://nodejs.org/) 20 ou superior.

```bash
cd frontend
npm install
npm run dev
```

Abra o endereço exibido no terminal (por padrão http://localhost:5173).

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
├── layout/AppLayout.jsx      # Menu lateral e cabeçalho
├── components/
│   ├── AgendamentoModal.jsx  # Formulário de agendamento
│   └── CadastroTabela.jsx    # Tela genérica de cadastro (busca + tabela + formulário)
├── data/
│   ├── mock.js               # Dados de exemplo
│   └── DataContext.jsx       # Estado em memória compartilhado entre as telas
└── pages/                    # Uma tela por menu
```

## Próximos passos

- Back-end com API e banco de dados
- Login com perfis (administrador, profissional, recepção), cada profissional vendo a própria agenda
- Validação de conflito de horários por profissional
- Baixa automática de materiais no estoque ao concluir um atendimento
