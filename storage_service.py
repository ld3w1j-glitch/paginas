"""Caminhos de armazenamento centralizados.

No Railway o disco do container é efêmero. Para produção, configure
PERSISTENT_STORAGE_DIR apontando para um volume persistente. Em ambiente local,
o padrão fica dentro de instance/storage.
"""
from __future__ import annotations

import os
from pathlib import Path
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_STORAGE_DIR = BASE_DIR / "instance" / "storage"


def storage_root() -> Path:
    root = Path(os.getenv("PERSISTENT_STORAGE_DIR", DEFAULT_STORAGE_DIR)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def storage_path(area: str, *parts: str, create: bool = True) -> Path:
    safe_area = secure_filename(area) or "geral"
    path = storage_root() / safe_area
    for part in parts:
        safe_part = secure_filename(str(part)) if part else ""
        if safe_part:
            path = path / safe_part
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_dir(app_name: str) -> Path:
    return storage_path(app_name, "uploads")


def workspace_dir(app_name: str) -> Path:
    return storage_path(app_name, "workspace")
