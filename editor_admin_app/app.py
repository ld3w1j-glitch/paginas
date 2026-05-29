import os

from flask import Flask

from security_config import get_secret_key
from .routes import editor_admin_bp


def create_app():
    """Compatibilidade do Editor Admin.

    Em produção/Railway, mesmo que a plataforma detecte este arquivo por
    engano, devolvemos o portal principal completo. Assim a URL raiz nunca
    fica presa somente no Editor Admin.

    Para rodar apenas o Editor Admin localmente, defina:
    RUN_EDITOR_STANDALONE=1
    """
    if os.getenv("RUN_EDITOR_STANDALONE", "0") != "1":
        from portal import create_application

        return create_application()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = get_secret_key()
    app.config["SESSION_COOKIE_NAME"] = "editor_admin_session"
    app.register_blueprint(editor_admin_bp)

    @app.route("/")
    def root_redirect():
        return (
            "<h1>Editor Admin iniciado sozinho</h1>"
            "<p>Este módulo é apenas uma parte do portal. "
            "No Railway, o Start Command precisa ser: "
            "<code>gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 portal:application</code></p>"
            "<p>Se você quer a Central de Programas, o deploy precisa iniciar <b>portal:application</b>, "
            "não <b>editor_admin_app.app</b>.</p>"
        )

    return app


# Variáveis comuns que plataformas de deploy procuram automaticamente.
application = create_app()
app = application


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    application.run(host="0.0.0.0", port=port, debug=True)
