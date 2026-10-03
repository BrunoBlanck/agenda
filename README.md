# Agendamento para Clínica

Sistema web para gestão de uma clínica com vários funcionários: agenda de atendimentos, cadastro de clientes, funcionários, serviços e materiais, além do controle de ponto (entrada e saída) da equipe.

> **Status:** há um back-end em [`backend/`](backend/README.md) (FastAPI + PostgreSQL) com o banco completo, dados de exemplo, login de funcionário e de superadmin, as regras de acesso e as rotas das três áreas: painel da loja, painel SUPERADMIN e site do consumidor. O front-end está **ligado à API** nas três áreas, com login de verdade: rode o back-end antes do front (ver "Como rodar").

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
- Entre em `/<slug-da-loja>/painel` (ex.: `/clinica-sorriso/painel`) com um dos usuários do seed (lista em [`backend/README.md`](backend/README.md)) para ver o painel com os acessos de cada perfil; os módulos e o tipo da loja são definidos no SUPERADMIN.
- Detalhes das regras em [`estrutura.md`](estrutura.md).

### Painel SUPERADMIN

Em `/superadmin` (login de superadmin) fica a área da plataforma:

| Menu | Descrição |
|---|---|
| **Visão geral** | Lojas ativas/suspensas, funcionários, receita dos planos, lojas por tipo, módulos em uso e últimas ações dos admins |
| **Lojas** | Lista com filtros e criação de loja (tipo, plano, módulos que a loja vai usar e o primeiro Administrador). No detalhe: dados gerais, módulos (ligar/desligar, observação e prazo), funcionários (suporte: criar, editar, redefinir senha) e histórico |
| **Planos** | Nome e preço. O plano não define módulos: eles são escolhidos loja a loja |
| **Usuários admin** | Só as contas de superadmin. Usuários das lojas são cadastrados na loja |
| **Auditoria** | Uma loja por vez: escolhe a loja, a tabela e o período e vê o que mudou (antes → depois) e quem fez |

O tipo da loja (Clínica, Barbearia, Escola) é uma constante do sistema: cada tipo terá o próprio site do consumidor. Nada é apagado de verdade: excluir marca a data/hora e quem excluiu, e tudo fica na auditoria.

O que o superadmin muda numa loja (módulos, dados, funcionários) vale no painel daquela loja a partir da próxima ação do funcionário.

### Regras de agendamento

- Todo agendamento é vinculado a um **serviço** previamente cadastrado.
- Ao escolher o serviço, a **duração** é preenchida automaticamente.
- Só podem ser escolhidos os **profissionais habilitados** para aquele serviço.
- Os **materiais** do serviço são exibidos no momento do agendamento.
- Com o módulo **Locais** ativo, o agendamento exige um local permitido para o serviço (serviço sem local vinculado aceita qualquer um) e não deixa escolher um local já ocupado no horário. Local online pode ter um link fixo ou um link por atendimento.

## Arquitetura planejada

| Área | Tecnologia | Por quê |
|---|---|---|
| Painel da loja (`/<slug>/painel`) e SUPERADMIN (`/superadmin`) | SPA em React (esta pasta `frontend/`) | Áreas logadas, sem SEO e muito interativas |
| Site do consumidor (`/<slug>`) | HTML renderizado no servidor pelo back-end Python, com JS mínimo | Público: precisa de SEO, link bonito no WhatsApp e abrir rápido no celular. Um modelo de site por tipo de loja |

Por enquanto `/<slug>` mostra uma página simples da loja (nome, logo e contato) gerada pelo back-end; o site com o fluxo de agendamento vem a seguir. As regras de negócio (horários livres, conflitos etc.) ficarão no back-end e serão usadas pelo site e pela API dos painéis.

## Tecnologias

Front-end:

