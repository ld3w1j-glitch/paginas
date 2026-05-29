# Fase 4A — Portal Blueprint + ponte segura para migração

Esta etapa inicia a conversão para uma aplicação Flask única sem quebrar o que já funciona.

## O que mudou agora

- O portal principal passou a ter `create_portal_app()`.
- As rotas do portal foram movidas para `portal_blueprints.py`.
- Os programas foram registrados em uma lista central `PROGRAMS`.
- Foi criada a rota `/system/programs` para o front-end descobrir os programas disponíveis.
- A montagem antiga por `DispatcherMiddleware` foi isolada em `legacy_wsgi_bridge.py`.

## Por que ainda existe a ponte WSGI?

Os módulos grandes ainda usam `url_for()` e endpoints locais, por exemplo `url_for('login')`.
Se eles forem jogados dentro de Blueprint de uma vez, vários endpoints passam a virar
`curso.login`, `prompt.login`, etc. Isso pode quebrar login, templates e redirecionamentos.

Por isso esta fase faz a migração segura:

1. Centraliza portal, config e registro dos programas.
2. Mantém URLs antigas funcionando.
3. Prepara cada módulo para ser convertido um por vez.

## Próxima etapa recomendada

Converter primeiro o `editor_admin_app`, porque é pequeno. Depois `financeiro_app`, depois
`prompt_app`, e por último `curso_ingles_app/app.py`, que ainda é o maior arquivo.
