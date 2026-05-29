# Fase 4E.9 — blindagem contra detecção errada do Railway

Problema observado: mesmo com `railway.json` apontando para `portal:application`, o deploy ainda podia abrir somente o Editor Admin. Isso normalmente acontece quando a plataforma usa detecção automática ou configuração antiga e acaba carregando `editor_admin_app/app.py` como aplicação principal.

Correção aplicada:

- criado `app.py` na raiz apontando para `portal.application`;
- criado `wsgi.py` na raiz apontando para `portal.application`;
- `editor_admin_app/app.py` agora, por padrão, devolve o portal completo se for carregado por engano;
- para rodar somente o Editor Admin localmente, usar `RUN_EDITOR_STANDALONE=1`;
- mantido `railway.json`, `Procfile`, `nixpacks.toml` e `start.sh` apontando para `portal:application`.

Com isso, mesmo que o Railway detecte `app.py` ou o módulo do Editor Admin, a aplicação principal será a Central de Programas.
