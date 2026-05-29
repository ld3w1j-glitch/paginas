"""Entrada WSGI raiz para plataformas que procuram automaticamente app.py.

Railway/Railpack às vezes tenta detectar um Flask app sozinho. Este arquivo
força qualquer detecção automática a carregar o portal principal, não um
submódulo como editor_admin_app.
"""
from portal import application

# Nomes comuns usados por Gunicorn/Railpack/Nixpacks.
app = application

if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "5000"))
    application.run(host="0.0.0.0", port=port)
