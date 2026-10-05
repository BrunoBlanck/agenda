# Cores do site escolhidas pela loja

- **Slug:** cores-site · **Branch:** feat/cores-site (a partir de `feat/site-agendamento`, onde o site existe) · **Status:** aprovada
- **Área:** painel da loja · SUPERADMIN · site do consumidor
- **Pedido original:** "Preciso adicionar uma configuração no painel para poder escolher as cores no site. Pode ser na aba Configurações." Hoje as cores do site (`/{slug}`) são fixas por tipo de loja em `backend/app/static/site/site.css` (SIT-09).

## 1. Objetivo
A loja deixa o site de agendamento com as cores da sua marca, sem depender do suporte. Uso raro (ao configurar a loja ou mudar a identidade). O SUPERADMIN também ajusta, ao criar ou dar suporte a uma loja.

## 2. Regras de negócio
| Código | Regra | Onde é garantida |
|---|---|---|
| SIT-13 (nova) | A loja pode escolher **duas cores** do site do consumidor: **topo** (cabeçalho) e **destaque** (botões, dia e horário escolhidos, links, indicador de passos). Cada uma é opcional: vazia = cor da paleta do tipo da loja (SIT-09). "Voltar ao padrão" limpa a cor | banco + rota + site |
| SIT-14 (nova) | Formato `#RRGGBB` (aceita maiúsculas, grava em minúsculas). Contraste: o texto **branco** sobre cada cor precisa de pelo menos **4,5:1** (WCAG AA). Cor que não passa é recusada com mensagem em português | banco (CHECK de formato) + rota (contraste, 422) + tela (aviso antes de salvar) |
| SIT-15 (nova) | No modo escuro do site, o topo usa a cor escolhida; o destaque é clareado automaticamente até ter 4,5:1 sobre o fundo escuro do site (a loja não escolhe cor para o modo escuro) | site (CSS gerado) |
| PLA (nova, PLA-20) | O SUPERADMIN edita as mesmas cores no detalhe da loja; a alteração entra na auditoria com o `superadmin_id` e `atualizado_por` NULL (GER) | rota superadmin |
| DIR-003 | O site continua sem nenhum caminho para o painel. (O painel **pode** linkar para o site: "Ver site".) | site |

**Diretrizes aplicáveis:** `DIR-001` (painel lateral: não abrir modal; aqui é uma seção na própria tela), `DIR-002` (identidade visual do painel: a seção usa só tokens do painel — as cores escolhidas aparecem **apenas** na pré-visualização do site), `DIR-003`.

**Acesso:**
- Painel da loja: ver = leitura em `config_loja`; salvar = escrita em `config_loja`. Sem módulo (Configurações é sempre ligado).
- SUPERADMIN: qualquer superadmin logado (como o resto do detalhe da loja).

## 3. Banco
Migração `0006_cores_site`:
- `loja_configuracoes.cor_site_topo varchar(7) NULL`
- `loja_configuracoes.cor_site_destaque varchar(7) NULL`
- `CHECK (cor_site_topo IS NULL OR cor_site_topo ~ '^#[0-9a-f]{6}$')` e o mesmo para `cor_site_destaque` (nomes `ck_loja_configuracoes_cor_site_topo` / `_destaque`).
- Triggers de alteração e auditoria já existem na tabela. Downgrade remove as colunas.
- `estrutura.md` 2.21 ganha as duas colunas (o coordenador atualiza).

## 4. Contrato da API

Objeto `CoresSite` (mesmo formato nas duas áreas):
```json
{
  "cor_topo": "#0d4b4f",          // string|null — null = padrão do tipo
  "cor_destaque": null,           // string|null
  "padrao": { "cor_topo": "#0d4b4f", "cor_destaque": "#0b6767" },  // paleta do tipo da loja (para "Voltar ao padrão" e pré-visualização)
  "tipo": "clinica",
  "criado_em": "datetime", "atualizado_em": "datetime",
  "atualizado_por": "uuid|null", "atualizado_por_nome": "string|null"
}
```
- A paleta padrão por tipo fica **num lugar só** no back-end (ex.: `app/services/cores_site.py`) e o `site.css` continua com os mesmos valores (teste garante que batem).

