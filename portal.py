import os
from flask import Flask

from security_config import get_secret_key
from portal_blueprints import portal_bp
from legacy_wsgi_bridge import attach_legacy_apps
from editor_admin_app.routes import editor_admin_bp
from prompt_app import init_prompt_app
from prompt_app.routes import prompt_bp
from financeiro_app import init_financeiro_app


def create_portal_app():
    app = Flask(__name__, template_folder="portal_templates", static_folder="portal_static")
    app.config["SECRET_KEY"] = get_secret_key()
    app.config["SESSION_COOKIE_NAME"] = "portal_session"
    app.register_blueprint(portal_bp)
    app.register_blueprint(editor_admin_bp)
    init_prompt_app(app)
    app.register_blueprint(prompt_bp, url_prefix="/prompt")
    init_financeiro_app(app)
    return app


def create_application():
    """Factory principal do deploy.

    Fase 4D: o portal, o Editor Admin, o Prompt Profissional e o Financeiro
    já são Blueprints reais. Apenas o Curso ainda entra pela ponte WSGI
    até ser migrado com segurança.
    """
    return attach_legacy_apps(create_portal_app())


application = create_application()


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    port = int(os.getenv("PORT", "5000"))
    run_simple(
        "0.0.0.0",
        port,
        application,
        use_debugger=os.getenv("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )
