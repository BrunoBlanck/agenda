# Plataforma / SUPERADMIN (`PLA-*`)

Fonte: `estrutura.md` seção 1 e 6.2. Rotas em `/api/superadmin/...` (só token de superadmin). Telas em `frontend/src/superadmin/`.

## Lojas
- **PLA-01** Superadmin cria e edita lojas: tipo, razão social, nome fantasia, CNPJ (único quando preenchido), `slug` (único entre não excluídas; só minúsculas, números e hífens), contato, endereço, fuso (padrão `America/Sao_Paulo`), plano e status.
- **PLA-02** Criar loja gera, no mesmo fluxo: os **perfis padrão** (ACE-16), uma linha de `loja_funcionalidades` por módulo opcional (habilitado conforme marcado), a linha de `loja_configuracoes` e o **primeiro funcionário** com perfil Administrador.
- **PLA-03** Status `ativa`, `suspensa`, `cancelada`; qualquer troca é permitida (inclusive reativar cancelada). Suspensa: ninguém faz login, dados mantidos. Cancelada: dados mantidos.
- **PLA-04** **Excluir** (lógica) só loja `cancelada`; o `slug` fica livre de novo. Loja excluída some do painel, do login e do site.
- **PLA-16** **Slugs reservados** (viram o primeiro pedaço da URL, GER-29): `superadmin`, `api`, `painel`, `site`, `docs`, `redoc`, `openapi`, `admin`, `login`, `static`, `assets`, `app`, `www`, `saude`, `health`. Recusados com 422 no campo `slug` e por CHECK no banco.

## Acessar loja (suporte)
- **PLA-17** No detalhe da loja, **Acessar loja** gera uma sessão do painel como o **Administrador da loja** (funcionário ativo com o perfil Administrador padrão, o mais antigo). Tudo que for feito nela fica registrado **como esse Administrador** (decisão do usuário). O ato de gerar o acesso entra na auditoria da loja como ação do superadmin (PLA-14).
- **PLA-18** A sessão dura **1 hora**, sem renovação.
- **PLA-19** Vale para loja ativa, suspensa ou cancelada (funcionários continuam bloqueados pela GER-25); loja excluída = 404; sem Administrador ativo = 409.

## Módulos da loja
- **PLA-05** Lojas › Módulos: liga/desliga cada módulo opcional, com observação e prazo (`expira_em`, sem fuso = fuso da loja). `PATCH` só muda os campos enviados. Recusa módulo não opcional. Ver ACE-06 a ACE-09.

## Funcionários pelo suporte
- **PLA-06** O superadmin cria, edita, inativa e redefine a senha de funcionários de qualquer loja, e pode atribuir qualquer perfil (inclusive Administrador), respeitando ACE-20 (loja nunca sem Administrador ativo). Usa `perfil_id`.
- **PLA-07** **Senha provisória (provisória até existir e-mail):** criar loja/funcionário/usuário admin sem senha, ou redefinir sem senha, gera uma senha aleatória devolvida **uma única vez** em `senha_provisoria`. A auditoria registra a troca sem o valor (`senha: •••••• → redefinida`).

## Planos
- **PLA-08** Plano = nome (único) + preço mensal (+ descrição). **Não define nem limita módulos** nem nada de acesso.
- **PLA-09** Plano inativo não é escolhido para loja nova nem trocado numa loja (quem já tem, mantém). Plano com lojas não excluídas não é excluído (inative).

## Usuários admin
- **PLA-10** Só contas de superadmin (usuários de loja são cadastrados na loja). E-mail único sem diferenciar maiúsculas.
- **PLA-11** Ninguém se exclui nem se desativa; sempre resta **pelo menos um superadmin ativo** (conferido com as contas travadas, `FOR UPDATE`).

## Auditoria
- **PLA-12** Sempre **uma loja por vez** (ou "Plataforma"): escolhe loja, tabela (só as do catálogo da área) e período (`hoje`, `7d`, `30d` padrão, `90d`, `ano`, `intervalo`), nos dias do fuso da loja. Filtro por pessoa: `f:<id>`, `s:<id>`, `site`, `sistema`.
- **PLA-13** Cada item mostra quando, quem (nome resolvido), operação, `rotulo` do registro e `mudancas` (campo, antes, depois) vindas do servidor; o navegador não compara `antes`/`depois`. Paginada.
- **PLA-14** Ações sem alteração de linha (entrar como a loja, enviar link de senha) também entram na auditoria (`registrar_acao`).

- **PLA-20** O SUPERADMIN edita as cores do site da loja (SIT-13/14) na aba **Site** do detalhe da loja (`GET/PUT /api/superadmin/lojas/{id}/site`). A alteração fica com `atualizado_por` NULL e a auditoria guarda o `superadmin_id` (origem `superadmin`).

## Catálogos fixos
- **PLA-15** Tipo da loja, módulos e recursos mudam **só por migração**, junto com o código. Não há tela de cadastro para eles.