Entrada `CoresSiteEntrada`:
| Campo | Tipo | Obrigatório | Null | Regra |
|---|---|---|---|---|
| `cor_topo` | string | sim | sim | `null` = padrão; senão `#RRGGBB` (com ou sem maiúsculas; espaços em volta ignorados); contraste ≥ 4,5:1 com branco |
| `cor_destaque` | string | sim | sim | idem |

### `GET /api/loja/configuracoes/site` · `PUT /api/loja/configuracoes/site`
- **Permissão:** GET `exigir("config_loja")`; PUT `exigir("config_loja", "escrita")`.
- **Saída 200:** `CoresSite`.
- **Erros:**
  | Status | Quando | `detail` |
  |---|---|---|
  | 401 | sem token | Faça login para continuar. |
  | 403 | sem leitura/escrita | mensagens atuais de `exigir()` |
  | 422 | formato inválido | `erros: [{campo: "cor_topo"|"cor_destaque", mensagem: "Informe a cor no formato #RRGGBB."}]` |
  | 422 | contraste insuficiente | `erros: [{campo, mensagem: "Cor muito clara: o texto branco fica difícil de ler. Escolha uma cor mais escura."}]` |

### `GET /api/superadmin/lojas/{loja_id}/site` · `PUT /api/superadmin/lojas/{loja_id}/site`
- **Permissão:** superadmin logado.
- Mesma entrada/saída e erros, mais **404** "Loja não encontrada." (inexistente ou excluída).

### Site do consumidor (`/{slug}` e páginas do fluxo)
- Com cor(es) escolhida(s), as páginas aplicam as variáveis CSS correspondentes por cima da paleta do tipo: `--cor-topo`, `--cor-destaque` e as derivadas (`--cor-destaque-suave` = destaque misturado com branco a ~12%; no modo escuro, SIT-15).
- **Sem enfraquecer a CSP** atual (`CSP_SITE`): nada de `unsafe-inline`. Opções aceitáveis: `<style>` com **nonce** por resposta, ou um CSS por loja servido pelo back-end (ex.: `/static/site/cores.css?loja=<slug>&v=<hash das cores>`) — o backend escolhe e justifica. Os valores vêm do banco já validados (CHECK) e mesmo assim são reescritos a partir do hex validado (nunca texto livre no CSS).
- Sem cores escolhidas, o HTML/CSS é o mesmo de hoje.

### Testes obrigatórios (backend)
- GET/PUT da loja e do superadmin; `null` volta ao padrão; maiúsculas normalizadas.
- Formato inválido (`#fff`, `red`, `#12345g`, `url(...)`, `;}` etc.) → 422 no campo certo; banco recusa formato inválido mesmo sem a rota (CHECK).
- Contraste: cor clara (ex.: `#ffeb3b`) → 422; limite (cor com exatamente ~4,5:1) aceita.
- Permissões: leitura não grava (403); Profissional sem acesso a `config_loja` → 403; token de funcionário nas rotas do superadmin → 401.
- Isolamento: loja A não lê nem altera cores da loja B (só existe a rota da própria loja; o superadmin com id inexistente → 404).
- Auditoria: alteração pela loja registra o funcionário; pelo superadmin registra `superadmin_id` e origem `superadmin`.
- Site: com cores, as páginas do fluxo usam as cores escolhidas (e a CSP continua sem `unsafe-inline`); sem cores, igual a hoje; outra loja não é afetada; padrão do back-end = valores do `site.css`.

## 5. Contrato de tela

### Painel da loja — `Configurações › Dados da loja` (`frontend/src/pages/ConfigLoja.jsx`)
Nova seção **"Cores do site"** (componente `Secao`, como as outras da página), depois dos dados da loja:

