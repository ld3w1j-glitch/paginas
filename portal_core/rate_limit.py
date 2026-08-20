"""Rate limit leve, sem dependência externa.

Serve como proteção básica por processo. Em produção com múltiplos workers, Redis/Flask-Limiter
é a evolução recomendada.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from flask import current_app, request

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _parse_rule(rule: str) -> tuple[int, int]:
    count_text, period_text = (rule or "60/minute").split("/", 1)
    count = max(1, int(count_text))
    period = period_text.strip().lower()
    seconds = 3600 if period.startswith("hour") else 86400 if period.startswith("day") else 60
    return count, seconds


def request_ip() -> str:
    # X-Forwarded-For só é confiável quando o deploy está atrás de um proxy conhecido.
    # Deixar isso opt-in evita que o cliente burle o rate limit forjando o cabeçalho.
    if current_app.config.get("TRUST_PROXY_HEADERS"):
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.remote_addr or "unknown"


def client_key(scope: str) -> tuple[str, str]:
    return scope, request_ip()


def check_rate_limit(scope: str, rule: str) -> tuple[bool, int]:
    # Evita interferência entre testes independentes. Testes específicos de rate limit
    # podem reativar o mecanismo com TEST_RATE_LIMIT=True.
    if current_app.config.get("TESTING") and not current_app.config.get("TEST_RATE_LIMIT", False):
        return True, 0

    limit, window = _parse_rule(rule)
    now = time.monotonic()
    key = client_key(scope)
    with _lock:
        bucket = _hits[key]
        cutoff = now - window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = max(1, int(window - (now - bucket[0])))
            return False, retry
        bucket.append(now)
    return True, 0