- [React 19](https://react.dev/) + [Vite](https://vite.dev/)
- [Ant Design](https://ant.design/) (UI kit, em português via `pt_BR`)
- [React Router](https://reactrouter.com/)
- [Day.js](https://day.js.org/) para datas

Back-end ([`backend/`](backend/README.md)): Python, FastAPI, PostgreSQL 16, SQLAlchemy 2 e Alembic.

## Como rodar

### Back-end (API)

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Docker Desktop. Detalhes, usuários de exemplo e a lista de rotas em [`backend/README.md`](backend/README.md).

```bash
cd backend
cp .env.example .env            # e troque JWT_SECRET
docker compose up -d            # PostgreSQL 16 local
uv sync
uv run python -m scripts.criar_papel_app
uv run alembic upgrade head
uv run python -m scripts.seed   # dados de exemplo
uv run uvicorn app.main:app --reload
```

A API fica em http://localhost:8000 (documentação em http://localhost:8000/docs). Testes: `uv run pytest`.

### Front-end


Pré-requisito: [Node.js](https://nodejs.org/) 20 ou superior e a API no ar (seção anterior, em http://localhost:8000).

```bash
cd frontend
npm install
npm run dev
```

Abra o endereço exibido no terminal (por padrão http://localhost:5173). Em desenvolvimento o Vite faz o papel do nginx de produção: serve o painel e o SUPERADMIN e encaminha todo o resto (`/api`, o site das lojas) para a API (`API_PROXY_ALVO`, padrão http://localhost:8000). Assim as URLs são as mesmas em dev e em produção.

| Endereço | Quem atende | O que é |
|---|---|---|
| `/<slug>` | back-end | Site do consumidor da loja, ex.: `/clinica-sorriso` (por enquanto uma página simples com os dados da loja) |
| `/<slug>/painel` | front | Painel da loja, já identificado pela URL: o login pede só e-mail e senha. Todos os menus ficam em `/<slug>/painel/...` |
| `/superadmin` | front | Painel SUPERADMIN (login em `/superadmin/login`) |
| `/api/...` | back-end | API |

Os arquivos do build ficam em `/_app/` e alguns slugs são reservados (`superadmin`, `api`, `painel`...). Deploy com nginx: [`deploy/README.md`](deploy/README.md).

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
├── App.jsx                   # Definição das rotas (cada tela carregada sob demanda)
├── tema.js                   # Identidade visual: cores e tema do Ant Design (espelhado em index.css)
├── index.css                 # Variáveis CSS (tokens) e estilos comuns
├── layout/
│   ├── Casca.jsx             # Estrutura comum aos dois painéis (menu lateral, topo, conteúdo)
│   ├── AppLayout.jsx         # Painel da loja e bloqueio de telas sem acesso
│   ├── navegacao.jsx         # Itens do menu e regra de acesso de cada tela
│   ├── TelaLogin.jsx         # Login (painel da loja e SUPERADMIN)
│   └── ExigirSessao.jsx      # Guarda das áreas logadas (sem sessão, vai ao login)
├── components/
│   ├── base/                 # Peças de tela: Pagina, Secao, Tabela, BarraFiltros, EstadoVazio, Etiqueta...
│   │                         # PainelLateral (consulta) e PainelFormulario (formulário): todo painel que abre por cima de uma tela
│   ├── Etiquetas.jsx         # Etiquetas de status (agendamento, loja, situação, auditoria)
│   ├── AgendamentoPainel.jsx # Formulário de agendamento (painel lateral)
│   └── CadastroTabela.jsx    # Tela de cadastro completa (cabeçalho, busca, tabela e formulário no painel lateral)
├── data/
│   ├── api/
│   │   ├── cliente.js        # Único lugar que chama a API: token, tempo limite, erros (ErroApi)
│   │   ├── conversao.js      # snake_case <-> camelCase, datas na hora da loja, dinheiro, paginação
│   │   ├── useConsulta.js    # Hook de leitura (carregando, erro, recarregar, cancelamento)
│   │   ├── useTratarErro.js  # Mostra cada erro (422 nos campos, 404, 409, 403, rede)
│   │   └── <area>.js         # Funções de cada área (clientes, agendamentos, plataforma, site...)
│   ├── sessao/               # Sessões do painel da loja e do SUPERADMIN (login, GET eu, sair)
│   ├── use<Area>.js          # Hooks consumidos pelas telas
│   ├── dominio.js            # Enums da API com rótulo e tom (status, canais, tipos)
│   ├── acesso.js             # Nomes dos módulos e rótulos dos níveis de acesso
│   └── useAcesso.js          # Acessos do usuário logado (de GET /api/loja/eu)
└── pages/                    # Uma tela por menu
```

## Agentes de desenvolvimento (Claude Code)

O projeto é desenvolvido com um time de agentes em [`.claude/agents/`](.claude/agents/), que seguem as skills de [`.claude/skills/`](.claude/skills/):

| Agente | Papel |
|---|---|
| `coordenador` | Conhece todas as regras de negócio, escreve a especificação de cada funcionalidade (com o contrato da API e o de tela) e conduz o fluxo |
| `backend` | API Python: banco, rotas, regras e testes, com foco em segurança, correção lógica e performance |
| `frontend-ui` | Telas no padrão visual e de componentes do projeto, com dados provisórios no formato do contrato |
| `frontend-dev` | Liga as telas à API: tipos, datas, nulos, erros, paginação e sessão |
| `revisor` | Revisão leve no front (nada quebra, tela no padrão) e rigorosa no back (segurança, lógica, cenários de falha) |

Fluxo de uma funcionalidade nova:

```
coordenador (especificação em docs/funcionalidades/<slug>.md)
   ├─► backend ─────┐   em paralelo
   └─► frontend-ui ─┤
                    ▼
              frontend-dev
                    ▼
                revisor ──► reprovado: volta para o dono do achado e revisa de novo (até 3 rodadas)
                    ▼ aprovado
           commit na branch feat/<slug>
```

Para usar: abra o Claude Code na raiz do projeto como coordenador (`claude --agent coordenador`) e descreva a funcionalidade, ou, numa sessão comum, use `/nova-funcionalidade <descrição>`. O fluxo precisa rodar na conversa principal, porque um subagente não chama outros subagentes.

| Skill | Usada por | Conteúdo |
|---|---|---|
| `regras-do-sistema` | todos | Catálogo das regras de negócio com códigos (`AGE-17`, `ACE-19`...), resumo do `estrutura.md` |
| `especificar-funcionalidade` | coordenador, backend, frontend-ui, frontend-dev | Modelo da especificação e dos contratos |
| `nova-funcionalidade` | coordenador | O fluxo passo a passo |
| `backend-seguro` | backend, revisor | Checklist de segurança, lógica, performance e código limpo |
| `padroes-ui` | frontend-ui, revisor | Checklist de telas, componentes e identidade visual |
| `integracao-api` | frontend-dev, revisor | Checklist de integração com a API |
| `diretrizes` | todos | Como registrar, seguir e verificar as diretrizes permanentes |

### Memória do time: diretrizes permanentes

Uma ordem que vale para sempre ("em todas as telas de cadastro coloque X", "padronize as mensagens de erro no back-end", "a partir de agora nunca…") vira uma **diretriz** em [`.claude/diretrizes/`](.claude/diretrizes/INDICE.md), com um ID (`DIR-003`), escopo, regra, forma de verificar e a lista do código existente onde ela ainda precisa ser aplicada.

- O índice é carregado em toda sessão (pelo `CLAUDE.md`) e a skill `diretrizes` é pré-carregada em todos os agentes.
- Antes de cada tarefa, o agente lê as diretrizes do seu escopo; o coordenador as cita na especificação e o revisor reprova se alguma for violada.
- Um hook (`.claude/hooks/lembrar-diretriz.mjs`) percebe mensagens como "sempre", "em todas as telas" ou "padronize" e lembra o modelo de registrar a ordem antes de executar.
- A memória privada de cada agente (`.claude/agent-memory/`) fica só para aprendizados técnicos dele; ordem do usuário nunca vai para lá.

## Próximos passos

- Proteção contra abuso nas rotas públicas do site (limite de requisições, captcha)
- Envio de e-mail (definir/redefinir senha) e notificações de agendamento
