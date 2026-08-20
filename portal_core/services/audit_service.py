"""Registro de ações administrativas e sensíveis."""
from __future__ import annotations

import json

from portal_core.rate_limit import request_ip


def write_audit(db, AuditLog, *, actor, action: str, target: str = "", metadata: dict | None = None) -> None:
    row = AuditLog(
        user_id=getattr(actor, "id", None),
        action=(action or "unknown")[:120],
        target=(target or "")[:255],
        ip_address=request_ip()[:64],
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False)[:8000],
    )
    db.session.add(row)
