from collections import defaultdict
from pathlib import Path
from uuid import uuid4
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user, logout_user
from werkzeug.utils import secure_filename
from financeiro_app.extensions import db
from financeiro_app.models import BankAccount, Transaction, AppSetting
from financeiro_app.forms import parse_float, parse_date
from financeiro_app.market import get_market_snapshot
from financeiro_app.pdf_importer import parse_financial_receipt, build_transaction_from_receipt
from ai_service import call_ai


main_bp = Blueprint("financeiro", __name__, url_prefix="/financeiro", template_folder="../templates", static_folder="../static", static_url_path="/static")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
DEFAULT_COLORS = ["#2563eb", "#7c3aed", "#059669", "#f97316", "#dc2626", "#0891b2", "#111827", "#ca8a04"]


def _is_finance_user() -> bool:
    """Confirma se a sessão atual pertence ao módulo Financeiro.

    Como o portal agora usa sessão compartilhada, um login feito no Prompt
    não pode ser aceito automaticamente dentro do Financeiro.
    """
    try:
        return current_user.is_authenticated and str(current_user.get_id()).startswith("financeiro:")
    except Exception:
        return False


@main_bp.before_request
def require_finance_identity():
    if current_user.is_authenticated and not _is_finance_user():
        logout_user()
        flash("Entre no Financeiro para continuar.", "warning")
        return redirect(url_for("financeiro_auth.login", next=request.url))


def get_setting(user_id, key, default=""):
    setting = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    return setting.value if setting else default


def set_setting(user_id, key, value):
    setting = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    if not setting:
        setting = AppSetting(user_id=user_id, key=key)
        db.session.add(setting)
    setting.value = value or ""


def admin_user():
    from financeiro_app.models import User
    return User.query.filter_by(role="admin").order_by(User.id.asc()).first()


def get_ai_config():
    import os
    admin = admin_user()
    api_key = get_setting(admin.id, "google_api_key") if admin else ""
    model = get_setting(admin.id, "gemini_model") if admin else ""
    api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return api_key.strip(), (model.strip() or "gemini-2.5-flash")


def require_admin():
    if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
        abort(403)


def money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_finance_context(limit=80):
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.occurrence_date.desc()).limit(limit).all()
    total_balance = sum(acc.current_balance for acc in accounts)
    all_transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    total_income = sum(tx.amount for tx in all_transactions if tx.type == "income")
    total_expense = sum(tx.amount for tx in all_transactions if tx.type == "expense")
    fixed_expenses = sum(tx.amount for tx in all_transactions if tx.type == "expense" and tx.is_fixed)
    lines = [
        "Você é uma IA financeira dentro de um sistema Flask de controle financeiro pessoal.",
        "Responda em português do Brasil, com orientação prática e sem prometer resultado financeiro garantido.",
        f"Saldo total: {money(total_balance)}",
        f"Receitas cadastradas: {money(total_income)}",
        f"Despesas cadastradas: {money(total_expense)}",
        f"Despesas fixas: {money(fixed_expenses)}",
        "Contas:",
    ]
    for acc in accounts:
        lines.append(f"- {acc.bank_name} / {acc.account_name}: saldo atual {money(acc.current_balance)}")
    lines.append("Últimas transações:")
    for tx in transactions:
        tipo = "receita" if tx.type == "income" else "despesa"
        fixa = " fixa" if tx.is_fixed else ""
        lines.append(f"- {tx.occurrence_date.strftime('%d/%m/%Y')} | {tipo}{fixa} | {tx.category} | {tx.description} | {money(tx.amount)}")
    return "\n".join(lines)


def run_finance_ai(action, extra_prompt=""):
    api_key, model = get_ai_config()
    if not api_key:
        return "A API ainda não foi configurada. Entre como admin e cadastre a chave em Admin IA."
    full_prompt = build_finance_context() + "\n\nPedido do usuário:\n" + (extra_prompt or "Analise minha situação financeira e gere recomendações objetivas.")
    return call_ai(action or "chat", full_prompt, api_key=api_key, model_name=model)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_color(value):
    value = (value or "#2563eb").strip()
    if len(value) == 7 and value.startswith("#"):
        return value
    return "#2563eb"


def account_or_404(account_id):
    return BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()


def transaction_or_404(tx_id):
    return Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("financeiro.dashboard"))
    return render_template("financeiro/index.html")