```
 Cores do site
 Usadas no site de agendamento dos clientes. Vazio = cores padrão de <Clínica>.

 Cor do topo        [■] [ #0D4B4F ]   Voltar ao padrão
 Cor de destaque    [■] [ #0B6767 ]   Voltar ao padrão

 Pré-visualização                                 Ver site ↗
 ┌──────────────────────────────────────────────┐
 │███ Clínica Sorriso ██████████████████████████│  ← cor do topo, texto branco
 │  Limpeza · 60 min                            │
 │  [Ter 06/10]  [ 09:00 ]   [ Pedir agendamento ]│ ← destaque (dia/horário escolhido, botão)
 └──────────────────────────────────────────────┘
 ⚠ Cor de destaque muito clara: o texto branco fica difícil de ler.

                                         [Salvar cores]
```
- Seletor de cor (`ColorPicker` do antd, sem transparência, formato hex) + campo de texto hex sincronizados. Campo vazio = padrão (mostra a cor padrão como placeholder/amostra esmaecida).
- **Pré-visualização** é uma miniatura estática do site (cabeçalho + um dia + um horário + botão) usando as cores escolhidas (ou as padrão). As cores do site aparecem **só dentro** da pré-visualização (DIR-002).
- Aviso de contraste calculado no navegador com a mesma fórmula (WCAG, luminância relativa) **antes** de salvar; o botão salvar continua habilitado e a API decide (GER-02). Erro 422 da API vai para o campo certo.
- "Ver site ↗" abre `/{slug}` em nova aba (`<a target="_blank" rel="noopener">`).
- Somente leitura (leitura em `config_loja`): campos desabilitados, sem botão salvar, pré-visualização visível.

### SUPERADMIN — detalhe da loja (`frontend/src/superadmin/pages/LojaDetalhe.jsx`)
Nova aba **"Site"** (depois de "Dados gerais") com **o mesmo componente** da seção acima (reutilizado, recebendo o hook por props), e o link "Abrir site" que já existe no cabeçalho.

### Hooks de dados (fronteira frontend-ui ↔ frontend-dev)
| Hook | Retorna | Ações |
|---|---|---|
| `useCoresSite()` em `frontend/src/data/useConfigLoja.js` (painel da loja) | `{ cores: CoresSite \| null, carregando, erro, recarregar }` | `salvar({ corTopo, corDestaque }) → Promise<CoresSite>` |
| `useCoresSiteLoja(lojaId)` em `frontend/src/superadmin/usePlataforma.js` (ou arquivo de hooks do superadmin equivalente) | idem | idem |

Formato na tela:
| Tela | API | Tipo | Pode ser null |
|---|---|---|---|
| `corTopo` | `cor_topo` | string `#rrggbb` | sim (padrão) |
| `corDestaque` | `cor_destaque` | string | sim |
| `padrao.corTopo` / `padrao.corDestaque` | `padrao.cor_topo` / `padrao.cor_destaque` | string | não |
| `tipo` | `tipo` | `clinica`\|`barbearia`\|`escola` | não |
| `atualizadoEm`, `atualizadoPorNome` | controle | (via `lerControle`) | sim |

Erros das ações: `ErroApi` do projeto, `{ status, mensagem, campos: [{ campo: 'cor_topo'|'cor_destaque', mensagem }] }`; o `useTratarErro` converte para `corTopo`/`corDestaque` (correção aceita do frontend-ui). Nome e slug da loja não vêm em `CoresSite`: a tela usa os que já tem (`dados` em ConfigLoja, `loja` no SUPERADMIN).

### Estados obrigatórios
Carregando (skeleton da seção), erro ao carregar (mensagem + "Tentar de novo"; resto da página funciona), sem cores escolhidas (mostra padrão), uma cor escolhida e outra padrão, cor inválida digitada (aviso no campo, não quebra a pré-visualização: usa o padrão enquanto o texto não for um hex válido), contraste insuficiente (aviso), somente leitura, salvando, nome de loja longo na pré-visualização (corta com reticências), largura de celular (seção empilha).

