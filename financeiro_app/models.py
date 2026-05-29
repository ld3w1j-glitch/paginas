from datetime import datetime, date
import os
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db
from security_config import get_admin_email, get_admin_password, get_admin_user


class User(UserMixin, db.Model):
    __tablename__ = "finance_user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    accounts = db.relationship("BankAccount", backref="user", lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="user", lazy=True, cascade="all, delete-orphan")
    settings = db.relationship("financeiro_app.models.AppSetting", backref="user", lazy=True, cascade="all, delete-orphan")

    def get_id(self):
        return f"financeiro:{self.id}"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return (self.role or "").lower() == "admin"

    @staticmethod
    def ensure_admin():
        """Cria/atualiza o administrador padrão do financeiro."""
        username = get_admin_user()
        password = get_admin_password()
        email = get_admin_email()
        admin = User.query.filter((User.username == username) | (User.email == email)).first()
        if not admin:
            admin = User(name=username, email=email, username=username, role="admin")
            admin.set_password(password)
            db.session.add(admin)
        else:
            admin.username = username
            admin.email = admin.email or email
            admin.role = "admin"
            admin.name = admin.name or username
            admin.set_password(password)
        db.session.commit()


class BankAccount(db.Model):
    __tablename__ = "finance_bank_account"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("finance_user.id"), nullable=False)
    bank_name = db.Column(db.String(120), nullable=False)
    account_name = db.Column(db.String(120), nullable=False)
    initial_balance = db.Column(db.Float, nullable=False, default=0.0)
    color = db.Column(db.String(20), nullable=False, default="#2563eb")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship("Transaction", backref="account", lazy=True, cascade="all, delete-orphan")

    @property
    def current_balance(self):
        total = self.initial_balance
        for tx in self.transactions:
            total += tx.signed_amount
        return total


class Transaction(db.Model):
    __tablename__ = "finance_transaction"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("finance_user.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("finance_bank_account.id"), nullable=False)
    description = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(120), nullable=False, default="Geral")
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # income ou expense
    occurrence_date = db.Column(db.Date, nullable=False, default=date.today)
    is_fixed = db.Column(db.Boolean, default=False)
    periodicity = db.Column(db.String(40), nullable=True)
    receipt_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def signed_amount(self):
        return self.amount if self.type == "income" else -self.amount


class AppSetting(db.Model):
    __tablename__ = "finance_app_setting"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("finance_user.id"), nullable=False, index=True)
    key = db.Column(db.String(120), nullable=False, index=True)
    value = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "key", name="uq_finance_user_setting_key"),)
