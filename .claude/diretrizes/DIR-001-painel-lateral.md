---
id: DIR-001
titulo: Painel lateral em vez de modal
status: ativa
escopo: [frontend-ui, frontend-dev, revisor]
onde: frontend/src/pages/**, frontend/src/superadmin/**, frontend/src/components/**
criada_em: 2026-10-02
substitui: —
---

## Ordem do usuário
Aprovou o painel lateral na tela Clientes e pediu para generalizar para todas as telas (2026-10-02).

## Regra
Tudo que cria, edita ou consulta um registro por cima de uma tela é um painel lateral à direita: `PainelFormulario` (formulário) ou `PainelLateral` (consulta), de `components/base/`. Nunca `Modal` centralizado, nunca `Drawer` montado à mão, nunca `ModalFormulario`. Detalhes: `padroes-ui` UI-06 a UI-13.

## Exceções
`Popconfirm`/`modal.confirm` de confirmação curta, menu em gaveta da `Casca`, `PainelDemonstracao`.

## Como verificar
- `grep -rn "from 'antd'" frontend/src | grep -E "\bModal\b|\bDrawer\b"`: todo uso encontrado é uma exceção listada acima.
- Nenhuma importação de `ModalFormulario`.
- Tela nova com formulário: abre `PainelFormulario`, com aviso de alterações não salvas.

## Aplicação no código existente
- [x] Todas as telas dos painéis migradas (2026-10-02).
