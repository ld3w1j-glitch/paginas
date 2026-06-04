from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db


_COLUMN_TYPES = {
    "sqlite": {
        "bank_color": "VARCHAR(20) DEFAULT '#2563eb' NOT NULL",
        "user_username": "VARCHAR(80)",
        "user_role": "VARCHAR(30) DEFAULT 'user'",
        "tx_category": "VARCHAR(120) DEFAULT 'Geral' NOT NULL",
        "tx_is_fixed": "BOOLEAN DEFAULT 0",
        "tx_periodicity": "VARCHAR(40)",
        "tx_receipt_filename": "VARCHAR(255)",
        "tx_created_at": "DATETIME",
    },
    "postgresql": {
        "bank_color": "VARCHAR(20) DEFAULT '#2563eb' NOT NULL",
        "user_username": "VARCHAR(80)",
        "user_role": "VARCHAR(30) DEFAULT 'user'",
        "tx_category": "VARCHAR(120) DEFAULT 'Geral' NOT NULL",
        "tx_is_fixed": "BOOLEAN DEFAULT FALSE",
        "tx_periodicity": "VARCHAR(40)",
        "tx_receipt_filename": "VARCHAR(255)",
        "tx_created_at": "TIMESTAMP",
    },
    "mysql": {
        "bank_color": "VARCHAR(20) DEFAULT '#2563eb' NOT NULL",
        "user_username": "VARCHAR(80)",
        "user_role": "VARCHAR(30) DEFAULT 'user'",
        "tx_category": "VARCHAR(120) DEFAULT 'Geral' NOT NULL",
        "tx_is_fixed": "BOOLEAN DEFAULT FALSE",
        "tx_periodicity": "VARCHAR(40)",
        "tx_receipt_filename": "VARCHAR(255)",
        "tx_created_at": "DATETIME",
    },
}


def _dialect_types() -> dict[str, str]:
    name = db.engine.dialect.name
    return _COLUMN_TYPES.get(name, _COLUMN_TYPES["sqlite"])


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column(connection, table_name: str, column_name: str, column_type: str) -> None:
    # Nomes de colunas/tabelas são constantes internas, não vêm do usuário.
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def ensure_finance_schema() -> None:
    """Aplica migrações leves compatíveis com SQLite, PostgreSQL e MySQL.

    O Railway normalmente usa PostgreSQL. A versão anterior tentava criar
    `DATETIME`, que não existe no PostgreSQL. Isso podia quebrar a importação
    de PDF ou impedir colunas novas como `receipt_filename`.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    types = _dialect_types()

    try:
        with db.engine.begin() as connection:
            if "finance_bank_account" in tables:
                cols = _column_names(inspector, "finance_bank_account")
                if "color" not in cols:
                    _add_column(connection, "finance_bank_account", "color", types["bank_color"])

            if "finance_user" in tables:
                cols = _column_names(inspector, "finance_user")
                if "username" not in cols:
                    _add_column(connection, "finance_user", "username", types["user_username"])
                if "role" not in cols:
                    _add_column(connection, "finance_user", "role", types["user_role"])

            if "finance_transaction" in tables:
                cols = _column_names(inspector, "finance_transaction")
                if "category" not in cols:
                    _add_column(connection, "finance_transaction", "category", types["tx_category"])
                if "is_fixed" not in cols:
                    _add_column(connection, "finance_transaction", "is_fixed", types["tx_is_fixed"])
                if "periodicity" not in cols:
                    _add_column(connection, "finance_transaction", "periodicity", types["tx_periodicity"])
                if "receipt_filename" not in cols:
                    _add_column(connection, "finance_transaction", "receipt_filename", types["tx_receipt_filename"])
                if "created_at" not in cols:
                    _add_column(connection, "finance_transaction", "created_at", types["tx_created_at"])
    except SQLAlchemyError:
        db.session.rollback()
        raise
