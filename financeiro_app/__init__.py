from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db, login_manager
from .models import User


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
            _ensure_light_migrations()
            User.ensure_admin()

    return app


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    init_financeiro_app(app)
    return app


def _ensure_light_migrations():
    """Pequenas migrações automáticas para bancos já existentes.

    Mantida como ponte de compatibilidade até todas as alterações de schema
    estarem versionadas no Alembic.
    """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    table_name = "finance_bank_account"
    if table_name in tables:
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "color" not in existing_columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE finance_bank_account ADD COLUMN color VARCHAR(20) DEFAULT '#2563eb' NOT NULL"))

    user_table = "finance_user"
    if user_table in tables:
        user_columns = {column["name"] for column in inspector.get_columns(user_table)}
        with db.engine.begin() as connection:
            if "username" not in user_columns:
                connection.execute(text("ALTER TABLE finance_user ADD COLUMN username VARCHAR(80)"))
            if "role" not in user_columns:
                connection.execute(text("ALTER TABLE finance_user ADD COLUMN role VARCHAR(30) DEFAULT 'user'"))
