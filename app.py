"""Entrada principal do Portal de Cursos."""

import os

from curso_ingles_app.app import create_app


application = create_app()
app = application


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    application.run(
        host="0.0.0.0",
        port=port,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
