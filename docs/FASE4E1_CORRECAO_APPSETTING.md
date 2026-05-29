# Fase 4E.1 — Correção do erro AppSetting no SQLAlchemy

## Problema

Ao iniciar o portal, o SQLAlchemy interrompia o boot com:

```text
sqlalchemy.exc.InvalidRequestError: Multiple classes found for path "AppSetting" in the registry of this declarative base. Please use a fully module-qualified path.
```

Isso aconteceu porque, depois da unificação do `db`, existem modelos com o mesmo nome Python em módulos diferentes, como:

- `prompt_app.models.AppSetting`
- `financeiro_app.models.AppSetting`

A relação do financeiro usava apenas:

```python
db.relationship("AppSetting")
```

Com um único registry declarativo, esse nome ficou ambíguo.

## Correção aplicada

No arquivo `financeiro_app/models.py`, a relação foi alterada para usar o caminho completo:

```python
db.relationship("financeiro_app.models.AppSetting", backref="user", lazy=True, cascade="all, delete-orphan")
```

## Prevenção

O `check_project.py` agora possui uma checagem extra para detectar `relationship("Classe")` quando `Classe` existe em mais de um módulo.

Assim, o erro passa a ser identificado antes do deploy ou antes de rodar o portal.
