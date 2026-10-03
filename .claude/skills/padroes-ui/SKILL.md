---
name: padroes-ui
description: Padrões obrigatórios das telas dos painéis React deste projeto (loja e SUPERADMIN) - componentes base, painel lateral, tokens da identidade visual, estados de tela, formulários, texto e sinais proibidos de tela genérica - em forma de checklist. Use ao criar, alterar ou revisar telas e componentes em frontend/src.
user-invocable: false
---

# Padrões de UI dos painéis

Checklist usado pelo **frontend-ui** ao construir e pelo **revisor** ao conferir (códigos `UI-*`). A memória do frontend-ui (`.claude/agent-memory/frontend-ui/`) guarda as decisões de identidade e as armadilhas do antd 6 já resolvidas: leia antes de mexer em estilo.

## 1. Montagem da tela

- **UI-01** Toda tela começa com `Pagina` (título, descrição, ações) e agrupa o conteúdo em `Secao` (`rente` para tabela encostada). Cadastro simples = `CadastroTabela` (já monta busca + tabela + painel lateral).
- **UI-02** **Procure antes de criar** (Grep/Glob em `components/`, `components/base/`, `layout/`, `utils/`, `data/`). Já existem: `Pagina`, `Secao`, `Tabela`, `BarraFiltros`, `EstadoVazio`, `Etiqueta`, `PontoCor`, `CarregandoPagina`, `LimiteErro`, `PainelLateral`, `PainelFormulario`, `usePainel`, `CadastroTabela`, `Etiquetas`, `UltimaAlteracao`, `LocalInfo`, `ResumoCliente`, `CanaisCliente`, `HistoricoCliente`, `utils/formatos.js`, `utils/cep.js`.
- **UI-03** Se existe e serve quase, **estenda por props** com padrão sensato. Trecho repetido pela segunda vez vira componente (`components/`), hook (`data/`) ou função pura (`utils/`).
- **UI-04** Componentes pequenos, uma responsabilidade, props com nomes de domínio, composição por `children`, sem dezenas de booleanos.
- **UI-05** Tela não acessa mock, `fetch` nem API direto: lê e grava **só pelos hooks de `data/`** definidos no contrato de tela da especificação.

## 2. Painel lateral (obrigatório)

- **UI-06** Tudo que **cria, edita ou consulta** um registro por cima da tela é painel lateral à direita: formulário → `PainelFormulario`; consulta → `PainelLateral`. Nunca `Modal` centralizado nem `Drawer` montado na mão. `ModalFormulario` está descontinuado.
- **UI-07** Cabeçalho: `titulo` (a ação: "Editar cliente") + `nome` (quem, com iniciais/ícone/cor); registro novo mostra o círculo tracejado; X à direita; atalhos em `extra(fechar)`.
- **UI-08** Corpo em seções `<h3 className="grupo-formulario">`, campos na ordem em que a pessoa tem a informação, foco no primeiro campo ao abrir.
- **UI-09** Rodapé fixo: `UltimaAlteracao` à esquerda; Cancelar + botão primário com o verbo à direita. Somente leitura: só "Fechar".
- **UI-10** Alterações não salvas: marca "Alterações não salvas" e pergunta "Descartar alterações?" ao fechar (X, Esc, clique fora, Cancelar). Não contornar.
- **UI-11** Origem destacada (`destaqueId` na `Tabela`, `em-edicao` nos cartões); estado `aberto` separado do registro (`usePainel`); **nunca empilhar** painéis (use `fechar(depois)`).
- **UI-12** Largura 480 px (até 560–720 px só se o conteúdo pedir); tela cheia no celular.
- **UI-13** Exceções permitidas: `Popconfirm`/`modal.confirm` de confirmação curta, menu em gaveta da `Casca`, `PainelDemonstracao`.

## 3. Identidade visual e estilo

- **UI-14** Cores, espaços, raios e fontes **só por tokens**: `theme.token` do `ConfigProvider` (`tema.js`) e variáveis CSS em `:root` (`index.css`); no JSX, `theme.useToken()`. Nenhuma cor hexadecimal solta. Mudou cor? Mude nos dois lugares.
- **UI-15** Identidade "agenda de papel": tinta `#2340A8`, grafite `#1E2230`, papel `#F3F4F7`, marca-texto `#FFE45C` (só para o que pede atenção agora: pendente, hoje, repor). Superfícies com borda e sem sombra; sombra só em camadas flutuantes. Raio 10 contêiner / 6 controle / 4 etiqueta. Fonte Atkinson Hyperlegible Next.
- **UI-16** `style={{...}}` só para valor dinâmico; estilo fixo em CSS com classes nomeadas pelo componente (`.agenda-semana-dia`). CSS por área importado pelo componente quando o `index.css` crescer.
- **UI-17** Espaçamento na escala 4, 8, 12, 16, 24, 32, 48; mais espaço entre grupos do que dentro deles. Hierarquia por peso/tamanho/cor do texto (`colorText`, `colorTextSecondary`, `colorTextTertiary`) antes de caixas e bordas. Um ponto focal por tela.

