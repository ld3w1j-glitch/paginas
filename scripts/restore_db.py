from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from db_cli_utils import postgres_env

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", ROOT / "backups"))

parser = argparse.ArgumentParser(description="Restaura o banco do Portal de Cursos.")
parser.add_argument("backup", help="Caminho do arquivo de backup")
parser.add_argument("--yes", action="store_true", help="Confirma a operação destrutiva sem prompt interativo")
args = parser.parse_args()

backup = Path(args.backup).resolve()
if not backup.exists():
    raise SystemExit("Backup não encontrado.")

url = os.getenv("CURSO_INGLES_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite:///{ROOT / 'curso_ingles_app' / 'legiao.db'}"

if not args.yes:
    answer = input("A restauração pode substituir dados atuais. Digite RESTAURAR para continuar: ").strip()
    if answer != "RESTAURAR":
        raise SystemExit("Restauração cancelada.")

if url.startswith("sqlite:///"):
    target = Path(url.replace("sqlite:///", "", 1)).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        safety = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
        shutil.copy2(target, safety)
        print(f"Backup de segurança do banco atual: {safety}")
    shutil.copy2(backup, target)
else:
    pg_env = postgres_env(url)
    with backup.open("rb") as archive:
        subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--dbname", pg_env["PGDATABASE"]],
            check=True,
            env=pg_env,
            stdin=archive,
        )
print("Restauração concluída.")
