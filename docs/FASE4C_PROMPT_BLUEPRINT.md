# Fase 4C — Prompt Profissional como Blueprint nativo

Nesta fase o módulo `prompt_app` deixou de ser montado pela ponte `DispatcherMiddleware` e passou a ser registrado diretamente no portal principal como Blueprint Flask em `/prompt`.

## O que mudou

- `prompt_app/routes.py` agora expõe `prompt_bp`.
- `prompt_app/__init__.py` agora possui `init_prompt_app(app)` para inicializar banco, login e rotas dentro do app principal.
- `portal.py` registra `prompt_bp` diretamente com `url_prefix="/prompt"`.
- `legacy_wsgi_bridge.py` não monta mais `/prompt`; a ponte agora fica apenas para `financeiro` e `curso-ingles`.
- Templates do Prompt foram ajustados para endpoints `prompt.*`.
- Chamadas JavaScript do Chat Executor agora respeitam automaticamente a base `/prompt`.

## Por que foi feito assim

A migração por partes reduz risco: o Prompt já compartilha a aplicação principal, mas Financeiro e Curso continuam isolados até suas rotas, autenticação e templates serem convertidos com segurança.

## Próximo passo recomendado

Converter o `financeiro_app` para Blueprint real. Ele é menor que o curso, mas mais complexo que o Editor Admin porque possui banco, uploads e rotas de importação PDF.
