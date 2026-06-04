from pathlib import Path

from flask import Flask
from .config import Config
from .extensions import db, login_manager
from .models import User
from .schema_utils import ensure_finance_schema


_routes_registered = False


def init_financeiro_app(app: Flask, *, create_tables: bool = True) -> Flask:
    """Inicializa o Financeiro como Blueprint nativo dentro do portal.

    Mantém compatibilidade com o modo separado, mas no portal principal ele
    passa a responder diretamente em `/financeiro`, sem DispatcherMiddleware.
    """
    app.config.from_object(Config)
    app.config.setdefault("SESSION_COOKIE_NAME", "portal_session")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    if "sqlalchemy" not in app.extensions:
        db.init_app(app)

    login_manager.login_view = "financeiro_auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.init_app(app)

    from .routes.auth import auth_bp
    from .routes.main import main_bp

    global _routes_registered
    if not _routes_registered:
        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        _routes_registered = True

    if create_tables:
        with app.app_context():
            db.create_all()
            ensure_finance_schema()
            User.ensure_admin()

    return app


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    init_financeiro_app(app)
    return app


# Migrações leves movidas para financeiro_app/schema_utils.py
