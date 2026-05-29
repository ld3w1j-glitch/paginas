# Fase 4B — Editor Admin convertido para Blueprint

## O que mudou

O módulo `editor_admin_app` deixou de ser montado pelo `DispatcherMiddleware` como uma aplicação Flask separada e passou a ser registrado diretamente no portal principal como um Blueprint real.

Agora o portal principal faz:

```python
app.register_blueprint(portal_bp)
app.register_blueprint(editor_admin_bp)
```

E a ponte WSGI continua apenas para os módulos maiores:

- `/prompt`
- `/financeiro`
- `/curso-ingles`

## Por que começar pelo Editor Admin

O Editor Admin é o módulo menor e mais seguro para iniciar a migração porque não depende de banco próprio, `Flask-Login` separado ou rotas complexas. Isso permite validar a estratégia de Blueprint sem mexer nos módulos mais sensíveis.

## URLs preservadas

As rotas continuam iguais para o usuário:

- `/editor-admin/`
- `/editor-admin/login`
- `/editor-admin/logout`
- `/editor-admin/servicos`
- `/editor-admin/projetos`
- `/editor-admin/estrutura`
- `/editor-admin/detalhe`

## Arquivos principais

- `editor_admin_app/routes.py`: contém o Blueprint `editor_admin_bp`.
- `editor_admin_app/app.py`: ficou apenas como factory standalone de compatibilidade.
- `portal.py`: registra o Blueprint diretamente.
- `legacy_wsgi_bridge.py`: removeu o Editor Admin da ponte WSGI.

## Próximo passo recomendado

Converter o `prompt_app` para Blueprint nativo, porque ele já está mais modularizado que o `curso_ingles_app`. Depois disso, converter o financeiro e deixar o curso por último, pois o curso ainda é o módulo mais extenso.
