---
name: integracao-api
description: Como o front-end React deste projeto conversa com a API FastAPI - cliente HTTP único, autenticação, conversão snake_case/camelCase, datas no fuso da loja, dinheiro, paginação, tratamento de cada status de erro e de valores nulos - em forma de checklist. Use ao ligar telas à API, criar ou alterar hooks em frontend/src/data, ou revisar essa integração.
user-invocable: false
---

# Integração front-end ↔ API

Checklist do **frontend-dev** (constrói) e do **revisor** (confere), códigos `INT-*`. O contrato vem da especificação da funcionalidade (`docs/funcionalidades/<slug>.md`, seções 4 e 5) e do OpenAPI do back-end (`http://localhost:8000/docs`, ou `uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))"` em `backend/` sem precisar subir a API). Convenções da API: `backend/README.md` e skill `regras-do-sistema` (GER-15 a GER-21).

## 1. Arquitetura da camada de dados

```
frontend/src/data/
├── api/
│   ├── cliente.js        # único lugar que chama fetch: api.loja/superadmin/site, token, timeout, ErroApi, urlDaApi, FormData
│   ├── conversao.js      # paraCamel/paraSnake/escolher, lerDataHora/enviarDataHora, agoraNaLoja, enviarNumero, lerPagina
│   ├── registro.js       # lerControle (UltimaAlteracao), conflitoNoCampo (409 -> campo), apontarCampo (422 de regra -> campo)
│   ├── useConsulta.js    # leitura: { dados, carregando, atualizando, atual, erro, recarregar } com cancelamento
│   ├── useTratarErro.js  # tratar(erro, { form, mapa, aoNaoEncontrado, aoConflito }) conforme a tabela da seção 5
│   └── <area>.js         # funções por área: listarClientes(filtros, sinal), salvarCliente(dados)...
├── sessao/               # useSessaoLoja / useSessaoSuperadmin: { estado, eu, entrar, sair, recarregar }
├── use<Area>.js          # hooks consumidos pelas telas (contrato de tela da especificação)
├── dominio.js            # enums da API com rótulo e tom
└── useAcesso.js          # níveis efetivos do GET /api/loja/eu
```

Telas de cadastro usam `components/CadastroTabela.jsx` com `lista = { itens, carregando, atualizando, erro, recarregar, salvar, excluir, carregarRegistro?, paginacao?, busca? }` (ela já trata loading, erro, 422/404/409 e trava o salvar); formulários avulsos usam `PainelFormulario` com `salvando`.

- **INT-01** **Um único cliente HTTP** (`data/api/cliente.js`). Nenhuma tela ou componente chama `fetch`/`axios` direto. Sem biblioteca nova sem justificativa (o `fetch` nativo resolve).
- **INT-02** Base URL por variável do Vite (`import.meta.env.VITE_API_URL`, com `.env.example`); em desenvolvimento, prefira o `server.proxy` do Vite para `/api` (evita CORS e cookie de outra origem).
- **INT-03** As telas consomem **hooks** com a assinatura do contrato de tela. O frontend-dev troca a implementação do hook (mock → API) **sem mudar a assinatura**. Se precisar mudar, relata ao coordenador.
- **INT-04** Todas as áreas já estão ligadas à API (o mock foi removido em 2026-10-02). Tela nova nasce com dados provisórios do frontend-ui no formato do contrato e o frontend-dev troca pelo hook da API. Nunca duas fontes da verdade para o mesmo dado na mesma tela.

## 2. Autenticação

- **INT-05** Token `Authorization: Bearer` anexado pelo cliente HTTP. Tokens diferentes para painel da loja e SUPERADMIN (nunca enviar um na área do outro).
- **INT-06** Guardar o token o mínimo possível: em memória + `sessionStorage` (sobrevive ao F5, some ao fechar a aba). Nunca em log, URL ou mensagem de erro. Logout limpa tudo (token, caches, estado do usuário).
- **INT-07** **401** em qualquer chamada: limpa a sessão e leva ao login da área, preservando a rota para voltar depois. **403 de loja suspensa** no login/`eu`: mostra a mensagem do servidor e não deixa entrar.
- **INT-08** Menu e botões usam `GET /api/loja/eu` (perfil, níveis efetivos, módulos ativos) via `useAcesso`; nunca deduzir permissão no navegador a partir do nome do perfil.

## 3. Conversão de dados

