"""Primitivas de segurança independentes das rotas do portal."""
from __future__ import annotations

import hmac
import secrets
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, current_app, flash, g, jsonify, redirect, request, session, url_for

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_protect_request() -> None:
    if request.method not in UNSAFE_METHODS:
        return
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    # Testes antigos continuam simples; testes de CSRF podem habilitar TEST_CSRF.
    if current_app.config.get("TESTING") and not current_app.config.get("TEST_CSRF"):
        return
    expected = session.get("_csrf_token")
    received = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
    if not expected or not received or not hmac.compare_digest(str(expected), str(received)):
        if request.path.startswith(("/api/", "/mcp/", "/agent-chat/")) or request.is_json:
            abort(400, description="Token CSRF ausente ou inválido.")
        flash("A sessão do formulário expirou. Atualize a página e tente novamente.", "warning")
        abort(400, description="Token CSRF ausente ou inválido.")


def is_safe_redirect_target(target: str | None) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and host_url.netloc == test_url.netloc


def safe_next_url(target: str | None, fallback_endpoint: str = "dashboard") -> str:
    if is_safe_redirect_target(target):
        return target  # type: ignore[return-value]
    return url_for(fallback_endpoint)


def permission_required(permission: str):
    """RBAC simples. Administrador possui todas as permissões críticas."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)
            if not user:
                flash("Faça login para continuar.", "warning")
                return redirect(url_for("login", next=request.path))
            allowed = bool(user.is_admin)
            if not allowed:
                if request.path.startswith("/api/") or request.is_json:
                    return jsonify({"ok": False, "error": f"Permissão necessária: {permission}."}), 403
                abort(403, description="Você não possui permissão para esta operação.")
            return view_func(*args, **kwargs)
        return wrapper
    return decorator
