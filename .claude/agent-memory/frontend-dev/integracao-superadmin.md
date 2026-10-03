---
name: integracao-superadmin
description: Armadilhas confirmadas da API do SUPERADMIN e do back-end em geral (datas em UTC "Z", ruído de login na auditoria, senha provisória)
metadata:
  type: project
---

Confirmado contra a API real em 2026-10-02:
- As colunas de controle (`criado_em`, `atualizado_em`, `ultimo_login_em`) saíam em UTC com "Z" (Pydantic), e a
  conversão do front lê a "hora de parede" cortando o offset: mostrava 3h a mais. No SUPERADMIN o back-end passou a
  converter (fuso da loja ou da plataforma). No painel da loja (schema `Controle` em `schemas/comum.py`) isso ficou
  relatado ao coordenador. **Why:** `lerDataHora`/`dataHoraBR` descartam o offset de propósito. **How to apply:** ao ligar
  uma área, confira se as datas da resposta têm offset da loja (`-03:00`), não "Z".
- Todo login grava `ultimo_login_em` e vira "alterar" na auditoria (inclusive do superadmin): a visão geral filtra isso.
- `senha_provisoria` vem uma única vez: nunca em `navigate(..., { state })` (fica em `history.state`; o revisor reprovou na rodada 2,
  2026-10-02). Lojas → detalhe passa pela memória de módulo (`entregarSenhaDaLojaNova`/`useSenhaDaLojaNova` em usePlataforma.js).
- Loja de teste: `DELETE /lojas/{id}` só depois de `POST /lojas/{id}/status {"status":"cancelada"}` (senão 409).