@main_bp.route("/admin-ia", methods=["GET", "POST"])
@login_required
def admin_ai():
    require_admin()
    if request.method == "POST":
        api_key = (request.form.get("google_api_key") or "").strip()
        model = (request.form.get("gemini_model") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        if request.form.get("clear_google_api_key"):
            set_setting(current_user.id, "google_api_key", "")
        elif api_key:
            set_setting(current_user.id, "google_api_key", api_key)
        set_setting(current_user.id, "gemini_model", model)
        db.session.commit()
        flash("Configuração da IA financeira salva com segurança.", "success")
        return redirect(url_for("financeiro.admin_ai"))
    api_key, model = get_ai_config()
    return render_template("financeiro/admin_ai.html", gemini_configured=bool(api_key), gemini_model=model)


@main_bp.route("/ai/analisar", methods=["POST"])
@login_required
def ai_analyze():
    action = request.form.get("action", "chat")
    origem = request.form.get("origem", "dashboard")
    prompt = request.form.get("prompt", "").strip()
    presets = {
        "dashboard": "Faça uma análise geral do meu dashboard financeiro. Mostre alertas, pontos bons, riscos e próximas ações.",
        "reports": "Analise os relatórios por categoria e por mês. Mostre onde estou gastando mais e quais cortes/reorganizações fazem sentido.",
        "transactions": "Analise minhas transações. Sugira categorias melhores, identifique possíveis gastos recorrentes e aponte lançamentos suspeitos ou duplicados.",
        "category": "Sugira uma categoria adequada para a transação informada e explique rapidamente o motivo.",
    }
    final_prompt = prompt or presets.get(origem, presets["dashboard"])
    ai_text = run_finance_ai(action, final_prompt)
    return render_template("financeiro/ai_result.html", ai_text=ai_text, origem=origem, prompt=final_prompt)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.occurrence_date.desc()).limit(8).all()
    total_balance = sum(acc.current_balance for acc in accounts)
    all_transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    total_income = sum(tx.amount for tx in all_transactions if tx.type == "income")
    total_expense = sum(tx.amount for tx in all_transactions if tx.type == "expense")
    fixed_expenses = sum(tx.amount for tx in all_transactions if tx.type == "expense" and tx.is_fixed)
    market = get_market_snapshot()
    return render_template(
        "financeiro/dashboard.html",
        accounts=accounts,
        transactions=transactions,
        total_balance=total_balance,
        total_income=total_income,
        total_expense=total_expense,
        fixed_expenses=fixed_expenses,
        market=market,
    )


@main_bp.route("/accounts", methods=["GET", "POST"])
@login_required
def accounts():
    if request.method == "POST":
        bank_name = request.form.get("bank_name", "").strip()
        account_name = request.form.get("account_name", "").strip()
        initial_balance = parse_float(request.form.get("initial_balance"))
        color = normalize_color(request.form.get("color"))
        if not bank_name or not account_name:
            flash("Informe banco e nome da conta.", "danger")
        else:
            db.session.add(BankAccount(
                user_id=current_user.id,
                bank_name=bank_name,
                account_name=account_name,
                initial_balance=initial_balance,
                color=color,
            ))
            db.session.commit()
            flash("Conta adicionada.", "success")
            return redirect(url_for("financeiro.accounts"))
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    return render_template("financeiro/accounts.html", accounts=accounts, colors=DEFAULT_COLORS, editing_account=None)


@main_bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(account_id):
    account = account_or_404(account_id)
    if request.method == "POST":
        account.bank_name = request.form.get("bank_name", "").strip()
        account.account_name = request.form.get("account_name", "").strip()
        account.initial_balance = parse_float(request.form.get("initial_balance"))
        account.color = normalize_color(request.form.get("color"))
        if not account.bank_name or not account.account_name:
            flash("Informe banco e nome da conta.", "danger")
        else:
            db.session.commit()
            flash("Conta atualizada com cor e saldo.", "success")
            return redirect(url_for("financeiro.accounts"))
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    return render_template("financeiro/accounts.html", accounts=accounts, colors=DEFAULT_COLORS, editing_account=account)


@main_bp.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id):
    account = account_or_404(account_id)
    db.session.delete(account)
    db.session.commit()
    flash("Conta removida.", "info")
    return redirect(url_for("financeiro.accounts"))


@main_bp.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    if request.method == "POST":
        if not accounts:
            flash("Cadastre uma conta bancária antes de lançar transações.", "warning")
            return redirect(url_for("financeiro.accounts"))
        receipt = request.files.get("receipt")
        filename = None
        if receipt and receipt.filename:
            if not allowed_file(receipt.filename):
                flash("Comprovante deve ser PDF, PNG, JPG, JPEG ou WEBP.", "danger")
                return redirect(url_for("financeiro.transactions"))
            safe = secure_filename(receipt.filename)
            filename = f"{uuid4().hex}_{safe}"
            receipt.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)

        tx = Transaction(
            user_id=current_user.id,
            account_id=int(request.form.get("account_id")),
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "Geral").strip() or "Geral",
            amount=parse_float(request.form.get("amount")),
            type=request.form.get("type", "expense"),
            occurrence_date=parse_date(request.form.get("occurrence_date")),
            is_fixed=bool(request.form.get("is_fixed")),
            periodicity=request.form.get("periodicity") or None,
            receipt_filename=filename,
        )
        if not tx.description or tx.amount <= 0 or tx.type not in ["income", "expense"]:
            flash("Preencha descrição, valor positivo e tipo válido.", "danger")
        else:
            db.session.add(tx)
            db.session.commit()
            flash("Transação registrada.", "success")
            return redirect(url_for("financeiro.transactions"))
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.occurrence_date.desc()).all()
    return render_template("financeiro/transactions.html", accounts=accounts, transactions=transactions, editing_tx=None)


