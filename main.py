"""Railway/Railpack fallback entrypoint.

Railpack can detect Python projects by a root main.py. Production should use
start.sh or the Procfile, but this file makes auto-detection safe.
"""
from __future__ import annotations

import os

from portal import application


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    application.run(host="0.0.0.0", port=port)
