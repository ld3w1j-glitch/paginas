"""Logging estruturado e correlação de requisições."""
from __future__ import annotations

import logging
import os
import time
import uuid
from logging.handlers import RotatingFileHandler

from flask import current_app, g, request


def configure_logging(app) -> None:
    log_dir = os.getenv("LOG_DIR") or os.path.join(app.instance_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(log_dir, "portal.log"), maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def before_request_logging() -> None:
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    g.request_started_at = time.monotonic()


def after_request_logging(response):
    started = getattr(g, "request_started_at", time.monotonic())
    duration_ms = int((time.monotonic() - started) * 1000)
    user = getattr(g, "user", None)
    request_id = getattr(g, "request_id", "-")
    # Evita poluir logs com assets estáticos.
    if not request.path.startswith("/static/"):
        current_app.logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s user_id=%s",
            request_id,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            getattr(user, "id", None),
        )
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response
