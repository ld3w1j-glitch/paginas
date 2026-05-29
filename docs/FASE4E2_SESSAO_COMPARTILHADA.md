# Fase 4E.2 — Correção de sessão compartilhada entre módulos

## Problema

Ao fazer login no Prompt Profissional e depois acessar o Financeiro, o Flask-Login aceitava a sessão já autenticada, mesmo sendo de outro módulo.

Isso fazia o Financeiro receber um `current_user` do Prompt. Como o usuário do Prompt não possui o relacionamento `transactions`, a tela `/financeiro/dashboard` quebrava com:

```text
AttributeError: 'User' object has no attribute 'transactions'
```

## Correção

- Adicionado isolamento de sessão no Blueprint do Financeiro.
- Adicionado isolamento de sessão no Blueprint de autenticação do Financeiro.
- Adicionado isolamento de sessão no Blueprint do Prompt Profissional.
- Se o usuário estiver logado em outro módulo, a sessão é encerrada e o sistema direciona para o login correto.
- O dashboard financeiro deixou de depender diretamente de `current_user.transactions` e passou a calcular totais via consulta por `user_id`.

## Resultado

Agora um login do Prompt não entra automaticamente no Financeiro, e um login do Financeiro não entra automaticamente no Prompt.
Cada módulo exige sua identidade correta antes de acessar páginas protegidas.
