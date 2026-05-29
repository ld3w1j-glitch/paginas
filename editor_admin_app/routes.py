from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from security_config import get_admin_password, get_admin_user

editor_admin_bp = Blueprint(
    "editor_admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/editor-admin/static",
    url_prefix="/editor-admin",
)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("editor_admin_ok"):
            return redirect(url_for("editor_admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@editor_admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == get_admin_user() and password == get_admin_password():
            session["editor_admin_ok"] = True
            session["editor_admin_user"] = username
            next_url = request.args.get("next") or url_for("editor_admin.index")
            return redirect(next_url)
        error = "Login ou senha do admin incorretos."
    return render_template("editor_admin/admin_login.html", error=error)


@editor_admin_bp.route("/logout")
def logout():
    session.pop("editor_admin_ok", None)
    session.pop("editor_admin_user", None)
    return redirect(url_for("editor_admin.login"))


@editor_admin_bp.route("/")
@admin_required
def index():
    return render_template("editor_admin/index.html")


@editor_admin_bp.route("/servicos")
@admin_required
def servicos():
    return render_template("editor_admin/servicos.html")


@editor_admin_bp.route("/projetos")
@admin_required
def projetos():
    return render_template("editor_admin/projetos.html")


@editor_admin_bp.route("/estrutura")
@admin_required
def estrutura():
    return render_template("editor_admin/estrutura.html")


@editor_admin_bp.route("/detalhe")
@admin_required
def detalhe():
    return render_template("editor_admin/detalhe.html")
