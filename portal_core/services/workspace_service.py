"""Workspaces isolados por usuário para arquivos gerados pelo agente."""
from __future__ import annotations

import os
from pathlib import Path

from storage_service import workspace_dir


def agent_workspace(user_id: int) -> Path:
    root = Path(workspace_dir("curso_ingles_agent"))
    workspace = root / f"user_{int(user_id)}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def safe_join(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if os.path.commonpath([str(base), str(target)]) != str(base):
        raise ValueError("Caminho fora do workspace do usuário.")
    return target
