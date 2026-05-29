# Fase 4E.6 — Correção Railway/Railpack

Correção para erro de deploy no Railway/Railpack:

```text
Script start.sh not found
Railpack could not determine how to build the app.
```

Alterações:

- Adicionado `start.sh` na raiz do projeto.
- Adicionado `main.py` na raiz como fallback de detecção Python.
- Atualizado `Procfile` para `web: bash start.sh`.
- Atualizado `railway.json` para usar `bash start.sh`.

Importante: no Railway, suba a raiz do projeto completo. A raiz precisa conter:

- `requirements.txt`
- `portal.py`
- `run.py`
- `main.py`
- `start.sh`
- `Procfile`
- `railway.json`

Se o deploy mostrar que analisou apenas `curso_ingles_app/` e `editor_admin_app/`, o upload foi feito da pasta errada ou o repositório está incompleto.
