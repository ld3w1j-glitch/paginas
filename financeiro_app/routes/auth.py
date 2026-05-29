from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from financeiro_app.extensions import db
from financeiro_app.models import User


auth_bp = Blueprint("financeiro_auth", __name__, url_prefix="/financeiro/auth")


def _is_finance_user() -> bool:
    try:
        return current_user.is_authenticated and str(current_user.get_id()).startswith("financeiro:")
    except Exception:
        return False


@auth_bp.before_request
def isolate_finance_auth_session():
    if current_user.is_authenticated and not _is_finance_user():
        logout_user()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Informe nome, e-mail e senha com pelo menos 6 caracteres.", "danger")
            return render_template("financeiro/auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "warning")
            return redirect(url_for("financeiro_auth.login"))
        user = User(name=name, email=email, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Conta criada com sucesso.", "success")
        return redirect(url_for("financeiro.dashboard"))
    return render_template("financeiro/auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if _is_finance_user():
        return redirect(url_for("financeiro.dashboard"))
    if request.method == "POST":
        login_value = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(or_(User.email == login_value, User.username == login_value)).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Login realizado com sucesso.", "success")
            if user.is_admin:
                return redirect(url_for("financeiro.admin_ai"))
            return redirect(url_for("financeiro.dashboard"))
        flash("Login ou senha inválidos.", "danger")
    return render_template("financeiro/auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("financeiro_auth.login"))