- **INT-09** API em `snake_case`, tela em `camelCase`: converter **só** em `data/api/conversao.js` (e nas funções de área), com mapeamento **explícito por campo** quando o nome muda (`estoque_minimo` → `minimo`, `nome` + `sobrenome` → `nomeCompleto`). Conversão recursiva genérica só para o caso trivial; nunca enviar campo extra que a API não espera (ela responde 422 `extra_forbidden`).
- **INT-10** Ids são **uuid (string)**: nunca `Number(id)`, `parseInt`, comparação numérica ou ordenação por id. Remova restos dos ids numéricos do mock.
- **INT-11** **Datas:** a API responde ISO com o fuso da loja (`2030-01-07T09:00:00-03:00`) e lê hora sem fuso como hora da loja. Para exibir, use o horário **como veio** na string (`lerDataHora`), nunca reconvertido para o fuso do navegador nem para um fuso global (loja de Manaus mostra -04:00 como veio); só UTC (`Z`) é levado ao fuso da loja. "Agora" é `agoraNaLoja()`. Teste com uma loja fora de America/Sao_Paulo. Para enviar, mande `AAAA-MM-DDTHH:mm:ss` sem fuso (hora da loja) ou com o offset da loja. `date` puro (`AAAA-MM-DD`) nunca vira `Date` (vira o dia anterior em UTC-3).
- **INT-12** **Dinheiro e quantidades** chegam como número: exibir com `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })` (ou o utilitário existente); enviar número com no máximo 2 casas; nunca concatenar string com número.
- **INT-13** **Paginação:** `{itens, total, pagina, por_pagina}` ligado à paginação da `Tabela` (servidor); filtros e busca vão para a query, não filtram só a página atual no navegador. Busca com debounce (~300 ms) ou `useDeferredValue`.
- **INT-14** Enums como vêm da API (`nao_compareceu`), com rótulo/tom pelos mapas de `data/` e `Etiquetas.jsx`. Valor desconhecido mostra um rótulo neutro, não quebra.

## 4. Nulos e respostas inesperadas (nada pode quebrar)

- **INT-15** Todo campo que o contrato marca como **pode ser null/faltar** tem tratamento: `?.` e `??` na conversão, padrão definido (lista vazia, "—"), nunca `undefined.algo`, `null.map`, "null"/"NaN"/"Invalid Date" na tela.
- **INT-16** Listas sempre como array na tela (`itens ?? []`), mesmo se a API devolver `null` ou faltar.
- **INT-17** Resposta 204/sem corpo não é passada a `response.json()`. Corpo que não é JSON (proxy, 502 HTML) vira erro genérico tratado.
- **INT-18** Erro de rede/timeout (`AbortController`, ~15 s) vira mensagem "Sem conexão com o servidor. Tente de novo." com ação de tentar novamente; nunca tela branca.

## 5. Erros por status

O cliente HTTP rejeita com um objeto padrão `{ status, mensagem, campos }`:

| Status | O que a tela faz |
|---|---|
| 401 | INT-07 (sessão) |
| 403 | Mensagem do servidor (`detail`); esconder/desabilitar a ação; se for módulo desligado, recarregar `eu` |
| 404 | "Não encontrado" (pode ter sido excluído ou ser de outra loja): fechar o painel e atualizar a lista |
| 409 | Mensagem do servidor ao lado do campo/ação relacionada (horário ocupado, nome repetido, exclusão com dependentes); manter o formulário preenchido |
| 422 | `erros[]` (`{campo, mensagem}`) mapeado para os campos do `Form` (`form.setFields`), convertendo o nome do campo da API para o da tela; o que não mapear vai para mensagem geral |
| 5xx / rede | Mensagem genérica + tentar de novo; logar no console só em desenvolvimento, sem dados pessoais |

- **INT-19** A mensagem mostrada é a do servidor (`detail`, já em português); não traduzir nem substituir por texto genérico quando ela existe.

## 6. Estado e mutações

- **INT-20** Carregamento, erro e dado vazio expostos pelo hook (`carregando`, `erro`), alimentando os estados da tela (skeleton, `EstadoVazio`, erro).
- **INT-21** Botão de salvar desabilitado/`loading` durante o envio (evita duplo clique = dois registros). Corrida: resposta de uma busca antiga não sobrescreve a mais nova (`AbortController` ou id da requisição). Desmontou? Cancela.
- **INT-22** Após salvar/excluir, atualizar a lista a partir do servidor (ou atualizar o item com a resposta da API, que traz `atualizado_em`/`atualizado_por_nome`). Atualização otimista só com reversão em caso de erro.
- **INT-23** Nunca reimplementar no navegador uma regra que a API já calcula (horários livres, permissões, conflito). O front pode pré-validar para UX, mas quem decide é a resposta da API.

## 7. Verificação

- **INT-24** Testar com o back-end real (`backend/README.md`: `docker compose up -d`, migrações, seed, `uvicorn`) e os usuários do seed: Administrador, Recepção e Profissional da Clínica Sorriso (permissões diferentes), login de loja suspensa (`clinica-bem-estar`), e pelo menos um caso de cada erro do contrato (409 e 422 no mínimo).
- **INT-25** `npm run lint` e `npm run build` em `frontend/` sem erros.
