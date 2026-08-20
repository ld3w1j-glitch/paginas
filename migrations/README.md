# Migrations

A infraestrutura Flask-Migrate/Alembic está ativa.

```bash
python -m flask --app app:application db upgrade
python -m flask --app app:application db migrate -m "descricao"
python -m flask --app app:application db upgrade
```

A primeira migration Level 6 é tolerante ao banco legado: se `db.create_all()` já tiver criado `curso_audit_log`, ela apenas registra a revisão. O bootstrap legado foi mantido nesta versão para não quebrar instalações locais existentes; novas alterações de schema devem usar migrations.
