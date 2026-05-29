"""Extensões compartilhadas entre os programas do portal.

Todos os módulos Flask importam o mesmo `db` e o mesmo `login_manager`.
A autenticação usa IDs prefixados por domínio, por exemplo `prompt:1` ou
`financeiro:1`, evitando conflito entre tabelas de usuários diferentes.
"""
from flask import flash, redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_message = "Entre para continuar."


@login_manager.user_loader
def load_portal_user(user_id: str):
    """Carrega usuários de módulos diferentes sem misturar identidades."""
    if not user_id:
        return None
    try:
        domain, raw_id = str(user_id).split(":", 1)
        numeric_id = int(raw_id)
    except (ValueError, TypeError):
        # Compatibilidade com sessões antigas do Prompt antes do prefixo.
        try:
            from prompt_app.models import User as PromptUser
            return db.session.get(PromptUser, int(user_id))
        except Exception:
            return None

    if domain == "prompt":
        from prompt_app.models import User as PromptUser
        return db.session.get(PromptUser, numeric_id)
    if domain == "financeiro":
        from financeiro_app.models import User as FinanceUser
        return db.session.get(FinanceUser, numeric_id)
    return None


@login_manager.unauthorized_handler
def route_unauthorized_user():
    """Envia cada módulo para sua própria tela de login."""
    flash(login_manager.login_message or "Entre para continuar.", "warning")
    if request.path.startswith("/financeiro"):
        return redirect(url_for("financeiro_auth.login", next=request.url))
    if request.path.startswith("/prompt"):
        return redirect(url_for("prompt.login", next=request.url))
    return redirect(url_for("prompt.login", next=request.url))
