---
name: painel-lateral
description: Decisão de 2026-10-02 - todo formulário/consulta que abre por cima de uma tela é painel lateral (PainelLateral/PainelFormulario); ModalFormulario foi removido
metadata:
  type: project
---

Desde 2026-10-02 não existe mais modal de formulário: tudo que cria, edita ou consulta um registro por cima de uma tela é o painel lateral à direita. O usuário aprovou o padrão na tela Clientes e pediu para generalizar.

**Why:** a lista continua visível atrás com a origem destacada, o cabeçalho diz o que está sendo editado, e o aviso de alterações não salvas evita perder o que a recepção digitou.

**How to apply:**
- Consulta: `PainelLateral`. Formulário: `PainelFormulario` (constrói sobre o primeiro). Estado com `usePainel()` (aberto separado do registro; `destaqueId` para a origem). `Tabela` aceita `destaqueId`; cartões da agenda usam a classe `em-edicao`.
- Marca do registro no cabeçalho: iniciais (pessoa, ignora "Dr./Dra./Prof."), `icone` (serviço, local, material, plano) ou `cor` (anel com a cor do profissional na agenda). Registro novo = círculo tracejado.
- Nunca empilhar: atalho para outra visão usa `fechar(depois)`; no agendamento, "Ver histórico" fecha o agendamento e abre o histórico (com alterações, pergunta antes de descartar).
- Não depender de `afterOpenChange` (só dispara no fim da animação; no Playwright desta máquina o rAF fica suspenso e ele nunca chega): reset de estado ao abrir é feito na renderização (padrão "estado anterior").
- Playwright aqui: chamar `page.bringToFront()` e forçar um quadro (redimensionar 1 px) antes de screenshot, senão a imagem sai velha.
- Exceções: Popconfirm/modal.confirm, menu em gaveta da Casca, PainelDemonstracao.
Relacionado: [[padroes-de-tela]], [[identidade-visual]]
