# Fase 4E.8 — garantir que Railway inicia o portal correto

Problema observado: o deploy abriu somente o Editor Web/Admin, em vez da Central de Programas.

Correções:

- `railway.json` agora chama diretamente `portal:application` com Gunicorn.
- `Procfile` também aponta diretamente para `portal:application`.
- Adicionado `nixpacks.toml` como fallback explícito.
- Adicionadas rotas `/central` e `/programas` para abrir a Central.
- O `editor_admin_app/app.py`, quando iniciado sozinho por engano, mostra aviso explicando que o start correto é `portal:application`.

No Railway, confirme em Settings/Deploy que o start command não está apontando para `editor_admin_app`. O correto é:

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 portal:application
```

A raiz do deploy precisa conter `portal.py`, `requirements.txt`, `railway.json`, `Procfile` e `main.py`.
