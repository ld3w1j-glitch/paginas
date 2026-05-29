#!/usr/bin/env bash
set -euo pipefail

# Railway/Railpack entrypoint.
# Uses Railway's PORT when available and falls back to 8080.
export PORT="${PORT:-8080}"
export PYTHONUNBUFFERED=1

exec gunicorn --bind "0.0.0.0:${PORT}" --workers "${WEB_CONCURRENCY:-1}" --timeout "${GUNICORN_TIMEOUT:-120}" portal:application
