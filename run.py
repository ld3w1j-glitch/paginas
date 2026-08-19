"""Inicialização local compatível com versões anteriores do projeto."""

from app import application


if __name__ == "__main__":
    import os

    application.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
