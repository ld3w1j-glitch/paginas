"""Configuração central do Portal de Cursos.

Mantém diferenças de desenvolvimento, teste e produção fora das rotas.
"""
from __future__ import annotations

import os
from datetime import timedelta

from security_config import is_production


class BaseConfig:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    AGENT_MAX_FILE_BYTES = 2 * 1024 * 1024
    AGENT_MAX_TOTAL_BYTES = 10 * 1024 * 1024
    CSRF_ENABLED = True
    LOGIN_RATE_LIMIT = "5/minute"
    MCP_RATE_LIMIT = "20/minute"
    AGENT_RATE_LIMIT = "30/minute"
    JSON_SORT_KEYS = False
    TRUST_PROXY_HEADERS = False


class DevelopmentConfig(BaseConfig):
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    TESTING = True
    SESSION_COOKIE_SECURE = False
    CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


def configure_app(app) -> None:
    """Aplica a configuração base e depois os overrides permitidos por ambiente."""
    config = ProductionConfig if is_production() else DevelopmentConfig
    for key in dir(config):
        if key.isupper():
            app.config[key] = getattr(config, key)
    # Permite desligar apenas em desenvolvimento/teste explícito.
    app.config["LOGIN_RATE_LIMIT"] = os.getenv("LOGIN_RATE_LIMIT", app.config["LOGIN_RATE_LIMIT"])
    app.config["MCP_RATE_LIMIT"] = os.getenv("MCP_RATE_LIMIT", app.config["MCP_RATE_LIMIT"])
    app.config["AGENT_RATE_LIMIT"] = os.getenv("AGENT_RATE_LIMIT", app.config["AGENT_RATE_LIMIT"])
    app.config["TRUST_PROXY_HEADERS"] = os.getenv("TRUST_PROXY_HEADERS", "0").strip().lower() in {"1", "true", "yes"}
    if os.getenv("CSRF_ENABLED", "1").strip().lower() in {"0", "false", "no"} and not is_production():
        app.config["CSRF_ENABLED"] = False