## 6. Critérios de aceite
- [ ] Administrador da Clínica Sorriso escolhe topo `#7a1f3d` e destaque `#1f5f8b`, salva, abre o site e vê as cores novas em todos os passos.
- [ ] "Voltar ao padrão" em uma cor e salvar: o site volta à cor do tipo só naquela parte.
- [ ] Cor clara (ex.: amarelo `#ffeb3b`) mostra o aviso na tela e a API recusa (422 no campo).
- [ ] SUPERADMIN muda as cores na aba "Site" da loja; a loja vê a mudança no painel e no site; a auditoria mostra o superadmin.
- [ ] Usuário com só leitura em `config_loja` vê as cores sem alterar (API 403 no PUT); Recepção e Profissional (sem acesso a `config_loja` nos perfis padrão) não veem a tela e a API dá 403.
- [ ] Outra loja continua com as próprias cores.
- [ ] O site continua funcionando sem JS, com a CSP sem `unsafe-inline`, e no modo escuro o destaque continua legível.
- [ ] Nada quebra com cores nulas, inválidas digitadas ou nome longo.

## 7. Fora do escopo
- Escolher fonte, imagem de fundo ou cores do modo escuro.
- Cores no painel da loja (o painel tem identidade própria, DIR-002).
- Paletas prontas.

## 8. Decisões e perguntas
- Decisão do usuário (2026-10-05): **duas cores livres** (topo e destaque); editáveis pela **loja e pelo SUPERADMIN**.
- **Divergências do backend aceitas (2026-10-05):** texto vazio ou só espaços = `null` (padrão); chave ausente no corpo = 422 "Campo obrigatório."; campos extras ignorados (`extra='ignore'` da base `Entrada`); `atualizado_por`/`atualizado_por_nome` `null` quando quem alterou foi o superadmin (o nome fica na auditoria); `atualizado_em` é o da linha de `loja_configuracoes` (editar rótulos de Local também muda). CSP por **nonce** por resposta, só quando há cor escolhida.
- Fora do escopo, corrigido pelo backend: teste instável do site (`test_envios_simultaneos_do_mesmo_formulario_no_limite_de_pendentes`) — envio repetido que encontrava o horário já ocupado pelo outro envio não conferia `pedido_repetido` (LOG-07), `paginas.py:570`.
- Regra de contraste fixa em 4,5:1 com texto branco (AA para texto normal). Provisório: sem opção de texto escuro sobre cor clara.

## 9. Histórico de revisão
- **2026-10-05 · rodada 1 · APROVADO**, sem achados. backend 860 passed / 1 skipped, ruff ok; frontend lint (0 erros) e build ok; navegador com banco e portas próprios. Conferidos: injeção pelas cores (fuzz no PUT, CSS reescrito do RGB, nonce por resposta, CSP sem `unsafe-inline`), contraste idêntico no front e no back nas 16.777.216 cores, isolamento, auditoria do superadmin, correção em `paginas.py:570` e testes de migração ajustados. Sugestões não aplicadas:
  - S1 (backend): SIT-14 garante só branco sobre a cor; a mesma cor como texto de link sobre fundos claros derivados (ex.: "Trocar horário" sobre `.resumo`) pode ficar abaixo de 4,5:1 com cores no limite (ex.: `#767676` → 3,95:1). Cores padrão e do critério de aceite passam com folga.
  - S2 (coordenador): critério da Recepção corrigido na seção 6 (aplicada).
  - S3 (backend): GET cria a linha de `loja_configuracoes` quando falta (leitura que grava; só em loja antiga sem a linha).
  - S4 (frontend-dev): `padrao.corTopo` pode vir `null` em resposta fora do contrato (só aviso do ColorPicker no console).
