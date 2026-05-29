# Fase 4D — Financeiro como Blueprint nativo

Nesta fase o módulo `financeiro_app` deixou de ser montado pelo `DispatcherMiddleware` e passou a ser registrado diretamente no portal principal como Blueprint em `/financeiro`.

## O que mudou

- `financeiro_app.init_financeiro_app(app)` inicializa o módulo dentro do portal.
- As rotas financeiras agora usam endpoints próprios:
  - `financeiro.*` para páginas principais.
  - `financeiro_auth.*` para login, registro e logout.
- Os templates foram isolados em `financeiro_app/templates/financeiro/` para evitar conflito com `base.html`, `index.html` e outros nomes repetidos em outros módulos.
- Os assets estáticos do financeiro são servidos por `financeiro.static`.
- `/financeiro` foi removido da ponte WSGI temporária.
- `/system/programs` agora marca o financeiro como `blueprint_nativo`.

## Autenticação compartilhada

Como agora Prompt e Financeiro rodam dentro do mesmo app Flask, foi criado um `login_manager` compartilhado em `extensions.py`.

Para evitar colisão entre usuários de tabelas diferentes, os modelos usam IDs prefixados:

- Prompt: `prompt:<id>`
- Financeiro: `financeiro:<id>`

O loader central identifica o prefixo e carrega o usuário correto.

## O que ainda falta

O `curso_ingles_app` continua temporariamente na ponte WSGI. Ele é o maior módulo e deve ser migrado por partes na próxima fase para reduzir risco de quebra em rotas, templates, login e Chat Agente.
