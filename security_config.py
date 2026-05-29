"""Configuração central de segurança para todos os apps do portal.

Objetivo:
- não deixar senha real ou chave fraca gravada no código;
- exigir variáveis de ambiente em produção/Railway;
- permitir desenvolvimento local sem expor credenciais sensíveis do usuário.
"""
from __future__ import annotations

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def is_production() -> bool:
    value = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_PROJECT_ID")
        or value in {"prod", "production"}
    )


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(
            f"Variável de ambiente obrigatória ausente: {name}. "
            "Configure essa variável no Railway ou no arquivo .env local."
        )
    return value


def get_secret_key() -> str:
    value = os.getenv("SECRET_KEY")
    if value:
        return value
    if is_production():
        return require_env("SECRET_KEY")
    return "dev-secret-key-local-only-change-me"


def get_admin_user() -> str:
    value = os.getenv("ADMIN_USER") or os.getenv("CURSO_ADMIN_USER")
    if value:
        return value
    if is_production():
        return require_env("ADMIN_USER")
    return "admin"


def get_admin_password() -> str:
    value = os.getenv("ADMIN_PASSWORD") or os.getenv("CURSO_ADMIN_PASSWORD")
    if value:
        return value
    if is_production():
        return require_env("ADMIN_PASSWORD")
    return "admin-local-change-me"


def get_admin_email() -> str:
    return os.getenv("ADMIN_EMAIL", "admin@local.test")


def looks_like_placeholder_database_url(url: str | None) -> bool:
    """Detecta DATABASE_URL deixado com texto de exemplo.

    Exemplo comum que quebra o SQLAlchemy no boot:
    postgresql://usuario:senha@host:porta/banco

    Em ambiente local isso deve cair para SQLite para não travar o teste.
    Em produção isso deve falhar com mensagem clara.
    """
    if not url:
        return False
    lowered = url.strip().lower()
    placeholders = (
        "porta",
        "usuario",
        "senha",
        "host",
        "banco",
        "postgresql://...",
        "postgres://...",
        "database_url",
    )
    return any(token in lowered for token in placeholders)


def normalize_database_url(url: str | None) -> str | None:
    if not url:
        return url
    url = url.strip()
    if looks_like_placeholder_database_url(url):
        return None
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    return url


def get_database_url(local_sqlite_url: str, *, env_name: str = "DATABASE_URL") -> str:
    raw_value = os.getenv(env_name) or os.getenv("DATABASE_URL")
    normalized = normalize_database_url(raw_value)
    if normalized:
        return normalized
    if raw_value and looks_like_placeholder_database_url(raw_value):
        message = (
            f"A variável {env_name}/DATABASE_URL parece estar com valor de exemplo: {raw_value!r}. "
            "Troque por uma URL real do Postgres ou remova essa variável para testar local com SQLite."
        )
        if is_production():
            raise RuntimeError(message)
        print(f"[AVISO] {message} Usando SQLite local temporariamente.")
    if is_production():
        return require_env(env_name)
    return local_sqlite_url