## 4. Ferramenta de trabalho

- **UI-18** Densidade alta e legível; números à direita com `tabular-nums`; datas `dd/MM`; horas "9h", "14h30" (`horaCurta`) na exibição e `HH:mm` em formulários.
- **UI-19** Status sempre por `components/Etiquetas.jsx` (tom + ícone + texto); mapas de status em `data/` usam `tom`.
- **UI-20** Ação principal visível sem rolagem; atalhos do fluxo diário (agendar a partir de horário vazio, busca por nome/telefone/CPF no mesmo campo). Início mostra o que fazer agora, não grade de KPIs.
- **UI-21** Textos que dependem da loja vêm de dados (ex.: rótulo de local "Sala"/"Cadeira" de `loja_configuracoes`), nunca fixos.

## 5. Estados (toda tela e todo componente de dados)

- **UI-22** **Carregando:** skeleton no formato real (não spinner centralizado).
- **UI-23** **Vazio:** explica e oferece a ação ("Nenhum agendamento hoje. Agendar horário").
- **UI-24** **Erro:** diz o que aconteceu e como resolver; erro de campo ao lado do campo.
- **UI-25** **Sem permissão:** `nenhum` esconde; `leitura` mostra sem botões de alterar (ou desabilitados com motivo). **Módulo desligado:** a área some do menu e campos dependentes somem dos formulários (ex.: sem Locais, o agendamento não pede local).
- **UI-26** **Dado longo** (nome de 60 caracteres, preço de 5 dígitos), **um item**, **muitos itens** (paginação/`virtual`), **campo opcional vazio** (mostra "—" ou nada, nunca "null"/"undefined"/"NaN"/"Invalid Date").

## 6. Formulários

- **UI-27** Rótulo sempre visível; máscaras e validação de `utils/formatos.js` (CPF/CNPJ, telefone, CEP); validação no blur e no envio com mensagem de como corrigir; preencher automaticamente o que der (duração pelo serviço, endereço pelo CEP).
- **UI-28** `Form` do antd com `valoresIniciais` + `destroyOnHidden` + `preserve={false}`; padrões de registro novo em `valoresNovo`, nunca `initialValue` no `Form.Item`; botão submit oculto para o Enter enviar; `message`/`modal` via `App.useApp()`.
- **UI-29** Botão diz o que acontece ("Agendar", "Salvar cliente") e a confirmação usa o mesmo verbo ("Cliente salvo"). Ação destrutiva confirma dizendo o que será afetado; reversível prefere "Desfazer".

## 7. Texto (pt-BR)

- **UI-30** Frases curtas, voz ativa, maiúscula só no início, vocabulário do negócio ("atendimento", "encaixe", "folga"), sem jargão de sistema ("registro", "entidade", "submeter"), sem emoji, sem marketing no painel, dados de exemplo realistas (nomes brasileiros, serviços reais).

## 8. Proibido (sinais de tela genérica de IA)

- **UI-31** Gradiente roxo/azul decorativo, blobs, glassmorphism; grade de cards iguais com ícone + número grande + "+12%"; hero centralizado genérico; mesma sombra e raio em tudo; tudo dentro de card; eyebrow em CAIXA ALTA; "A · B · C"; "→" no fim do botão; palavra do título em outra cor; 01/02/03 sem sequência; fade+subir em cada bloco; hover que levanta card; "Lorem"/"Gerencie tudo em um só lugar".

## 9. Piso de qualidade

- **UI-32** Responsivo até 360 px sem rolagem horizontal da página; foco de teclado visível; tudo clicável é `button`/`a` (nunca `div` com `onClick`); contraste AA; `aria-label` em botão só com ícone; `prefers-reduced-motion`; animação só com `transform`/`opacity`.
- **UI-33** Rotas com `lazy()` + fallback com formato da tela; `LimiteErro` por rota; painel da loja e SUPERADMIN em chunks separados; `key` estável (id), nunca índice.
- **UI-34** Estado derivado calculado na renderização (sem `useEffect` + `useState` para isso); `useEffect` só para sincronizar com algo externo.
- **UI-35** Site do consumidor (`frontend/src/site/`) é protótipo: não investir, não compartilhar componentes com o painel. Painel não importa nada de `site/`.
