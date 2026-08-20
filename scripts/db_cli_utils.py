"""Utilidades para pg_dump/pg_restore sem expor senha na linha de comando."""
from __future__ import annotations

import os
from urllib.parse import parse_qs, unquote, urlparse


def postgres_env(database_url: str) -> dict[str, str]:
    """Converte DATABASE_URL em variáveis PG* para ferramentas do PostgreSQL.

    A senha vai em PGPASSWORD no ambiente do processo filho, evitando colocá-la no argv
    de pg_dump/pg_restore, que pode ficar visível em listagens de processos.
    """
    normalized = database_url.replace("postgresql+pg8000://", "postgresql://", 1).replace(
        "postgres+pg8000://", "postgresql://", 1
    )
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL não é PostgreSQL.")

    env = os.environ.copy()
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("DATABASE_URL PostgreSQL não informa o nome do banco.")
    env["PGDATABASE"] = unquote(database)

    query = parse_qs(parsed.query)
    if query.get("sslmode"):
        env["PGSSLMODE"] = query["sslmode"][0]
    return env
