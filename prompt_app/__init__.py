from pathlib import Path

from flask import Flask
from security_config import get_database_url, get_secret_key
from extensions import db, login_manager
from .models import User
from .routes import prompt_bp, register_routes

_routes_registered = False


def init_prompt_app(app: Flask, *, create_tables: bool = True) -> Flask:
    """Inicializa o módulo Prompt dentro de qualquer app Flask.

    Fase 4C: o Prompt virou Blueprint real. Esta função mantém a
    compatibilidade com o modo isolado e permite registrar o módulo no
    portal principal sem DispatcherMiddleware.
    """
    app.config.setdefault("SECRET_KEY", get_secret_key())
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", get_database_url("sqlite:///prompt_profissional.db"))
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("MAX_CONTENT_LENGTH", 20 * 1024 * 1024)
    app.config.setdefault("SESSION_COOKIE_NAME", "prompt_session")
    app.config.setdefault("UPLOAD_EXTENSIONS", [".zip"])

    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except RuntimeError:
        pass

    if "sqlalchemy" not in app.extensions:
        db.init_app(app)

    login_manager.login_view = "prompt.login"
    login_manager.init_app(app)

    global _routes_registered
    if not _routes_registered:
        register_routes(prompt_bp)
        _routes_registered = True

    if create_tables:
        with app.app_context():
            db.create_all()
            User.ensure_admin()
    return app


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    init_prompt_app(app)
    app.register_blueprint(prompt_bp)
    return app
