# Operação, backup e recuperação

- `/health` permanece como healthcheck simples.
- logs rotativos ficam em `instance/logs/portal.log` por padrão.
- use `scripts/backup_db.py` para gerar backup.
- restauração deve ser testada periodicamente; backup nunca testado não é recuperação garantida.
- em PostgreSQL, os scripts usam `pg_dump`/`pg_restore` quando disponíveis.

## Restauração segura

A restauração pede confirmação explícita (`RESTAURAR`). Em automações controladas, use `--yes`. No SQLite, o script cria automaticamente um backup `pre_restore_*` do banco atual antes de substituí-lo. Para PostgreSQL, a senha é entregue a `pg_dump`/`pg_restore` via ambiente (`PGPASSWORD`) e não é colocada na linha de comando.

```bash
python scripts/backup_db.py
python scripts/restore_db.py backups/SEU_BACKUP.sqlite3
# somente em automação conscientemente autorizada:
python scripts/restore_db.py backups/SEU_BACKUP.sqlite3 --yes
```
