"""Política de menor privilégio para o agente do Portal."""
from __future__ import annotations

import os
from pathlib import Path

BLOCKED_NAMES = {".ssh", ".aws", ".gnupg", ".env", "id_rsa", "id_ed25519"}


def validate_relative_agent_path(relative_path: str) -> str:
    raw = (relative_path or "").replace("\\", "/").strip()
    raw_parts = [part for part in raw.split("/") if part]
    if not raw_parts:
        raise ValueError("Caminho vazio.")
    if raw.startswith("/") or os.path.isabs(raw) or ":" in raw_parts[0]:
        raise ValueError("O agente só pode usar caminhos relativos ao workspace.")
    if any(part == ".." for part in raw_parts):
        raise ValueError("Travessia de diretórios não é permitida no workspace do agente.")
    parts = [part for part in raw_parts if part != "."]
    if any(part.lower() in BLOCKED_NAMES for part in parts):
        raise ValueError("O agente não pode criar ou acessar caminhos sensíveis.")
    return "/".join(parts)


def describe_policy(workspace: Path) -> dict:
    return {
        "workspace": str(workspace),
        "filesystem_scope": "workspace-only",
        "network_default": "off-for-sandbox-workers",
        "docker_default": "off",
        "credentials_default": "off",
    }