@main_bp.route("/transactions/import-comprovante", methods=["POST"])
@login_required
def import_receipt_transaction():
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    if not accounts:
        flash("Cadastre uma conta bancária antes de importar comprovantes.", "warning")
        return redirect(url_for("financeiro.accounts"))

    account_id = request.form.get("account_id")
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first()
    if not account:
        flash("Selecione a conta onde a transação será registrada.", "danger")
        return redirect(url_for("financeiro.transactions"))

    receipt = request.files.get("receipt_pdf")
    if not receipt or not receipt.filename:
        flash("Selecione um PDF de comprovante Pix/transferência.", "danger")
        return redirect(url_for("financeiro.transactions"))
    if not receipt.filename.lower().endswith(".pdf"):
        flash("Para importação automática, envie um arquivo PDF. Imagens/prints ainda devem ser lançados manualmente.", "danger")
        return redirect(url_for("financeiro.transactions"))

    safe = secure_filename(receipt.filename)
    filename = f"{uuid4().hex}_{safe}"
    saved_path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    receipt.save(saved_path)

    try:
        parsed = parse_financial_receipt(saved_path)
        tx_data = build_transaction_from_receipt(parsed)
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        flash(f"Não consegui ler esse comprovante automaticamente: {exc}", "danger")
        return redirect(url_for("financeiro.transactions"))

    # Evita duplicar o mesmo comprovante quando o ID da transação já foi importado.
    existing = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.description.contains(parsed.transaction_id),
    ).first()
    if existing:
        saved_path.unlink(missing_ok=True)
        flash("Esse comprovante parece já ter sido importado antes.", "warning")
        return redirect(url_for("financeiro.transactions"))

    tx = Transaction(
        user_id=current_user.id,
        account_id=account.id,
        description=f"{tx_data['description']} | ID {parsed.transaction_id}",
        category=tx_data["category"],
        amount=tx_data["amount"],
        type=tx_data["type"],
        occurrence_date=tx_data["occurrence_date"],
        is_fixed=False,
        periodicity=None,
        receipt_filename=filename,
    )
    db.session.add(tx)
    db.session.commit()
    flash(f"Comprovante {parsed.source} importado: R$ {parsed.amount:.2f} para {parsed.receiver_name}.", "success")
    return redirect(url_for("financeiro.transactions"))


# Mantém compatibilidade com versões antigas e formulários salvos.
@main_bp.route("/transactions/import-picpay", methods=["POST"])
@login_required
def import_picpay_transaction():
    return import_receipt_transaction()


@main_bp.route("/transactions/<int:tx_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(tx_id):
    tx = transaction_or_404(tx_id)
    accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    if request.method == "POST":
        tx.account_id = int(request.form.get("account_id"))
        tx.description = request.form.get("description", "").strip()
        tx.category = request.form.get("category", "Geral").strip() or "Geral"
        tx.amount = parse_float(request.form.get("amount"))
        tx.type = request.form.get("type", "expense")
        tx.occurrence_date = parse_date(request.form.get("occurrence_date"))
        tx.is_fixed = bool(request.form.get("is_fixed"))
        tx.periodicity = request.form.get("periodicity") or None
        if not tx.description or tx.amount <= 0 or tx.type not in ["income", "expense"]:
            flash("Preencha descrição, valor positivo e tipo válido.", "danger")
        else:
            db.session.commit()
            flash("Transação atualizada.", "success")
            return redirect(url_for("financeiro.transactions"))
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.occurrence_date.desc()).all()
    return render_template("financeiro/transactions.html", accounts=accounts, transactions=transactions, editing_tx=tx)


@main_bp.route("/transactions/<int:tx_id>/delete", methods=["POST"])
@login_required
def delete_transaction(tx_id):
    tx = transaction_or_404(tx_id)
    db.session.delete(tx)
    db.session.commit()
    flash("Transação removida.", "info")
    return redirect(url_for("financeiro.transactions"))


@main_bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@main_bp.route("/reports")
@login_required
def reports():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.occurrence_date.asc()).all()
    by_category = defaultdict(float)
    by_month_income = defaultdict(float)
    by_month_expense = defaultdict(float)
    for tx in transactions:
        if tx.type == "expense":
            by_category[tx.category] += tx.amount
            by_month_expense[tx.occurrence_date.strftime("%Y-%m")] += tx.amount
        else:
            by_month_income[tx.occurrence_date.strftime("%Y-%m")] += tx.amount
    months = sorted(set(by_month_income) | set(by_month_expense))
    return render_template(
        "financeiro/reports.html",
        category_labels=list(by_category.keys()),
        category_values=list(by_category.values()),
        months=months,
        income_values=[by_month_income[m] for m in months],
        expense_values=[by_month_expense[m] for m in months],
    )
