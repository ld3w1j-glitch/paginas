from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from db_cli_utils import postgres_env

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", ROOT / "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
url = os.getenv("CURSO_INGLES_DATABASE_URL") or os.getenv("DATABASE_URL") or f"sqlite:///{ROOT / 'curso_ingles_app' / 'legiao.db'}"
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

if url.startswith("sqlite:///"):
    source = Path(url.replace("sqlite:///", "", 1)).resolve()
    target = BACKUP_DIR / f"portal_{stamp}.sqlite3"
    if not source.exists():
        raise SystemExit(f"Banco SQLite não encontrado: {source}")
    shutil.copy2(source, target)
else:
    target = BACKUP_DIR / f"portal_{stamp}.dump"
    pg_env = postgres_env(url)
    subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(target), "--dbname", pg_env["PGDATABASE"]],
        check=True,
        env=pg_env,
    )

print(target)
