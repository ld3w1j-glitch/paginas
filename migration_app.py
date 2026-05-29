"""Aplicação mínima para Flask-Migrate/Alembic.

Uso local:
  flask --app migration_app:app db migrate -m "mensagem"
  flask --app migration_app:app db upgrade

Ela carrega o mesmo `db` compartilhado e importa os modelos para que o Alembic
conheça as tabelas. A consolidação completa em blueprints fica para a fase 2.
"""
from flask import Flask
from flask_migrate import Migrate
from security_config import get_database_url, get_secret_key
from extensions import db

# Importa modelos para registrar metadata no SQLAlchemy.
import prompt_app.models  # noqa: F401
import financeiro_app.models  # noqa: F401
# O curso ainda está no arquivo-Deus; importar registra os modelos curso_*.
import curso_ingles_app.app  # noqa: F401


def create_migration_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = get_secret_key()
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url("sqlite:///instance/app.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    Migrate(app, db)
    return app


app = create_migration_app()
