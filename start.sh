#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export PYTHONUNBUFFERED=1

exec gunicorn --bind "0.0.0.0:${PORT}" --workers "${WEB_CONCURRENCY:-1}" --timeout "${GUNICORN_TIMEOUT:-120}" app:application
